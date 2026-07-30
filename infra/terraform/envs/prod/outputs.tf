# ─── M1 — Networking + DNS ───────────────────────────────────────────────────

output "resource_group_name" {
  value       = azurerm_resource_group.this.name
  description = "Name of the prod resource group."
}

output "vnet_name" {
  value       = module.network.vnet_name
  description = "Name of the prod VNet."
}

output "subnet_ids" {
  value       = module.network.subnet_ids
  description = "Map of subnet name → resource ID."
}

output "natgw_public_ip" {
  value       = module.network.natgw_public_ip
  description = "Fixed public IP for outbound from prod. Allow-list on ClickHouse Cloud, Snowflake, and Anthropic."
}

output "dns_zone_name" {
  value       = data.azurerm_dns_zone.apex.name
  description = "Apex DNS zone serving tenant subdomains. Read-only — prod does not own this zone."
}

# The services layer needs the zone's OWN resource group for cert-manager's
# DNS-01 solver. It is NOT `resource_group_name` above (that is prod's RG) —
# the apex zone lives outside this state. Keeping them as separate outputs is
# what stops the solver from writing TXT challenges into the wrong RG.
output "dns_zone_resource_group_name" {
  value       = data.azurerm_dns_zone.apex.resource_group_name
  description = "Resource group holding the apex DNS zone (NOT prod's resource group)."
}

# NOTE: no `dns_zone_nameservers` output. dev/staging emit one because they
# CREATE a child zone that must then be delegated from the apex. Prod consumes
# the apex zone itself, so there is no delegation step and no nameservers to
# publish.

# ─── M2 — PostgreSQL ─────────────────────────────────────────────────────────

output "pg_server_name" {
  value       = module.postgresql.server_name
  description = "Prod PG Flex server name."
}

output "pg_fqdn" {
  value       = module.postgresql.fqdn
  description = "Prod PG server FQDN. Resolves to a 10.30.4.x private IP from inside the VNet."
}

output "pg_database_name" {
  value       = module.postgresql.database_name
  description = "Initial database name inside PG."
}

output "pg_admin_username" {
  value       = module.postgresql.admin_username
  description = "PG admin login. Password is in Key Vault under 'pg-admin-password'."
}

# ─── M2 — Key Vault ──────────────────────────────────────────────────────────

output "kv_name" {
  value       = module.keyvault.name
  description = "Key Vault name."
}

output "kv_uri" {
  value       = module.keyvault.uri
  description = "Key Vault HTTPS endpoint."
}

output "kv_secret_names" {
  value       = module.keyvault.secret_names
  description = "Secrets seeded in this Key Vault. REPLACE_ME values must be set before serving traffic."
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

output "filestore_storage_account_name" {
  value       = module.filestore.storage_account_name
  description = "Storage account hosting the Azure Files share."
}

output "filestore_share_url" {
  value       = module.filestore.share_url
  description = "Azure Files share URL."
}

# ─── M3 — AKS + App Gateway + Workload Identity ─────────────────────────────

output "aks_cluster_name" {
  value       = module.aks.name
  description = "Prod AKS cluster name."
}

output "aks_oidc_issuer_url" {
  value       = module.aks.oidc_issuer_url
  description = "AKS cluster OIDC issuer URL."
}

output "appgw_name" {
  value       = module.appgw.name
  description = "App Gateway name."
}

output "appgw_public_ip" {
  value       = module.appgw.public_ip
  description = "App Gateway public IP. The *.earlyread.ai wildcard A record targets this."
}

output "appgw_public_ip_fqdn" {
  value       = module.appgw.public_ip_fqdn
  description = "Azure-assigned cloudapp.azure.com FQDN for the App Gateway public IP."
}

output "eso_uami_client_id" {
  value       = module.workload_identity.eso_uami_client_id
  description = "client_id of the ESO UAMI."
}

output "cert_manager_uami_client_id" {
  value       = module.workload_identity.cert_manager_uami_client_id
  description = "client_id of the cert-manager UAMI."
}
