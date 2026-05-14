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

# ─── M3 — Shared resources ───────────────────────────────────────────────────

variable "acr_name" {
  description = "Shared ACR name (created by envs/shared/, referenced via data source)."
  type        = string
  default     = "earlyreadsaasacreread"
}

# ─── M3 — AKS ────────────────────────────────────────────────────────────────

variable "kubernetes_version" {
  description = "AKS Kubernetes version. Verify availability with `az aks get-versions --location eastus2`."
  type        = string
  default     = "1.34.6"
}

variable "pod_cidr" {
  description = "Pod CIDR for CNI Overlay (RFC 6598 range — doesn't consume VNet IPs)."
  type        = string
  default     = "100.64.0.0/16"
}

# Dev system pool — must be >= 4 vCPU SKU AND >= 2 nodes (AKS rule).
# D4as_v4 (DASv4 family) chosen over D4as_v5 because every v5 D-family has a
# quota LIMIT of 0 in eastus2 (capacity-constrained region). v4/v6/v7
# families have non-zero quota. D4as_v4 = 4 vCPU / 16 GB, DASv4 family.
variable "system_vm_size" {
  description = "AKS system pool VM SKU. Must be >= 4 vCPU / 4 GB RAM. D4as_v4 draws on the DASv4 family quota."
  type        = string
  default     = "Standard_D4as_v4"
}

variable "system_min_count" {
  description = "System pool min node count. AKS requires ≥ 2."
  type        = number
  default     = 2
}

variable "system_max_count" {
  description = "System pool max node count. Dev: fixed at 2 (min=max=2)."
  type        = number
  default     = 2
}

# Dev user pool — cost-optimized. D2s_v4 draws on the DSv4 family quota —
# a SEPARATE family from the system pool's DASv4, so neither family's
# 10-vCPU limit is the bottleneck for dev.
variable "user_vm_size" {
  description = "AKS user pool VM SKU. Dev: D2s_v4 (2vCPU/8GB, DSv4 family)."
  type        = string
  default     = "Standard_D2s_v4"
}

variable "user_min_count" {
  description = "User pool min node count."
  type        = number
  default     = 1
}

variable "user_max_count" {
  description = "User pool max node count."
  type        = number
  default     = 2
}

variable "admin_group_object_ids" {
  description = "Azure AD group OIDs granted system:masters (K8s RBAC). Empty = use --admin flag for ad-hoc kubectl."
  type        = list(string)
  default     = []
}

variable "cluster_admin_oids" {
  description = "Principal OIDs granted 'Azure Kubernetes Service RBAC Cluster Admin' (Azure RBAC layer). Empty = relies on --admin flag local accounts."
  type        = list(string)
  default     = []
}

# ─── M3 — App Gateway ────────────────────────────────────────────────────────

variable "appgw_sku" {
  description = "App Gateway SKU. 'Standard_v2' (~$180/mo, no WAF) or 'WAF_v2' (~$324/mo). SKU cannot be changed in-place — switching requires gateway recreation + DNS cutover. Dev: Standard_v2 (cost-optimized non-prod)."
  type        = string
  default     = "Standard_v2"
}

variable "waf_mode" {
  description = "WAF firewall mode. Only applied when appgw_sku = WAF_v2. Detection for first 2 weeks per parent plan; flip to Prevention in M6."
  type        = string
  default     = "Detection"
}
