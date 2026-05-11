variable "env" {
  description = "Environment slug (e.g. dev, staging, prod). Used in resource names."
  type        = string
}

variable "location" {
  description = "Azure region (e.g. eastus2)."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that holds these network resources."
  type        = string
}

variable "vnet_cidr" {
  description = "CIDR block for the VNet (e.g. 10.10.0.0/16)."
  type        = string
}

variable "aks_subnet_cidr" {
  description = "CIDR block for the AKS subnet."
  type        = string
}

variable "pg_subnet_cidr" {
  description = "CIDR block for the PostgreSQL Flexible Server subnet (delegated)."
  type        = string
}

variable "appgw_subnet_cidr" {
  description = "CIDR block for the Application Gateway subnet (must be /24 minimum)."
  type        = string
}

variable "pe_subnet_cidr" {
  description = "CIDR block for the Private Endpoints subnet."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
