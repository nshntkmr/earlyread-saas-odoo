output "storage_account_id" {
  value       = azurerm_storage_account.this.id
  description = "Resource ID of the storage account."
}

output "storage_account_name" {
  value       = azurerm_storage_account.this.name
  description = "Storage account name."
}

output "share_name" {
  value       = azurerm_storage_share.filestore.name
  description = "Azure Files share name (always 'odoo-filestore')."
}

output "share_url" {
  value       = azurerm_storage_share.filestore.url
  description = "Public URL of the share (resolves to private IP from inside the VNet)."
}

output "private_endpoint_id" {
  value       = azurerm_private_endpoint.files.id
  description = "Resource ID of the Files private endpoint."
}

output "private_dns_zone_id" {
  value       = azurerm_private_dns_zone.files.id
  description = "Resource ID of the privatelink.file.core.windows.net zone."
}
