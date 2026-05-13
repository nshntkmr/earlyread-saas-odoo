variable "env" {
  description = "Environment slug (dev, staging, prod)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the UAMIs."
  type        = string
}

variable "aks_oidc_issuer_url" {
  description = "AKS cluster's OIDC issuer URL (used to validate K8s tokens during federated auth)."
  type        = string
}

variable "kv_id" {
  description = "Key Vault resource ID — ESO gets Key Vault Secrets User on this."
  type        = string
}

variable "dns_zone_id" {
  description = "Public DNS zone resource ID — cert-manager gets DNS Zone Contributor on this for ACME DNS-01 challenges."
  type        = string
}

variable "tags" {
  description = "Tags applied to UAMIs."
  type        = map(string)
  default     = {}
}
