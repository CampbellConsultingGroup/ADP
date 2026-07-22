// Azure Database for PostgreSQL Flexible Server (ADP-fnv.2).
//
// Private/VNet-integrated (no public network access at all) rather than
// public+firewall -- the delegated subnet + private DNS zone are provisioned
// by modules/network.bicep and passed in.
//
// pgvector is allow-listed via the azure.extensions server parameter
// (a Microsoft.DBforPostgreSQL/flexibleServers/configurations child
// resource); the actual `CREATE EXTENSION vector` statement is run by the
// app's own Alembic migration 002 (src/adp/store/migrations/versions/
// 002_knowledge_schema.py) when the migration job (ADP-fnv.7) runs --
// no separate SQL-execution step needed here.
//
// Uses a single admin login for both server administration and the app's
// own connection (ADP_DATABASE_URL), matching docker-compose.yml's existing
// single-user (adp_user) precedent -- a separate low-privilege app role
// would need its own SQL execution step this deployment doesn't otherwise
// require, so it's deliberately not added to keep this the simplest
// configuration consistent with what's already running locally.

@description('Azure region.')
param location string

@description('Flexible Server name. Must be globally unique.')
param serverName string = 'adp-postgres'

@description('Postgres major version.')
param postgresVersion string = '16'

@description('Burstable SKU -- cheapest tier, sufficient for a single-environment deployment.')
param skuName string = 'Standard_B1ms'

@description('Storage size in GB (32 is the minimum tier).')
param storageSizeGB int = 32

@description('Admin username.')
param adminUsername string = 'adp_admin'

@secure()
@description('Admin password. Supplied at deploy time -- never hardcoded/committed.')
param adminPassword string

@description('Delegated subnet resource ID from modules/network.bicep.')
param delegatedSubnetId string

@description('Private DNS zone resource ID from modules/network.bicep.')
param privateDnsZoneId string

@description('Name of the application database to create.')
param databaseName string = 'adp'

@description('Name of the Keycloak database to create (ADP-fnv.5) -- its own DB on the same server, not sharing the app schema.')
param keycloakDatabaseName string = 'keycloak'

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: serverName
  location: location
  sku: {
    name: skuName
    tier: 'Burstable'
  }
  properties: {
    version: postgresVersion
    administratorLogin: adminUsername
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: storageSizeGB
    }
    network: {
      delegatedSubnetResourceId: delegatedSubnetId
      privateDnsZoneArmResourceId: privateDnsZoneId
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// Extension allow-list (azure.extensions server parameter). Azure Flexible
// Server blocks `CREATE EXTENSION` for anything not listed here, regardless
// of DB privileges. The app's Alembic migrations create exactly two:
//   - vector   (pgvector; migrations 002 + 011, the search/knowledge index)
//   - pgcrypto (migration 004, llm_reasoning_log's gen_random_uuid/digest)
// Both MUST be listed or `alembic upgrade head` fails partway (migration
// 004 hit "extension pgcrypto is not allow-listed" on the first Azure run).
resource azureExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-08-01' = {
  parent: server
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR,PGCRYPTO'
    source: 'user-override'
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: server
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource keycloakDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: server
  name: keycloakDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

output serverName string = server.name
output serverFqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name
output keycloakDatabaseName string = keycloakDatabase.name
// adp expects postgresql+asyncpg://user:password@host:5432/db -- password
// is deliberately NOT interpolated into this output (it's @secure() and
// this output isn't marked secure); the deploy script assembles the full
// connection string from this plus the password it already holds.
output connectionStringTemplate string = 'postgresql+asyncpg://${adminUsername}:<PASSWORD>@${server.properties.fullyQualifiedDomainName}:5432/${database.name}'
