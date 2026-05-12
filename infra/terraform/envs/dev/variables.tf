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

# ─── M1 — Networking ─────────────────────────────────────────────────────────

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

# ─── M2 — PostgreSQL ─────────────────────────────────────────────────────────

variable "pg_admin_username" {
  description = "PostgreSQL admin login name."
  type        = string
  default     = "psadmin"
}

variable "pg_sku_name" {
  description = "PostgreSQL Flexible Server SKU. Dev: B_Standard_B1ms (1vC/2GB Burstable)."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "pg_storage_mb" {
  description = "PG storage in MB. 32768 = 32 GB (dev)."
  type        = number
  default     = 32768
}

variable "pg_backup_retention_days" {
  description = "PG backup retention in days (7-35). Dev: 7."
  type        = number
  default     = 7
}

variable "pg_geo_redundant_backup_enabled" {
  description = "Enable geo-redundant backups. Dev: no."
  type        = bool
  default     = false
}

variable "pg_pgbouncer_enabled" {
  description = "Enable built-in PgBouncer transaction pool. Dev: no (B1ms doesn't support it)."
  type        = bool
  default     = false
}

variable "pg_database_name" {
  description = "Initial DB name inside PG (matches Odoo's db_filter)."
  type        = string
  default     = "posterra_dev"
}

# ─── M2 — Key Vault ──────────────────────────────────────────────────────────

variable "kv_name" {
  description = "Key Vault name (3-24 chars, alphanumeric + hyphens, globally unique)."
  type        = string
  default     = "earlyread-saas-dev-kv"
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

variable "filestore_storage_name" {
  description = "Storage account name (3-24 chars, lowercase alphanumeric only, globally unique)."
  type        = string
  default     = "earlyreaddevfseread"
}

variable "filestore_quota_gb" {
  description = "Azure Files share quota in GB. Premium minimum is 100."
  type        = number
  default     = 100
}

# ─── M2 — Network ACLs ───────────────────────────────────────────────────────

variable "allowed_ips" {
  description = "Public IPs allowed through KV + Storage firewalls. Includes your laptop / CI runner IP. Update via terraform.tfvars when your IP changes."
  type        = list(string)
  default     = []
}
