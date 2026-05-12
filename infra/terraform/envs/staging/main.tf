# ─────────────────────────────────────────────────────────────────────────────
# STAGING environment
#
# Address space: 10.20.0.0/16  (separate from dev's 10.10/16 for future
# peering with no overlap)
#   aks    10.20.0.0/22
#   pg     10.20.4.0/24  (delegated to Microsoft.DBforPostgreSQL)
#   appgw  10.20.5.0/24  (App Gateway v2 — /24 minimum required by Azure)
#   pe     10.20.6.0/24
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

# Randomly generated PG admin password. Avoid SQL-quoting nightmare chars.
resource "random_password" "pg_admin" {
  length           = 32
  special          = true
  override_special = "_-"
  min_lower        = 4
  min_upper        = 4
  min_numeric      = 4
}

# Randomly generated JWT signing secret (POSTERRA_JWT_SECRET env var in M5)
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
  # AKS subnet pre-allowed so M3 workload identity can read secrets without
  # a separate VNet rule change.
  allowed_subnet_ids = [module.network.subnet_ids["aks"]]

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
  allowed_subnet_ids  = [module.network.subnet_ids["aks"]]
  quota_gb            = var.filestore_quota_gb

  tags = local.tags
}
