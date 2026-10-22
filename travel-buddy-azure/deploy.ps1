<#
 deploy.ps1  --  Deploy Travel Buddy (API + Celery worker + Redis) to Azure Container Apps (PowerShell)

 Run from the travel-buddy-azure folder. You need: Azure CLI (az) and az login.
 You do NOT need Docker on your laptop; the image is built inside Azure.

 Example:
   .\deploy.ps1 -ResourceGroup rg-travelbuddy -Location eastus `
       -FoundryAccountName my-foundry-account `
       -FoundryProjectEndpoint "https://my-foundry-account.services.ai.azure.com/api/projects/my-project"
#>
param(
    [Parameter(Mandatory = $true)][string]$ResourceGroup,
    [Parameter(Mandatory = $true)][string]$Location,
    [Parameter(Mandatory = $true)][string]$FoundryAccountName,
    [Parameter(Mandatory = $true)][string]$FoundryProjectEndpoint,
    [string]$FoundryResourceGroup = "",
    [string]$ModelDeployment = "gpt-4.1-mini",
    [string]$ImageTag = "v1",
    [string]$InfrastructureSubnetId = "",
    [string]$RedisSku = "Balanced_B1",
    [int]$ApiMinReplicas = 2,
    [int]$ApiMaxReplicas = 10,
    [int]$WorkerMinReplicas = 1,
    [int]$WorkerMaxReplicas = 10,
    [int]$RateLimitPerMinute = 10,
    [switch]$InternalOnly
)

$ErrorActionPreference = "Stop"
if (-not $FoundryResourceGroup) { $FoundryResourceGroup = $ResourceGroup }
# Azure needs these services switched on in your subscription (safe to run again)
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.Cache --wait
$internal = if ($InternalOnly) { "true" } else { "false" }

Write-Host "1/4 Creating the resource group..."
az group create --name $ResourceGroup --location $Location | Out-Null

Write-Host "2/4 Creating monitoring, Redis, registry, identity and environment (no apps yet). Redis can take 10 to 20 minutes..."
az deployment group create --name main --resource-group $ResourceGroup `
    --template-file infra/main.bicep `
    --parameters deployApp=false foundryAccountName=$FoundryAccountName `
                 foundryResourceGroup=$FoundryResourceGroup `
                 foundryProjectEndpoint=$FoundryProjectEndpoint `
                 modelDeployment=$ModelDeployment imageTag=$ImageTag `
                 infrastructureSubnetId=$InfrastructureSubnetId internalOnly=$internal `
                 redisSku=$RedisSku rateLimitPerMinute=$RateLimitPerMinute `
                 apiMinReplicas=$ApiMinReplicas apiMaxReplicas=$ApiMaxReplicas `
                 workerMinReplicas=$WorkerMinReplicas workerMaxReplicas=$WorkerMaxReplicas | Out-Null

$acrName = az deployment group show --name main --resource-group $ResourceGroup --query properties.outputs.acrName.value -o tsv

Write-Host "3/4 Building the image inside Azure Container Registry ($acrName)..."
az acr build --registry $acrName --image "travelbuddy:$ImageTag" --file Dockerfile .

Write-Host "4/4 Creating the API and the worker..."
az deployment group create --name main --resource-group $ResourceGroup `
    --template-file infra/main.bicep `
    --parameters deployApp=true foundryAccountName=$FoundryAccountName `
                 foundryResourceGroup=$FoundryResourceGroup `
                 foundryProjectEndpoint=$FoundryProjectEndpoint `
                 modelDeployment=$ModelDeployment imageTag=$ImageTag `
                 infrastructureSubnetId=$InfrastructureSubnetId internalOnly=$internal `
                 redisSku=$RedisSku rateLimitPerMinute=$RateLimitPerMinute `
                 apiMinReplicas=$ApiMinReplicas apiMaxReplicas=$ApiMaxReplicas `
                 workerMinReplicas=$WorkerMinReplicas workerMaxReplicas=$WorkerMaxReplicas | Out-Null

$url = az deployment group show --name main --resource-group $ResourceGroup --query properties.outputs.apiUrl.value -o tsv
Write-Host ""
Write-Host "Done. Your API: $url   (the worker has no public address, by design)"
Write-Host "Test it:  python smoke_test.py $url"
