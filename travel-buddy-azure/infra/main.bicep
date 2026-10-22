// =====================================================================
// Travel Buddy on Azure Container Apps  (API + Celery worker + Redis)
// ---------------------------------------------------------------------
// Creates:   Log Analytics + Application Insights   (monitoring)
//            Azure Managed Redis                     (queue, sessions, cache, rate limits)
//            Container Registry                      (stores the app image)
//            User-assigned managed identity          (the apps' login, no passwords)
//            Container Apps environment              (where the apps run)
//            API app    (FastAPI, public, scales on HTTP load)
//            Worker app (Celery, no public address, scales on queue length)
//            Role assignments: AcrPull (pull the image), Azure AI User (call the model)
//
// Uses an EXISTING Foundry account for the AI model. It does not create one.
//
// Deploy in phases (see deploy.ps1):
//   1) deployApp = false   create everything except the two apps
//   2) build the image into the registry
//   3) deployApp = true    create the API and the worker, which need the image to exist
//
// Landing zone options: infrastructureSubnetId and internalOnly (see README).
// =====================================================================
targetScope = 'resourceGroup'

@description('Short name used in resource names: 3 to 12 lowercase letters or digits')
@minLength(3)
@maxLength(12)
param namePrefix string = 'travelbuddy'

param location string = resourceGroup().location

@description('Name of the EXISTING Foundry (AI Services) account that hosts the model')
param foundryAccountName string

@description('Resource group of the existing Foundry account')
param foundryResourceGroup string = resourceGroup().name

@description('Foundry project endpoint, for example https://NAME.services.ai.azure.com/api/projects/PROJECT')
param foundryProjectEndpoint string

@description('Name of the model deployment in Foundry')
param modelDeployment string = 'gpt-4.1-mini'

@description('false on the first run (everything except the app). true after the image is built.')
param deployApp bool = false

@description('Image tag built into the registry')
param imageTag string = 'v1'

@description('LANDING ZONE OPTION: subnet for the Container Apps environment. Empty means no virtual network integration.')
param infrastructureSubnetId string = ''

@description('LANDING ZONE OPTION: true makes the app reachable only from inside the virtual network.')
param internalOnly bool = false

@description('Azure Managed Redis size. Balanced_B1 is a small start. Check the sizes offered in your region.')
param redisSku string = 'Balanced_B1'

@description('Messages one person may send per minute (protects the model quota)')
param rateLimitPerMinute int = 10

@description('API: smallest and largest number of copies. Two or more means no single point of failure.')
param apiMinReplicas int = 2
param apiMaxReplicas int = 10

@description('API: add a copy when each one handles more than this many requests at the same moment')
param apiConcurrentRequests int = 50

@description('Worker: smallest and largest number of copies')
param workerMinReplicas int = 1
param workerMaxReplicas int = 10

@description('Worker: chats handled at the same time by ONE worker copy')
param workerConcurrency int = 4

@description('Worker: add a copy for every this many jobs waiting in the queue')
param queueLengthPerReplica int = 5

@description('Tags required by your organisation, for example { owner: "team", costCentre: "123" }')
param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var acrName = 'acr${namePrefix}${uniqueSuffix}'

// ----- Monitoring -----
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${namePrefix}-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${namePrefix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ----- Registry for the container image -----
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

// ----- The app's identity (replaces keys and passwords) -----
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${namePrefix}'
  location: location
  tags: tags
}

// Built-in role "AcrPull": allows pulling images from the registry
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// Allows the identity to call the model in the existing Foundry account
module foundryAccess 'foundry-access.bicep' = {
  name: 'foundry-access'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName: foundryAccountName
    principalId: identity.properties.principalId
    identityId: identity.id
  }
}

