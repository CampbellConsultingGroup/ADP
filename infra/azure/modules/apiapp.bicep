// API container app (ADP-fnv.6) -- the one component the public actually
// reaches. External ingress; managed identity (adp-identity) already holds
// AcrPull (granted at resource-group scope in modules/keycloak.bicep, the
// first consumer -- covers this app too, no re-grant needed) and Key Vault
// Secrets User (modules/keyvault.bicep). /health is exempt from auth
// (adp.auth.middleware._EXEMPT_PATHS) and wired as the liveness probe.
//
// minReplicas=0 (unlike Keycloak's minReplicas=1): a FastAPI/uvicorn cold
// start is seconds, not the tens of seconds Keycloak's JVM needs, so
// scale-to-zero when idle is a real cost saving here without materially
// hurting responsiveness -- this app costs ~$0 while nothing is using it.

@description('Azure region.')
param location string

@description('Container Apps environment resource ID.')
param environmentId string

@description('User-assigned managed identity resource ID.')
param identityId string

@description('ACR login server.')
param acrLoginServer string

@description('Tag of the API image (Dockerfile at repo root), already built+pushed to ACR by deploy.sh before this runs.')
param apiImageTag string

@description('Key Vault URI (used to build secret references).')
param keyVaultUri string

@description('Keycloak container app FQDN (internal-only) from modules/keycloak.bicep.')
param keycloakFqdn string

@description('Keycloak realm name.')
param keycloakRealm string = 'ADPRealm'

@description('Keycloak client ID -- must match the client baked into the realm export (infra/keycloak/adp-realm.json).')
param keycloakClientId string = 'adp-frontend'

@description('Port the API listens on inside the container (matches ADP_PORT).')
param apiPort int = 8001

resource apiApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'adp-api'
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
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: apiPort
        transport: 'auto'
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
        {
          name: 'adp-llm-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/adp-llm-api-key'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/adp-api:${apiImageTag}'
          env: [
            { name: 'ADP_PORT', value: string(apiPort) }
            { name: 'ADP_WORKERS', value: '2' }
            { name: 'ADP_MAX_DESIGNS', value: '1000' }
            { name: 'ADP_AUTH_ENABLED', value: 'true' }
            { name: 'ADP_KEYCLOAK_ISSUER', value: 'https://${keycloakFqdn}/realms/${keycloakRealm}' }
            { name: 'ADP_KEYCLOAK_CLIENT_ID', value: keycloakClientId }
            { name: 'ADP_DATABASE_URL', secretRef: 'postgres-connection-string' }
            { name: 'ADP_LLM_API_KEY', secretRef: 'adp-llm-api-key' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: apiPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: apiPort
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output fqdn string = apiApp.properties.configuration.ingress.fqdn
output name string = apiApp.name
