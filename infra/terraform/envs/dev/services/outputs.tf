output "cluster_secret_store_name" {
  value       = module.cluster_services.cluster_secret_store_name
  description = "ClusterSecretStore name. M5 ExternalSecret resources reference this."
}

output "cert_manager_namespace" {
  value       = module.cluster_services.cert_manager_namespace
  description = "Namespace cert-manager runs in."
}

output "external_secrets_namespace" {
  value       = module.cluster_services.external_secrets_namespace
  description = "Namespace ESO runs in."
}
