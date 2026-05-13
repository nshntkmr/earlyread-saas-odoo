# ─────────────────────────────────────────────────────────────────────────────
# ACR module — Azure Container Registry (shared, one for all envs)
#
# Standard tier — sufficient for M3-M4 non-prod.
# Limitations (documented):
#   • No private endpoint support (Premium-only)
#   • No geo-replication (Premium-only)
#   • Public endpoint with admin disabled; AAD auth via AcrPull role
#
# Upgrade trigger: switch to Premium before prod for private ACR pulls.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

resource "azurerm_container_registry" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "Standard"

  # Admin user disabled — AKS pulls via AcrPull role on its kubelet identity.
  # No registry credentials shipped as K8s imagePullSecrets.
  admin_enabled = false

  tags = var.tags
}
