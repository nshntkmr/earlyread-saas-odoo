# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL Flexible Server module
#
# Uses VNet INJECTION (NOT private endpoint) — the server gets a NIC directly
# in the delegated 'pg' subnet established in M1.  This is the native private-
# access mode for PG Flex; it does NOT use the 'privatelink.*' DNS zone pattern
# that PE-based services use.
#
# DNS resolution: a custom-named Azure Private DNS Zone (suffix must end with
# '.postgres.database.azure.com') is linked to the env's VNet so internal
# clients resolve <server-name>.<zone> to the PG server's VNet-internal IP.
#
# Odoo 19 officially supports PostgreSQL versions 14–16.  We pin 16 (released
# Oct 2023, ~2.5 years of GA track record).  Upgrade trigger: when Odoo
# certifies PG 17/18 in their compatibility matrix.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

locals {
  # Zone name must end with '.postgres.database.azure.com'. The 'earlyread-<env>'
  # prefix keeps each env's zone unique within the subscription.
  private_zone_name = "earlyread-${var.env}.postgres.database.azure.com"
}

# Private DNS zone for PG server FQDN resolution
resource "azurerm_private_dns_zone" "pg" {
  name                = local.private_zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# Link the zone to the env's VNet
resource "azurerm_private_dns_zone_virtual_network_link" "pg" {
  name                  = "earlyread-saas-${var.env}-pg-vnet-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.pg.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
}

# PostgreSQL Flexible Server with VNet injection
resource "azurerm_postgresql_flexible_server" "this" {
  name                          = "earlyread-saas-${var.env}-pg"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "16"
  delegated_subnet_id           = var.delegated_subnet_id
  private_dns_zone_id           = azurerm_private_dns_zone.pg.id
  public_network_access_enabled = false

  administrator_login    = var.admin_username
  administrator_password = var.admin_password

  sku_name   = var.sku_name
  storage_mb = var.storage_mb
  zone       = "1"

  backup_retention_days        = var.backup_retention_days
  geo_redundant_backup_enabled = var.geo_redundant_backup_enabled

  tags = var.tags

  # PG Flex needs the DNS zone linked to the VNet BEFORE the server is created,
  # otherwise it can't write its A record at provisioning time.
  depends_on = [azurerm_private_dns_zone_virtual_network_link.pg]

  lifecycle {
    # Prevent accidental destruction of the server (which would wipe all data).
    # To intentionally destroy: remove this block first, then 'terraform destroy'.
    prevent_destroy = false # Set true once you have prod data; keep false for dev iteration.
  }
}

# Initial database for Odoo to populate at M5 init time
resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  lifecycle {
    # Odoo creates tables in this DB; don't let terraform recreate it
    prevent_destroy = false # Same caveat as the server above
  }
}

# Built-in PgBouncer for Standard SKUs (staging only — Burstable doesn't support it)
resource "azurerm_postgresql_flexible_server_configuration" "pgbouncer_enabled" {
  count     = var.pgbouncer_enabled ? 1 : 0
  name      = "pgbouncer.enabled"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "true"
}

resource "azurerm_postgresql_flexible_server_configuration" "pgbouncer_pool_mode" {
  count     = var.pgbouncer_enabled ? 1 : 0
  name      = "pgbouncer.pool_mode"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "TRANSACTION"
}

# Force all connections to use TLS
resource "azurerm_postgresql_flexible_server_configuration" "require_tls" {
  name      = "require_secure_transport"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "ON"
}
