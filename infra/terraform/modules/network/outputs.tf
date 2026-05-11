output "vnet_id" {
  value       = azurerm_virtual_network.this.id
  description = "Resource ID of the VNet."
}

output "vnet_name" {
  value       = azurerm_virtual_network.this.name
  description = "Name of the VNet."
}

output "subnet_ids" {
  value = {
    aks   = azurerm_subnet.aks.id
    pg    = azurerm_subnet.pg.id
    appgw = azurerm_subnet.appgw.id
    pe    = azurerm_subnet.pe.id
  }
  description = "Map of subnet purpose → subnet resource ID. Consumed by AKS (M3), PG (M2), AppGw (M3), PE creation (M2+)."
}

output "natgw_id" {
  value       = azurerm_nat_gateway.this.id
  description = "Resource ID of the NAT Gateway."
}

output "natgw_public_ip" {
  value       = azurerm_public_ip.natgw.ip_address
  description = "Fixed public IP for outbound traffic from AKS pods. Allow-list this on ClickHouse Cloud and Anthropic."
}
