# ─────────────────────────────────────────────────────────────────────────────
# DEV environment
#
# Address space: 10.10.0.0/16
#   aks    10.10.0.0/22  (1024 IPs for nodes; pods use CNI Overlay 100.64/16)
#   pg     10.10.4.0/24  (delegated to Microsoft.DBforPostgreSQL)
#   appgw  10.10.5.0/24  (App Gateway v2 — /24 minimum required by Azure)
#   pe     10.10.6.0/24  (Private Endpoints for KV / Storage / ACR)
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
