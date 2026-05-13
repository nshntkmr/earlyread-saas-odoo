# ─── M1 — Networking + DNS ───────────────────────────────────────────────────

output "resource_group_name" {
  value       = azurerm_resource_group.this.name
  description = "Name of the staging resource group."
}

output "vnet_name" {
  value       = module.network.vnet_name
  description = "Name of the staging VNet."
}

output "subnet_ids" {
  value       = module.network.subnet_ids
  description = "Map of subnet name → resource ID."
}

output "natgw_public_ip" {
  value       = module.network.natgw_public_ip
  description = "Fixed public IP for outbound from staging. Allow-list on ClickHouse Cloud + Anthropic."
}

output "dns_zone_name" {
  value       = module.dns.zone_name
  description = "Staging DNS zone name."
}

output "dns_zone_nameservers" {
  value       = module.dns.nameservers
  description = "MANUAL STEP: Add as NS records on host 'staging' under earlyread.ai at GoDaddy."
}

# ─── M2 — PostgreSQL ─────────────────────────────────────────────────────────

output "pg_server_name" {
  value       = module.postgresql.server_name
  description = "Staging PG Flex server name."
}

output "pg_fqdn" {
  value       = module.postgresql.fqdn
  description = "Staging PG server FQDN. Resolves to a 10.20.4.x private IP from inside the VNet."
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
  description = "Secrets seeded in this Key Vault."
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
  description = "Staging AKS cluster name."
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
  description = "App Gateway public IP. Wildcard *.staging.earlyread.ai DNS record targets this."
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
