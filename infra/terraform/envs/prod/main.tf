# ─────────────────────────────────────────────────────────────────────────────
# PROD environment — INFRA layer
#
# Address space: 10.30.0.0/16  (dev 10.10/16, staging 10.20/16 — no overlap,
# so future VNet peering stays possible)
#   aks    10.30.0.0/22
#   pg     10.30.4.0/24  (delegated to Microsoft.DBforPostgreSQL)
#   appgw  10.30.5.0/24  (App Gateway v2 — /24 minimum required by Azure)
#   pe     10.30.6.0/24
#
# Three deliberate differences from dev/staging — read before editing:
#
#   1. DNS. Prod serves the APEX wildcard `*.earlyread.ai`, so it CONSUMES the
#      pre-existing `earlyread.ai` zone via a data source and creates ONLY the
#      wildcard A record. It must NOT create the zone: a new zone would get new
#      nameservers and drop the existing `dev.earlyread.ai` NS delegation.
#
#   2. Node SKUs. Dasv7 family. DASv5 has a quota limit of 0 subscription-wide
#      (not just eastus2 — East US and Central US are 0/0 too), and DASv4 in
#      eastus2 is 80% consumed by dev, which we are intentionally not touching.
#
#   3. App Gateway SKU is Standard_v2 (no WAF) by explicit decision. See the
#      `appgw_sku` variable for the upgrade cost.
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

# Reference the shared ACR (created by envs/shared/ apply).
# NOTE: the shared ACR lives in eastus2 on the Standard tier. If prod is
# deployed to a different region, image pulls are cross-region (slower on
# deploy/scale + egress). Geo-replication would require the Premium tier.
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

# Apex zone is PRE-EXISTING and owned outside this state — read only.
# Deliberately NOT `module "dns"` (which creates a zone). See header note 1.
data "azurerm_dns_zone" "apex" {
  name                = var.dns_zone_name
  resource_group_name = var.dns_zone_resource_group_name
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

# Odoo master password — database-manager auth + odoo.conf admin_passwd.
# override_special restricts to "_-" so the value is safe in the INI file
# (no "#" comment / "%" interpolation chars) and in shell/envsubst rendering.
resource "random_password" "odoo_admin" {
  length           = 32
  special          = true
  override_special = "_-"
  min_lower        = 4
  min_upper        = 4
  min_numeric      = 4
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

  # REPLACE_ME values MUST be set in Key Vault before the app serves traffic.
  initial_secrets = {
    "pg-admin-password"      = random_password.pg_admin.result
    "jwt-secret"             = random_password.jwt_secret.result
    "odoo-admin-password"    = random_password.odoo_admin.result
    "ch-password-prod"       = "REPLACE_ME"
    "ai-api-key"             = "REPLACE_ME"
    "ai-endpoint"            = "https://api.anthropic.com"
    "ai-model"               = "claude-opus-4-6"
    "filestore-account-name" = var.filestore_storage_name
    "filestore-account-key"  = "REPLACE_ME"
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
  sku_name            = var.appgw_sku
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

  # SCOPE NOTE: this grants the cert-manager UAMI DNS Zone Contributor on the
  # APEX zone (needed for DNS-01 TXT challenges on *.earlyread.ai). That zone
  # also holds the dev/staging NS delegation records — a broader blast radius
  # than dev's child-zone grant. Reviewed and accepted.
  dns_zone_id = data.azurerm_dns_zone.apex.id

  tags = local.tags
}

# Wildcard for tenant subdomains: client.earlyread.ai, acme.earlyread.ai, …
# Written INTO the pre-existing apex zone (hence the zone's own RG, not ours).
#
# ⚠ Two apex-wildcard behaviours that did NOT apply at *.dev.earlyread.ai:
#   • `*.earlyread.ai` does NOT match the bare apex `earlyread.ai` — the root
#     site needs its own A/ALIAS record, managed wherever the zone is owned.
#   • `*.earlyread.ai` DOES match `www.earlyread.ai`. Without an explicit `www`
#     record, www resolves here and the app rejects it (`www` is a reserved
#     subdomain), so visitors get an app error instead of the marketing site.
#     Add an explicit `www` record in the apex zone before go-live.
resource "azurerm_dns_a_record" "wildcard" {
  name                = "*"
  zone_name           = data.azurerm_dns_zone.apex.name
  resource_group_name = data.azurerm_dns_zone.apex.resource_group_name
  ttl                 = 300
  records             = [module.appgw.public_ip]
  tags                = local.tags
}
