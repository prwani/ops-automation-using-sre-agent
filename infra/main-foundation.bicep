@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name: dev, staging, or prod')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Project prefix for resource naming')
param projectPrefix string = 'opsauto'

@description('Azure subscription ID for Arc-enrolled servers')
param arcSubscriptionId string = subscription().subscriptionId

var suffix = '${projectPrefix}-${environment}'
var tags = {
  project: 'ops-automation-using-sre-agent'
  environment: environment
  managedBy: 'bicep'
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 90
    features: {
      searchVersion: 1
    }
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'ai-${suffix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// Storage Account (Azure Functions requirement)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${replace(suffix, '-', '')}fn'
  location: location
  kind: 'StorageV2'
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${suffix}-2'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Cosmos DB Account (serverless)
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: 'cosmos-${suffix}'
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    enableAutomaticFailover: false
    publicNetworkAccess: 'Enabled'
    minimalTlsVersion: 'Tls12'
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: 'ops-automation'
  properties: {
    resource: {
      id: 'ops-automation'
    }
  }
}

resource runsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: cosmosDatabase
  name: 'runs'
  properties: {
    resource: {
      id: 'runs'
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
        excludedPaths: [{ path: '/_etag/?' }]
      }
    }
  }
}

resource feedbackContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: cosmosDatabase
  name: 'feedback'
  properties: {
    resource: {
      id: 'feedback'
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
    }
  }
}

resource memoriesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: cosmosDatabase
  name: 'memories'
  properties: {
    resource: {
      id: 'memories'
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
    }
  }
}

// Outputs
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output logAnalyticsWorkspaceId string = logAnalytics.properties.customerId
output keyVaultUri string = keyVault.properties.vaultUri
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output storageAccountName string = storageAccount.name
