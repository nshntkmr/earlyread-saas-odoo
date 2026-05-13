output "cluster_secret_store_name" {
  value       = "${var.env}-kv-store"
  description = "ClusterSecretStore name. M5 ExternalSecret resources reference this in spec.secretStoreRef.name."
}

output "cert_manager_namespace" {
  value       = "cert-manager"
  description = "Namespace cert-manager runs in."
}

output "external_secrets_namespace" {
  value       = "external-secrets-system"
  description = "Namespace ESO runs in."
}
