variable "env" {
  description = "Environment slug (dev, staging, prod)."
  type        = string
}

variable "subscription_id" {
  description = "Azure subscription ID — passed into the Azure DNS solver config."
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID — passed into the ClusterSecretStore config."
  type        = string
}

# ─── cert-manager wiring ────────────────────────────────────────────────────

variable "cert_manager_chart_version" {
  description = "cert-manager Helm chart version. Pin to a known-good release."
  type        = string
  default     = "v1.16.1"
}

variable "cert_manager_uami_client_id" {
  description = "client_id of the UAMI federated to cert-manager's K8s SA. From workload_identity module."
  type        = string
}

variable "acme_email" {
  description = "Email address for Let's Encrypt registration. Used for renewal-warning notifications."
  type        = string
}

variable "dns_zone_name" {
  description = "Public DNS zone name (e.g. dev.earlyread.ai). cert-manager writes ACME challenge TXT records here."
  type        = string
}

variable "dns_zone_resource_group_name" {
  description = "Resource group that holds the public DNS zone."
  type        = string
}

# ─── ESO wiring ──────────────────────────────────────────────────────────────

variable "eso_chart_version" {
  description = "External Secrets Operator Helm chart version."
  type        = string
  default     = "0.10.7"
}

variable "eso_uami_client_id" {
  description = "client_id of the UAMI federated to ESO's K8s SA. From workload_identity module."
  type        = string
}

variable "kv_uri" {
  description = "Key Vault URI (e.g. https://earlyread-saas-dev-kv.vault.azure.net/). Used by ClusterSecretStore."
  type        = string
}
