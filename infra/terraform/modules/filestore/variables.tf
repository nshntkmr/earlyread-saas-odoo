variable "name" {
  description = "Storage account name (3-24 chars, lowercase alphanumeric only, globally unique). E.g. earlyreaddevfseread."
  type        = string

  validation {
    condition     = length(var.name) >= 3 && length(var.name) <= 24 && can(regex("^[a-z0-9]+$", var.name))
    error_message = "name must be 3-24 chars, lowercase alphanumeric only (no hyphens)."
  }
}

variable "env" {
  description = "Environment slug (used in PE and vnet-link names)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the storage account + private DNS zone + private endpoint."
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
  description = "Public IPs allowed through the storage account firewall (in addition to PE + AzureServices bypass)."
  type        = list(string)
  default     = []
}

variable "allowed_subnet_ids" {
  description = "VNet subnets allowed direct (non-PE) access to the storage account. Typically the AKS subnet for M3+."
  type        = list(string)
  default     = []
}

variable "quota_gb" {
  description = "Azure Files share quota in GB. Premium tier minimum is 100 GB."
  type        = number
  default     = 100

  validation {
    condition     = var.quota_gb >= 100
    error_message = "Premium Azure Files requires at least 100 GB."
  }
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
