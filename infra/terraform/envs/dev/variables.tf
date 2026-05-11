variable "subscription_id" {
  description = "Azure subscription ID to deploy into."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.subscription_id))
    error_message = "subscription_id must be a valid GUID."
  }
}

variable "env" {
  description = "Environment slug. DO NOT change for this directory."
  type        = string
  default     = "dev"

  validation {
    condition     = var.env == "dev"
    error_message = "This directory is hardcoded for env=dev. Use envs/staging or envs/prod for other environments."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus2"
}

variable "vnet_cidr" {
  description = "VNet address space."
  type        = string
  default     = "10.10.0.0/16"
}

variable "aks_subnet_cidr" {
  description = "AKS nodes subnet."
  type        = string
  default     = "10.10.0.0/22"
}

variable "pg_subnet_cidr" {
  description = "PostgreSQL Flexible Server subnet (delegated)."
  type        = string
  default     = "10.10.4.0/24"
}

variable "appgw_subnet_cidr" {
  description = "Application Gateway v2 subnet (Azure requires /24 minimum)."
  type        = string
  default     = "10.10.5.0/24"
}

variable "pe_subnet_cidr" {
  description = "Private Endpoints subnet."
  type        = string
  default     = "10.10.6.0/24"
}
