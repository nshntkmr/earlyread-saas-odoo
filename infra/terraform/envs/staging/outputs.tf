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
