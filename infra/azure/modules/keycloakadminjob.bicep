// Keycloak admin-REST-API patch job (ADP-cm9).
//
// Manual-trigger, one-off job that runs `python -m adp.ops.keycloak_admin_patch`
// (same API image the app itself runs) from inside the Container Apps
// environment's VNet, since adp-keycloak has internal-only ingress and isn't
// reachable from outside it. Exists because Keycloak's `--import-realm` uses
// IGNORE_EXISTING -- once a realm is provisioned, redeploying the realm-JSON
// image is a no-op; only the admin REST API can change an already-live realm.
//
// Reused across invocations: the container's command/args are fixed, but
// KC_PATCH_TARGET / KC_PATCH_CLIENT_ID / KC_PATCH_BODY are overridden per call
// via `az containerapp job start --env-vars ...` rather than baked in here --
// this is what ADP-odp's MFA realm patch reuses unmodified.

@description('Azure region.')
param location string

@description('Container Apps environment resource ID.')
param environmentId string

@description('User-assigned managed identity resource ID.')
param identityId string

@description('ACR login server.')
param acrLoginServer string

@description('Tag of the API image -- same image the API app runs; only the command differs.')
param apiImageTag string

@description('Key Vault URI.')
param keyVaultUri string

@description('Internal Keycloak FQDN (adp-keycloak.internal...).')
param keycloakFqdn string

@description('Realm name.')
param keycloakRealm string

resource keycloakAdminJob 'Microsoft.App/jobs@2025-01-01' = {
  name: 'adp-keycloak-admin'
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
      replicaTimeout: 300
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
          name: 'keycloak-admin-password'
          keyVaultUrl: '${keyVaultUri}secrets/keycloak-admin-password'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'keycloak-admin'
          image: '${acrLoginServer}/adp-api:${apiImageTag}'
          command: ['python3']
          args: ['-m', 'adp.ops.keycloak_admin_patch']
          env: [
            // Keycloak serves everything under /auth (--http-relative-path=/auth,
            // see modules/keycloak.bicep) -- this must match, or the admin
            // token/realm endpoints 404 (hit exactly this bug once already).
            { name: 'KEYCLOAK_URL', value: 'https://${keycloakFqdn}/auth' }
            { name: 'KEYCLOAK_REALM', value: keycloakRealm }
            { name: 'KEYCLOAK_ADMIN_USERNAME', value: 'admin' }
            { name: 'KEYCLOAK_ADMIN_PASSWORD', secretRef: 'keycloak-admin-password' }
            // Placeholder default -- always overridden per-invocation via
            // `az containerapp job start --env-vars ...`.
            { name: 'KC_PATCH_TARGET', value: 'client' }
            { name: 'KC_PATCH_CLIENT_ID', value: 'adp-frontend' }
            { name: 'KC_PATCH_BODY', value: '{}' }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
    }
  }
}

output jobName string = keycloakAdminJob.name
