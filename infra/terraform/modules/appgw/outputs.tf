output "id" {
  value       = azurerm_application_gateway.this.id
  description = "App Gateway resource ID. Consumed by AKS module's AGIC add-on config + AGIC role assignment."
}

output "name" {
  value       = azurerm_application_gateway.this.name
  description = "App Gateway name."
}

output "public_ip" {
  value       = azurerm_public_ip.this.ip_address
  description = "App Gateway public IP. Wildcard A record targets this address."
}

output "public_ip_fqdn" {
  value       = azurerm_public_ip.this.fqdn
  description = "Azure-assigned FQDN for the public IP (e.g. earlyread-saas-dev-appgw.eastus2.cloudapp.azure.com). Useful for cert-bypass testing."
}
