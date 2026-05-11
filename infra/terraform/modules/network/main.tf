# ─────────────────────────────────────────────────────────────────────────────
# Network module — VNet, 4 subnets, NAT Gateway
#
# Subnets:
#   aks    nodes (pods use CNI Overlay, separate Pod CIDR)
#   pg     PostgreSQL Flexible Server (delegated to Microsoft.DBforPostgreSQL)
#   appgw  Application Gateway v2 (M3)
#   pe     Private Endpoints for Key Vault / Storage / ACR (M2+)
#
# NAT Gateway attached to the AKS subnet for fixed-IP outbound to
# ClickHouse Cloud, Anthropic API, package mirrors. PG / App Gateway / PEs
# do not need NAT.
# ─────────────────────────────────────────────────────────────────────────────

resource "azurerm_virtual_network" "this" {
  name                = "earlyread-saas-${var.env}-vnet"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = [var.vnet_cidr]
  tags                = var.tags
}

# ── AKS subnet ──────────────────────────────────────────────────────────────
resource "azurerm_subnet" "aks" {
  name                 = "earlyread-saas-${var.env}-aks-snet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.aks_subnet_cidr]
}

# ── PostgreSQL Flexible Server subnet (delegated) ───────────────────────────
# Delegating now (with subnet empty) so M2 can drop a PG server in without
# requiring a subnet update.  Microsoft.DBforPostgreSQL flexible servers
# require exclusive subnet ownership via this delegation.
resource "azurerm_subnet" "pg" {
  name                 = "earlyread-saas-${var.env}-pg-snet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.pg_subnet_cidr]

  delegation {
    name = "pg-flex-delegation"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }

  # Enables backups via service endpoint when M2 lands
  service_endpoints = ["Microsoft.Storage"]
}

# ── App Gateway subnet ──────────────────────────────────────────────────────
# Azure rule: AppGw v2 requires /24 minimum (not negotiable). NSG attaches
# in M3 with the GatewayManager allow rule for Azure-internal probes.
resource "azurerm_subnet" "appgw" {
  name                 = "earlyread-saas-${var.env}-appgw-snet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.appgw_subnet_cidr]
}

# ── Private Endpoints subnet ─────────────────────────────────────────────────
resource "azurerm_subnet" "pe" {
  name                              = "earlyread-saas-${var.env}-pe-snet"
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [var.pe_subnet_cidr]
  private_endpoint_network_policies = "Disabled" # PEs require this
}

# ─────────────────────────────────────────────────────────────────────────────
# NAT Gateway — outbound internet for AKS pods with fixed public IP
# ─────────────────────────────────────────────────────────────────────────────

resource "azurerm_public_ip" "natgw" {
  name                = "earlyread-saas-${var.env}-natgw-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway" "this" {
  name                    = "earlyread-saas-${var.env}-natgw"
  location                = var.location
  resource_group_name     = var.resource_group_name
  sku_name                = "Standard"
  idle_timeout_in_minutes = 10
  tags                    = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "this" {
  nat_gateway_id       = azurerm_nat_gateway.this.id
  public_ip_address_id = azurerm_public_ip.natgw.id
}

# Attach NAT only to the AKS subnet — that's the one that needs egress.
# PG, AppGw, PEs all use service-side networking (no outbound from inside).
resource "azurerm_subnet_nat_gateway_association" "aks" {
  subnet_id      = azurerm_subnet.aks.id
  nat_gateway_id = azurerm_nat_gateway.this.id
}
