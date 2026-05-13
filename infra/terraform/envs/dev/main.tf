# ─────────────────────────────────────────────────────────────────────────────
# DEV environment — INFRA layer
#
# Address space: 10.10.0.0/16
#   aks    10.10.0.0/22  (1024 IPs for nodes; pods use CNI Overlay 100.64/16)
#   pg     10.10.4.0/24  (delegated to Microsoft.DBforPostgreSQL)
#   appgw  10.10.5.0/24  (App Gateway v2 — /24 minimum required by Azure)
#   pe     10.10.6.0/24  (Private Endpoints for KV / Storage / ACR)
#
# Layers applied here (azurerm provider only):
#   M1: network, dns
#   M2: postgresql, keyvault, filestore
#   M3 infra: aks, appgw, workload_identity, wildcard DNS A record
#
# Cluster-side services (cert-manager, ESO) are in services/ subdirectory.
# ─────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    project     = "earlyread-saas"
    environment = var.env
    managed_by  = "terraform"
    repo        = "earlyread-saas-odoo"
  }
}

resource "azurerm_resource_group" "this" {
  name     = "earlyread-saas-${var.env}-rg"
  location = var.location
  tags     = local.tags
}

# Reference the shared ACR (created by envs/shared/ apply)
data "azurerm_container_registry" "shared" {
  name                = var.acr_name
  resource_group_name = "earlyread-saas-shared-rg"
}

# ─── M1 — Networking + DNS ───────────────────────────────────────────────────

module "network" {
  source = "../../modules/network"

  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name

  vnet_cidr         = var.vnet_cidr
  aks_subnet_cidr   = var.aks_subnet_cidr
  pg_subnet_cidr    = var.pg_subnet_cidr
  appgw_subnet_cidr = var.appgw_subnet_cidr
  pe_subnet_cidr    = var.pe_subnet_cidr

  tags = local.tags
}

module "dns" {
  source = "../../modules/dns"

  zone_name           = "${var.env}.earlyread.ai"
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

# ─── M2 — Data & secrets layer ───────────────────────────────────────────────

resource "random_password" "pg_admin" {
  length           = 32
  special          = true
  override_special = "_-"
  min_lower        = 4
  min_upper        = 4
  min_numeric      = 4
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

module "postgresql" {
  source = "../../modules/postgresql"

  env                          = var.env
  location                     = var.location
  resource_group_name          = azurerm_resource_group.this.name
  vnet_id                      = module.network.vnet_id
  delegated_subnet_id          = module.network.subnet_ids["pg"]
  admin_username               = var.pg_admin_username
  admin_password               = random_password.pg_admin.result
  sku_name                     = var.pg_sku_name
  storage_mb                   = var.pg_storage_mb
  backup_retention_days        = var.pg_backup_retention_days
  geo_redundant_backup_enabled = var.pg_geo_redundant_backup_enabled
  pgbouncer_enabled            = var.pg_pgbouncer_enabled
  database_name                = var.pg_database_name
  tags                         = local.tags
}

module "keyvault" {
  source = "../../modules/keyvault"

  name                = var.kv_name
  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  vnet_id             = module.network.vnet_id
  pe_subnet_id        = module.network.subnet_ids["pe"]
  allowed_ips         = var.allowed_ips

  initial_secrets = {
    "pg-admin-password" = random_password.pg_admin.result
    "jwt-secret"        = random_password.jwt_secret.result
    "ch-password-prod"  = "REPLACE_ME"
    "ai-api-key"        = "REPLACE_ME"
    "ai-endpoint"       = "https://api.anthropic.com"
    "ai-model"          = "claude-opus-4-6"
  }

  tags = local.tags
}

module "filestore" {
  source = "../../modules/filestore"

  name                = var.filestore_storage_name
  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  vnet_id             = module.network.vnet_id
  pe_subnet_id        = module.network.subnet_ids["pe"]
  allowed_ips         = var.allowed_ips
  quota_gb            = var.filestore_quota_gb

  tags = local.tags
}

# ─── M3 — AKS + App Gateway + Workload Identity ──────────────────────────────

module "appgw" {
  source = "../../modules/appgw"

  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  appgw_subnet_id     = module.network.subnet_ids["appgw"]
  waf_mode            = var.waf_mode

  tags = local.tags
}

module "aks" {
  source = "../../modules/aks"

  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  resource_group_id   = azurerm_resource_group.this.id

  kubernetes_version = var.kubernetes_version
  aks_subnet_id      = module.network.subnet_ids["aks"]
  pod_cidr           = var.pod_cidr

  appgw_id = module.appgw.id
  acr_id   = data.azurerm_container_registry.shared.id

  system_vm_size   = var.system_vm_size
  system_min_count = var.system_min_count
  system_max_count = var.system_max_count

  user_vm_size   = var.user_vm_size
  user_min_count = var.user_min_count
  user_max_count = var.user_max_count

  admin_group_object_ids = var.admin_group_object_ids
  cluster_admin_oids     = var.cluster_admin_oids

  tags = local.tags
}

module "workload_identity" {
  source = "../../modules/workload_identity"

  env                 = var.env
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name

  aks_oidc_issuer_url = module.aks.oidc_issuer_url
  kv_id               = module.keyvault.id
  dns_zone_id         = module.dns.zone_id

  tags = local.tags
}

# Wildcard A record covers every tenant subdomain (posterra.dev, inhome-v1.dev,
# etc.) plus admin.dev.earlyread.ai — all hit App Gateway which routes by host.
resource "azurerm_dns_a_record" "wildcard" {
  name                = "*"
  zone_name           = module.dns.zone_name
  resource_group_name = azurerm_resource_group.this.name
  ttl                 = 300
  records             = [module.appgw.public_ip]
  tags                = local.tags
}
