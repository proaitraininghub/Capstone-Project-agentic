// Gives the Travel Buddy identity permission to use the existing Foundry account.
// This is a separate file (a "module") because the Foundry account may live in a
// different resource group than the app.
targetScope = 'resourceGroup'

@description('Name of the existing Foundry (AI Services) account')
param foundryAccountName string

@description('Object (principal) ID of the app identity')
param principalId string

@description('Resource ID of the app identity (only used to make the assignment name unique)')
param identityId string

// Built-in role "Azure AI User". Check the ID with: az role definition list --name "Azure AI User"
var azureAiUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource assignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identityId, azureAiUserRoleId)
  scope: foundry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUserRoleId)
  }
}
