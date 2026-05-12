# ─────────────────────────────────────────────────────────────────────────────
# Filestore module — Azure Files Premium share for Odoo's persistent filestore
#
# Creates:
#   • Storage account (FileStorage kind — required for Premium Files)
#   • Azure Files share (Premium tier, 100 GB minimum)
#   • Private Endpoint in the 'pe' subnet
#   • Private DNS zone 'privatelink.file.core.windows.net' linked to the VNet
#
# Network posture: public endpoint enabled with deny-by-default firewall and
# IP allow-list (same pattern as Key Vault).  AKS pods mount this share at
# /var/lib/odoo via the Azure Files CSI driver in M5.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

# Premium Files require account_kind = "FileStorage"
resource "azurerm_storage_account" "this" {
  name                            = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_tier                    = "Premium"
  account_kind                    = "FileStorage"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = true
  shared_access_key_enabled       = true # CSI driver needs this for SMB auth

  network_rules {
    default_action             = "Deny"
    bypass                     = ["AzureServices"]
    ip_rules                   = var.allowed_ips
    virtual_network_subnet_ids = var.allowed_subnet_ids
  }

  tags = var.tags
}

# Azure Files share — mounted into AKS pods at /var/lib/odoo (M5)
resource "azurerm_storage_share" "filestore" {
  name               = "odoo-filestore"
  storage_account_id = azurerm_storage_account.this.id
  quota              = var.quota_gb
  enabled_protocol   = "SMB"
}

# Private DNS zone for Azure Files privatelink endpoint
resource "azurerm_private_dns_zone" "files" {
  name                = "privatelink.file.core.windows.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "files" {
  name                  = "earlyread-saas-${var.env}-files-vnet-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.files.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
}

# Private Endpoint for Files sub-resource (storage account has separate PEs
# per service: 'file', 'blob', 'queue', etc.  We only need 'file'.)
resource "azurerm_private_endpoint" "files" {
  name                = "${var.name}-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.pe_subnet_id

  private_service_connection {
    name                           = "${var.name}-psc"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.files.id]
  }

  tags = var.tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.files]
}
