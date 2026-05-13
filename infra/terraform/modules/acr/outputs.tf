output "id" {
  value       = azurerm_container_registry.this.id
  description = "ACR resource ID. Consumed by AKS module for the AcrPull role assignment."
}

output "name" {
  value       = azurerm_container_registry.this.name
  description = "ACR name."
}

output "login_server" {
  value       = azurerm_container_registry.this.login_server
  description = "Login server (e.g. earlyreadsaasacreread.azurecr.io). Use this in `docker push` and pod image references."
}
