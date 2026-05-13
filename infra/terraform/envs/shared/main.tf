# ─────────────────────────────────────────────────────────────────────────────
# SHARED layer — one-time apply
#
# Creates resources used by BOTH dev and staging:
#   • Shared RG (separate from tfstate-rg and env-specific RGs)
#   • Azure Container Registry (Standard tier)
#
# Both dev and staging reference the ACR via data source at apply time.
# Deleting dev or staging RGs does not affect this layer.
#
# Lifecycle:
#   • Apply: ONCE per cloud account (see README runbook M3 prep)
#   • Destroy: should never be needed under normal operations
# ─────────────────────────────────────────────────────────────────────────────

locals {
  tags = {
    project    = "earlyread-saas"
    layer      = "shared"
    managed_by = "terraform"
    repo       = "earlyread-saas-odoo"
  }
}

resource "azurerm_resource_group" "shared" {
  name     = "earlyread-saas-shared-rg"
  location = var.location
  tags     = local.tags
}

module "acr" {
  source = "../../modules/acr"

  name                = var.acr_name
  location            = var.location
  resource_group_name = azurerm_resource_group.shared.name
  tags                = local.tags
}
