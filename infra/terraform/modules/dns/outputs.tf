output "zone_name" {
  value       = azurerm_dns_zone.this.name
  description = "Zone name (e.g. dev.earlyread.ai)."
}

output "zone_id" {
  value       = azurerm_dns_zone.this.id
  description = "Resource ID of the zone."
}

output "nameservers" {
  value       = azurerm_dns_zone.this.name_servers
  description = "Azure-assigned nameservers. Copy these into GoDaddy as NS records on the subdomain to delegate."
}
