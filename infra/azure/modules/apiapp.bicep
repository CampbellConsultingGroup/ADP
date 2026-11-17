// API container app (ADP-fnv.6) -- the one component the public actually
// reaches. External ingress; managed identity (adp-identity) already holds
// AcrPull and Key Vault Secrets User (both granted in modules/keyvault.bicep).
// /health is exempt from auth (adp.auth.middleware._EXEMPT_PATHS) and wired
// as the liveness probe.
//
// Ingress is IP-restricted when allowedIpRanges is non-empty: once one Allow
// rule exists, Container Apps denies all other traffic. deploy.sh supplies
// the list from infra/azure/.secrets/allowed-ips and refuses to deploy with
// an empty list unless explicitly told to, so a redeploy can't silently
// expose the app. The template enforces the same rule itself: an empty list
// without allowPublicIngress=true denies all traffic (ADP-blp.64).
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

@description('Keycloak container app FQDN (internal-only) from modules/keycloak.bicep -- adp-api proxies /auth/* to this.')
param keycloakFqdn string

@description('Public base URL the browser reaches Keycloak through (ADP-cm9): https://<this-api-fqdn>/auth. Keycloak is configured (KC_HOSTNAME) to believe this is its own address, so its issuer claim and generated URLs already match this exactly.')
param keycloakPublicBaseUrl string

@description('Keycloak realm name.')
param keycloakRealm string = 'ADPRealm'

@description('Keycloak client ID -- must match the client baked into the realm export (infra/keycloak/adp-realm.json).')
param keycloakClientId string = 'adp-frontend'

@description('Port the API listens on inside the container (matches ADP_PORT).')
param apiPort int = 8001

@description('Client IP ranges allowed to reach the API, as objects { cidr: string, description: string }.')
param allowedIpRanges array

@description('Deploy with NO IP restriction. Must be set on purpose: an empty allowedIpRanges without it closes the ingress to everyone instead of opening it (ADP-blp.64).')
param allowPublicIngress bool = false

// One Allow rule makes Container Apps deny everything else. With no ranges and no explicit
// "public" flag, a single Deny-all rule is used, so a forgotten or emptied list fails closed.
var allowRules = [for (range, i) in allowedIpRanges: {
  name: 'allowed-ip-${i + 1}'
  description: range.description
  ipAddressRange: range.cidr
  action: 'Allow'
}]
var denyAllRule = [
  {
    name: 'deny-all'
    description: 'No allowed ranges were supplied and allowPublicIngress is false'
    ipAddressRange: '0.0.0.0/0'
    action: 'Deny'
  }
]

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
        ipSecurityRestrictions: empty(allowedIpRanges) && !allowPublicIngress ? denyAllRule : allowRules
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
            // Public issuer -- must exactly match the "iss" claim Keycloak
            // emits (KC_HOSTNAME points Keycloak at this same public URL),
            // since adp/auth/tokens.py validates iss as an exact string match.
            { name: 'ADP_KEYCLOAK_ISSUER', value: '${keycloakPublicBaseUrl}/realms/${keycloakRealm}' }
            { name: 'ADP_KEYCLOAK_CLIENT_ID', value: keycloakClientId }
            // Internal target for the /auth/* reverse proxy (adp.api.routers.auth_proxy,
            // ADP-cm9) -- Keycloak has internal-only ingress, unreachable by a
            // real browser directly.
            { name: 'ADP_KEYCLOAK_INTERNAL_URL', value: 'https://${keycloakFqdn}' }
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
