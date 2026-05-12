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
  description = "Map of subnet name → resource ID. Consumed by M2 (PG), M3 (AKS, AppGw, PEs)."
}

output "natgw_public_ip" {
  value       = module.network.natgw_public_ip
  description = "Fixed public IP for outbound from staging. Allow-list this on ClickHouse Cloud + Anthropic."
}

output "dns_zone_name" {
  value       = module.dns.zone_name
  description = "Staging DNS zone name."
}

output "dns_zone_nameservers" {
  value       = module.dns.nameservers
  description = "MANUAL STEP: Add these as NS records on host 'staging' under earlyread.ai at GoDaddy."
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
  description = "Secrets seeded in this Key Vault. Replace any 'REPLACE_ME' placeholders before M5."
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

output "filestore_storage_account_name" {
  value       = module.filestore.storage_account_name
  description = "Storage account hosting the Azure Files share."
}

output "filestore_share_url" {
  value       = module.filestore.share_url
  description = "Azure Files share URL. Mounted at /var/lib/odoo in M5 AKS pods."
}
