# ─────────────────────────────────────────────────────────────────────────────
# Key Vault module
#
# Creates:
#   • Key Vault (RBAC mode, soft-delete + purge-protection)
#   • Private Endpoint in the 'pe' subnet
#   • Private DNS zone 'privatelink.vaultcore.azure.net' linked to the VNet
#   • Role assignment granting the Terraform SP 'Key Vault Administrator' so
#     it can seed initial secrets
#   • Initial secrets, all with lifecycle.ignore_changes = [value] so manual
#     rotations don't get reverted
#
# Network posture: PUBLIC ENDPOINT ENABLED with deny-by-default firewall,
# allow-listing your IP + AzureServices bypass + AKS subnet (for M3+).  This
# lets you run Terraform from your laptop during M2; we tighten to fully
# private once M3 (AKS + ESO + workload identity) is in place.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.11"
    }
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  enable_rbac_authorization     = true
  public_network_access_enabled = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90

  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    ip_rules                   = var.allowed_ips
    virtual_network_subnet_ids = var.allowed_subnet_ids
  }

  tags = var.tags
}

# Grant Terraform SP "Key Vault Administrator" so it can seed initial secrets.
# Requires the SP to already have "User Access Administrator" at sub scope
# (the user granted this manually before M2).
resource "azurerm_role_assignment" "tf_kv_admin" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Azure RBAC has eventual consistency — there's a ~30-60s window between
# role assignment creation and effective permission. This sleep prevents
# the first secret-create call from racing with role propagation.
resource "time_sleep" "wait_for_kv_role" {
  depends_on      = [azurerm_role_assignment.tf_kv_admin]
  create_duration = "60s"
}

# Private DNS zone for KV's privatelink endpoint
resource "azurerm_private_dns_zone" "kv" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "kv" {
  name                  = "earlyread-saas-${var.env}-kv-vnet-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.kv.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
}

# Private Endpoint for Key Vault
resource "azurerm_private_endpoint" "kv" {
  name                = "${var.name}-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.pe_subnet_id

  private_service_connection {
    name                           = "${var.name}-psc"
    private_connection_resource_id = azurerm_key_vault.this.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.kv.id]
  }

  tags = var.tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.kv]
}

# ─── Initial secrets ─────────────────────────────────────────────────────────
# All use lifecycle.ignore_changes = [value, version, content_type, tags] so
# that manual rotations (via portal or 'az keyvault secret set') aren't
# reverted on subsequent 'terraform apply' runs.
#
# Terraform creates each secret slot once with the supplied initial value.
# Replace placeholders ('REPLACE_ME') manually before M5.

resource "azurerm_key_vault_secret" "secrets" {
  for_each     = var.initial_secrets
  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.this.id
  content_type = "text/plain"

  tags = var.tags

  lifecycle {
    ignore_changes = [value, version, content_type, tags]
  }

  depends_on = [time_sleep.wait_for_kv_role]
}
