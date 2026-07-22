// DB migration Container Apps Job (ADP-fnv.7).
//
// Manual-trigger, one-off job running `alembic upgrade head` against the
// same API image the app itself runs (adp/store/migrations/env.py reads
// ADP_DATABASE_URL and rewrites postgresql+asyncpg:// -> +psycopg2:// for
// Alembic's sync driver, so the same Key Vault secret the API app uses
// works here unmodified). Matches RUNBOOK.md's existing
// `docker compose run --rm api alembic upgrade head` pattern rather than
// running migrations on container boot.

@description('Azure region.')
param location string

@description('Container Apps environment resource ID.')
param environmentId string

@description('User-assigned managed identity resource ID.')
param identityId string

@description('ACR login server.')
param acrLoginServer string

@description('Tag of the API image -- the same image the API app runs; only the command differs.')
param apiImageTag string

@description('Key Vault URI.')
param keyVaultUri string

resource migrationJob 'Microsoft.App/jobs@2025-01-01' = {
  name: 'adp-migrate'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
      secrets: [
        {
          name: 'postgres-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/postgres-connection-string'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: '${acrLoginServer}/adp-api:${apiImageTag}'
          command: ['alembic']
          args: ['upgrade', 'head']
          env: [
            { name: 'ADP_DATABASE_URL', secretRef: 'postgres-connection-string' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}

output jobName string = migrationJob.name
