output "id" {
  value       = azurerm_kubernetes_cluster.this.id
  description = "AKS cluster resource ID."
}

output "name" {
  value       = azurerm_kubernetes_cluster.this.name
  description = "AKS cluster name."
}

output "oidc_issuer_url" {
  value       = azurerm_kubernetes_cluster.this.oidc_issuer_url
  description = "Cluster's OIDC issuer URL — used by federated identity credentials in the workload_identity module."
}

output "kubelet_identity_object_id" {
  value       = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  description = "Kubelet identity's object ID. Has AcrPull on the shared ACR."
}

output "agic_identity_object_id" {
  value       = azurerm_kubernetes_cluster.this.ingress_application_gateway[0].ingress_application_gateway_identity[0].object_id
  description = "AGIC's managed identity object ID."
}

output "node_resource_group" {
  value       = azurerm_kubernetes_cluster.this.node_resource_group
  description = "MC_* RG that AKS creates for node/load-balancer resources."
}
