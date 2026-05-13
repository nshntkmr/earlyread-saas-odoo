output "eso_uami_id" {
  value       = azurerm_user_assigned_identity.eso.id
  description = "ESO UAMI resource ID."
}

output "eso_uami_client_id" {
  value       = azurerm_user_assigned_identity.eso.client_id
  description = "ESO UAMI client_id. Goes into the K8s ServiceAccount annotation 'azure.workload.identity/client-id'."
}

output "eso_uami_principal_id" {
  value       = azurerm_user_assigned_identity.eso.principal_id
  description = "ESO UAMI principal (object) ID. Used for further role assignments if needed."
}

output "cert_manager_uami_id" {
  value       = azurerm_user_assigned_identity.cert_manager.id
  description = "cert-manager UAMI resource ID."
}

output "cert_manager_uami_client_id" {
  value       = azurerm_user_assigned_identity.cert_manager.client_id
  description = "cert-manager UAMI client_id. Used by cert-manager's azureDNS solver config + K8s SA annotation."
}

output "cert_manager_uami_principal_id" {
  value       = azurerm_user_assigned_identity.cert_manager.principal_id
  description = "cert-manager UAMI principal (object) ID."
}
