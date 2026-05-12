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
  default     = "staging"

  validation {
    condition     = var.env == "staging"
    error_message = "This directory is hardcoded for env=staging. Use envs/dev or envs/prod for other environments."
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
  default     = "10.20.0.0/16"
}

variable "aks_subnet_cidr" {
  description = "AKS nodes subnet."
  type        = string
  default     = "10.20.0.0/22"
}

variable "pg_subnet_cidr" {
  description = "PostgreSQL Flexible Server subnet (delegated)."
  type        = string
  default     = "10.20.4.0/24"
}

variable "appgw_subnet_cidr" {
  description = "Application Gateway v2 subnet (Azure requires /24 minimum)."
  type        = string
  default     = "10.20.5.0/24"
}

variable "pe_subnet_cidr" {
  description = "Private Endpoints subnet."
  type        = string
  default     = "10.20.6.0/24"
}

# ─── M2 — PostgreSQL ─────────────────────────────────────────────────────────

variable "pg_admin_username" {
  description = "PostgreSQL admin login name."
  type        = string
  default     = "psadmin"
}

variable "pg_sku_name" {
  description = "PG Flex SKU. Staging: GP_Standard_D2ds_v5 (2vC/8GB General Purpose, supports PgBouncer)."
  type        = string
  default     = "GP_Standard_D2ds_v5"
}

variable "pg_storage_mb" {
  description = "PG storage in MB. 65536 = 64 GB (staging)."
  type        = number
  default     = 65536
}

variable "pg_backup_retention_days" {
  description = "PG backup retention in days (7-35). Staging: 35."
  type        = number
  default     = 35
}

variable "pg_geo_redundant_backup_enabled" {
  description = "Enable geo-redundant backups. Staging: yes."
  type        = bool
  default     = true
}

variable "pg_pgbouncer_enabled" {
  description = "Enable built-in PgBouncer transaction pool. Staging: yes."
  type        = bool
  default     = true
}

variable "pg_database_name" {
  description = "Initial DB name inside PG (matches Odoo's db_filter)."
  type        = string
  default     = "posterra_staging"
}

# ─── M2 — Key Vault ──────────────────────────────────────────────────────────

variable "kv_name" {
  description = "Key Vault name (3-24 chars). Staging uses 'stg' abbreviation to fit Azure's 24-char limit ('earlyread-saas-staging-kv' is 25 chars)."
  type        = string
  default     = "earlyread-saas-stg-kv"
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

variable "filestore_storage_name" {
  description = "Storage account name (3-24 chars, lowercase alphanumeric only). Staging uses 'stg' abbreviation."
  type        = string
  default     = "earlyreadstgfseread"
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
