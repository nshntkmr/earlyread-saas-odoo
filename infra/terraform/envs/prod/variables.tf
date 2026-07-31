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
  default     = "prod"

  validation {
    condition     = var.env == "prod"
    error_message = "This directory is hardcoded for env=prod. Use envs/dev for other environments."
  }
}

variable "location" {
  description = <<-EOT
    Azure region. Decide at apply time based on Dasv7 quota:
      - eastus2   — co-located with dev + shared ACR, but only 10 vCPU of Dasv7
                    free today. Needs a quota increase for a realistic prod.
      - eastus / centralus — 20 vCPU free today (Dasv7 10 + DASv4 10, both
                    unused), so prod can stand up with no approval. centralus
                    is eastus2's Azure paired region (geo-redundant PG backups).
    Cross-region from eastus2 means cross-region ACR pulls (Standard tier
    cannot geo-replicate). Everything else here is region-agnostic.
  EOT
  type        = string
  default     = "eastus2"
}

# ─── M1 — Networking ─────────────────────────────────────────────────────────

variable "vnet_cidr" {
  description = "VNet address space. 10.30/16 — no overlap with dev (10.10) or staging (10.20)."
  type        = string
  default     = "10.30.0.0/16"
}

variable "aks_subnet_cidr" {
  description = "AKS nodes subnet."
  type        = string
  default     = "10.30.0.0/22"
}

variable "pg_subnet_cidr" {
  description = "PostgreSQL Flexible Server subnet (delegated)."
  type        = string
  default     = "10.30.4.0/24"
}

variable "appgw_subnet_cidr" {
  description = "Application Gateway v2 subnet (Azure requires /24 minimum)."
  type        = string
  default     = "10.30.5.0/24"
}

variable "pe_subnet_cidr" {
  description = "Private Endpoints subnet."
  type        = string
  default     = "10.30.6.0/24"
}

# ─── M1 — DNS (apex zone is READ, never created) ─────────────────────────────

variable "dns_zone_name" {
  description = "Apex DNS zone serving tenant subdomains (client.earlyread.ai). Must ALREADY exist as an Azure DNS zone — prod reads it and adds only the wildcard A record."
  type        = string
  default     = "earlyread.ai"
}

variable "dns_zone_resource_group_name" {
  description = "Resource group holding the apex DNS zone. It is NOT prod's resource group — the zone is owned outside this state (it also carries the dev.earlyread.ai NS delegation)."
  type        = string
}

# ─── M2 — PostgreSQL ─────────────────────────────────────────────────────────

variable "pg_admin_username" {
  description = "PostgreSQL admin login name."
  type        = string
  default     = "psadmin"
}

variable "pg_sku_name" {
  description = "PG Flex SKU. NOTE: PostgreSQL Flexible Server SKUs draw on a SEPARATE managed-service capacity pool from the VM-family vCPU quotas — the DASv5 = 0 constraint that blocks AKS node SKUs does NOT apply here."
  type        = string
  default     = "GP_Standard_D2ds_v5"
}

variable "pg_storage_mb" {
  description = "PG storage in MB. 131072 = 128 GB (prod). Storage can be grown but NEVER shrunk."
  type        = number
  default     = 131072
}

variable "pg_backup_retention_days" {
  description = "PG backup retention in days (7-35). Prod: 35 (max)."
  type        = number
  default     = 35
}

variable "pg_geo_redundant_backup_enabled" {
  description = "Enable geo-redundant backups. Prod: yes. Backups land in the region's Azure pair, so the pair changes if `location` changes."
  type        = bool
  default     = true
}

variable "pg_pgbouncer_enabled" {
  description = "Enable built-in PgBouncer transaction pool. Prod: yes."
  type        = bool
  default     = true
}

variable "pg_database_name" {
  description = "Initial DB name inside PG (matches Odoo's db_filter)."
  type        = string
  default     = "posterra_prod"
}

# ─── M2 — Key Vault ──────────────────────────────────────────────────────────

variable "kv_name" {
  description = "Key Vault name (Azure limit: 24 chars, globally unique)."
  type        = string
  default     = "earlyread-saas-prod-kv"
}

# ─── M2 — Filestore (Azure Files) ────────────────────────────────────────────

variable "filestore_storage_name" {
  description = "Storage account name (3-24 chars, lowercase alphanumeric, globally unique)."
  type        = string
  default     = "earlyreadprodfseread"
}

variable "filestore_quota_gb" {
  description = "Azure Files share quota in GB. Premium minimum is 100; raise as the filestore grows."
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

# ─── M3 — AKS ────────────────────────────────────────────────────────────────

variable "kubernetes_version" {
  description = "AKS Kubernetes version. Verify with `az aks get-versions --location <region>`."
  type        = string
  default     = "1.34.6"
}

variable "pod_cidr" {
  description = "Pod CIDR for CNI Overlay."
  type        = string
  default     = "100.64.0.0/16"
}

# Prod system pool — Dasv7. AKS hard rule: >= 2 nodes AND >= 4 vCPU SKU.
variable "system_vm_size" {
  description = "AKS system pool VM SKU. Dasv7 family — DASv5 is 0 quota subscription-wide and dev already holds 8/10 of eastus2 DASv4."
  type        = string
  default     = "Standard_D4as_v7"
}

variable "system_min_count" {
  description = "System pool min node count (Azure minimum for a system pool is 2)."
  type        = number
  default     = 2
}

variable "system_max_count" {
  description = "System pool max node count (autoscale)."
  type        = number
  default     = 3
}

# Prod user pool — Dasv7.
variable "user_vm_size" {
  description = "AKS user pool VM SKU."
  type        = string
  default     = "Standard_D4as_v7"
}

variable "user_min_count" {
  description = "User pool min node count."
  type        = number
  default     = 2
}

variable "user_max_count" {
  description = "User pool max node count. Raise once a load baseline exists — bounded by Dasv7 family quota in the chosen region."
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

variable "appgw_sku" {
  description = <<-EOT
    App Gateway SKU. 'Standard_v2' (~$180/mo, no WAF) or 'WAF_v2' (~$324/mo).
    Set to Standard_v2 by explicit decision — WAF deferred to a later stage.

    ⚠ The switch to WAF_v2 is NOT in-place: Terraform destroys and re-creates
    the gateway (~5-10 min downtime), and that will be on a live PHI system.
    Budget a maintenance window when you make the change.

    v1 SKUs are not an option: AGIC supports Application Gateway v2 only, and
    v1 was retired by Azure on 28 April 2026.
  EOT
  type        = string
  default     = "Standard_v2"

  validation {
    condition     = contains(["Standard_v2", "WAF_v2"], var.appgw_sku)
    error_message = "appgw_sku must be Standard_v2 or WAF_v2 (v1 SKUs are retired and unsupported by AGIC)."
  }
}

variable "waf_mode" {
  description = "WAF firewall mode. Only applied when appgw_sku = WAF_v2. Start in Detection and flip to Prevention after a tuning period (mode change IS in-place, no downtime)."
  type        = string
  default     = "Detection"
}
