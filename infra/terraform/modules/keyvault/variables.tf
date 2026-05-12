variable "name" {
  description = "Key Vault name (3-24 chars, alphanumeric + hyphens, globally unique). E.g. earlyread-saas-dev-kv."
  type        = string

  validation {
    condition     = length(var.name) >= 3 && length(var.name) <= 24 && can(regex("^[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]$", var.name))
    error_message = "name must be 3-24 chars, start with letter, end with letter or digit, alphanumeric + hyphens only."
  }
}

variable "env" {
  description = "Environment slug (used in PE name and vnet-link name)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the KV + private DNS zone + private endpoint."
  type        = string
}

variable "vnet_id" {
  description = "VNet resource ID — for the private-DNS-zone vnet link."
  type        = string
}

variable "pe_subnet_id" {
  description = "Subnet ID for the Private Endpoint (the 'pe' subnet from M1)."
  type        = string
}

variable "allowed_ips" {
  description = "Public IPs allowed through the KV firewall (in addition to PE + AzureServices bypass). E.g. your laptop IP."
  type        = list(string)
  default     = []
}

variable "allowed_subnet_ids" {
  description = "VNet subnets allowed direct (non-PE) access to KV. Typically the AKS subnet for M3+ workloads."
  type        = list(string)
  default     = []
}

variable "initial_secrets" {
  description = "Map of secret_name → initial_value. Use 'REPLACE_ME' for placeholders the user fills later. All values get lifecycle.ignore_changes."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