// ----- Redis: the queue, the sessions, the caches and the rate limits -----
// Azure Managed Redis (the current Redis service on Azure). One cluster with one database.
resource redis 'Microsoft.Cache/redisEnterprise@2024-05-01-preview' = {
  name: 'redis${namePrefix}${uniqueSuffix}'
  location: location
  tags: tags
  sku: {
    name: redisSku
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

resource redisDb 'Microsoft.Cache/redisEnterprise/databases@2024-05-01-preview' = {
  name: 'default'
  parent: redis
  properties: {
    clientProtocol: 'Encrypted'            // TLS only
    port: 10000
    // EnterpriseCluster presents ONE normal-looking address, so Celery (which cannot follow
    // cluster redirects) works. The other policy, OSSCluster, needs a cluster-aware client.
    clusteringPolicy: 'EnterpriseCluster'
    // When memory is full, remove only keys that have an expiry (sessions, caches, results).
    // The Celery queue has no expiry, so waiting jobs are never thrown away.
    evictionPolicy: 'VolatileLRU'
    persistence: {
      aofEnabled: false
      rdbEnabled: false
    }
  }
}

// The address the apps use. rediss (two s) means encrypted. The access key becomes a SECRET, never plain text.
var redisPrimaryKey = redisDb.listKeys().primaryKey
var redisUrl = 'rediss://:${redisPrimaryKey}@${redis.properties.hostName}:10000/0'

// ----- Where the apps run -----
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${namePrefix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    // Only set when a landing zone subnet is given. The subnet must be delegated to Microsoft.App/environments.
    vnetConfiguration: empty(infrastructureSubnetId) ? null : {
      infrastructureSubnetId: infrastructureSubnetId
      internal: internalOnly
    }
  }
}

// Settings and secrets that BOTH apps share
var appIdentity = {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${identity.id}': {}
  }
}

var appRegistries = [
  {
    server: acr.properties.loginServer
    identity: identity.id
  }
]

var appSecrets = [
  {
    name: 'appinsights-connection'
    value: appInsights.properties.ConnectionString
  }
  {
    name: 'redis-url'
    value: redisUrl
  }
  {
    name: 'redis-password'
    value: redisPrimaryKey
  }
]

var image = '${acr.properties.loginServer}/travelbuddy:${imageTag}'

// ---------- 1) THE API: the front door ----------
resource api 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: 'ca-${namePrefix}-api'
  location: location
  tags: tags
  identity: appIdentity
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: !internalOnly
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: appRegistries
      secrets: appSecrets
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'RATE_LIMIT_PER_MINUTE', value: string(rateLimitPerMinute) }
            { name: 'OTEL_SERVICE_NAME', value: 'travel-buddy-api' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      // The API keeps nothing in memory now, so it can have many copies.
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: [
          {
            name: 'http-load'
            http: {
              metadata: {
                concurrentRequests: string(apiConcurrentRequests)
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPull
  ]
}

// ---------- 2) THE WORKER: takes jobs from the queue and talks to the model ----------
resource worker 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: 'ca-${namePrefix}-worker'
  location: location
  tags: tags
  identity: appIdentity
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      // No ingress: nobody on the internet can reach the worker. It only reaches OUT (to Redis and the model).
      registries: appRegistries
      secrets: appSecrets
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: image
          // Same image as the API, but a different start command
          command: [ 'celery' ]
          args: [ '-A', 'celery_app:celery_app', 'worker', '--loglevel=info', '--concurrency=${workerConcurrency}' ]
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'RUNNING_IN_AZURE', value: 'true' }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'AZURE_OPENAI_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: modelDeployment }
            { name: 'OTEL_SERVICE_NAME', value: 'travel-buddy-worker' }
            { name: 'ENABLE_SENSITIVE_DATA', value: 'false' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection' }
          ]
        }
      ]
      // Scale on the LENGTH OF THE QUEUE: KEDA (built into Container Apps) looks at the Redis
      // list called "celery" every 30 seconds. About one new copy per queueLengthPerReplica waiting jobs.
      scale: {
        minReplicas: workerMinReplicas
        maxReplicas: workerMaxReplicas
        rules: [
          {
            name: 'celery-queue'
            custom: {
              type: 'redis'
              metadata: {
                address: '${redis.properties.hostName}:10000'
                listName: 'celery'
                listLength: string(queueLengthPerReplica)
                enableTLS: 'true'
              }
              auth: [
                {
                  secretRef: 'redis-password'
                  triggerParameter: 'password'
                }
              ]
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPull
    foundryAccess
  ]
}

output acrName string = acr.name
output appInsightsName string = appInsights.name
output identityClientId string = identity.properties.clientId
output redisHostName string = redis.properties.hostName
output apiUrl string = deployApp ? 'https://${api.properties.configuration.ingress.fqdn}' : 'Apps not deployed yet'
