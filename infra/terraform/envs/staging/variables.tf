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
  description = "PG Flex SKU. Staging: GP_Standard_D2ds_v5."
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
  description = "Key Vault name. Staging uses 'stg' abbreviation to fit Azure's 24-char limit."
  type        = string
  default     = "earlyread-saas-stg-kv"
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

variable "filestore_storage_name" {
  description = "Storage account name. Staging uses 'stg' abbreviation."
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
  description = "Public IPs allowed through KV + Storage firewalls."
  type        = list(string)
  default     = []
}

# ─── M3 — Shared resources ───────────────────────────────────────────────────

variable "acr_name" {
  description = "Shared ACR name (created by envs/shared/, referenced via data source)."
  type        = string
  default     = "earlyreadsaasacreread"
}

# ─── M3 — AKS (prod-replica sizing) ──────────────────────────────────────────

variable "kubernetes_version" {
  description = "AKS Kubernetes version."
  type        = string
  default     = "1.34.6"
}

variable "pod_cidr" {
  description = "Pod CIDR for CNI Overlay."
  type        = string
  default     = "100.64.0.0/16"
}

# Staging system pool — D4as_v5 minimum + autoscale 2-3
variable "system_vm_size" {
  description = "AKS system pool VM SKU. Staging: Standard_D4as_v5."
  type        = string
  default     = "Standard_D4as_v5"
}

variable "system_min_count" {
  description = "System pool min node count. Staging: 2."
  type        = number
  default     = 2
}

variable "system_max_count" {
  description = "System pool max node count. Staging: 3 (autoscale)."
  type        = number
  default     = 3
}

# Staging user pool — D4as_v5 + autoscale 2-3 (prod-replica for 20-30 concurrent)
variable "user_vm_size" {
  description = "AKS user pool VM SKU. Staging: Standard_D4as_v5 (prod-replica)."
  type        = string
  default     = "Standard_D4as_v5"
}

variable "user_min_count" {
  description = "User pool min node count. Staging: 2."
  type        = number
  default     = 2
}

variable "user_max_count" {
  description = "User pool max node count. Staging: 3 initial; raise after M9 k6 baseline."
  type        = number
  default     = 3
}

variable "admin_group_object_ids" {
  description = "Azure AD group OIDs granted system:masters (K8s RBAC)."
  type        = list(string)
  default     = []
}

variable "cluster_admin_oids" {
  description = "Principal OIDs granted 'Azure Kubernetes Service RBAC Cluster Admin'."
  type        = list(string)
  default     = []
}

# ─── M3 — App Gateway ────────────────────────────────────────────────────────

variable "waf_mode" {
  description = "WAF firewall mode. Detection for first 2 weeks per parent plan."
  type        = string
  default     = "Detection"
}
