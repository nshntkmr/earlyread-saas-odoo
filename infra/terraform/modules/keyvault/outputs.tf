output "id" {
  value       = azurerm_key_vault.this.id
  description = "Resource ID of the Key Vault."
}

output "name" {
  value       = azurerm_key_vault.this.name
  description = "Key Vault name."
}

output "uri" {
  value       = azurerm_key_vault.this.vault_uri
  description = "HTTPS URI base for the vault (e.g. https://earlyread-saas-dev-kv.vault.azure.net/)."
}

output "private_endpoint_id" {
  value       = azurerm_private_endpoint.kv.id
  description = "Resource ID of the KV private endpoint."
}

output "private_dns_zone_id" {
  value       = azurerm_private_dns_zone.kv.id
  description = "Resource ID of the privatelink.vaultcore.azure.net zone."
}

output "secret_names" {
  value       = keys(azurerm_key_vault_secret.secrets)
  description = "List of secret names provisioned in this vault."
}
