output "server_id" {
  value       = azurerm_postgresql_flexible_server.this.id
  description = "Resource ID of the PG Flex server."
}

output "server_name" {
  value       = azurerm_postgresql_flexible_server.this.name
  description = "Server name (e.g. earlyread-saas-dev-pg)."
}

output "fqdn" {
  value       = azurerm_postgresql_flexible_server.this.fqdn
  description = "Fully qualified DNS name. Resolves internally via the private DNS zone linked to the VNet."
}

output "database_name" {
  value       = azurerm_postgresql_flexible_server_database.this.name
  description = "Initial database name."
}

output "admin_username" {
  value       = var.admin_username
  description = "PG admin login. The password is stored in Key Vault as 'pg-admin-password'."
}

output "private_dns_zone_name" {
  value       = azurerm_private_dns_zone.pg.name
  description = "Private DNS zone hosting the PG server's A record."
}
