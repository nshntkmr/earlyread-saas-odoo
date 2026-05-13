output "resource_group_name" {
  value       = azurerm_resource_group.shared.name
  description = "Shared resource group name."
}

output "acr_name" {
  value       = module.acr.name
  description = "ACR name. Both dev and staging reference this via data source."
}

output "acr_id" {
  value       = module.acr.id
  description = "ACR resource ID."
}

output "acr_login_server" {
  value       = module.acr.login_server
  description = "ACR login server (use this in `docker push` and pod image references)."
}
