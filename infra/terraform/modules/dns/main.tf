# ─────────────────────────────────────────────────────────────────────────────
# DNS module — Azure DNS zone for one env
#
# Creates the zone only. A-records and TXT records inside the zone are
# managed by app-side controllers (cert-manager, App Gateway Ingress
# Controller) starting in M3, NOT by Terraform.
#
# After apply, copy the four nameserver records into GoDaddy as NS records
# on the corresponding subdomain ('dev' or 'staging') under earlyread.ai.
# ─────────────────────────────────────────────────────────────────────────────

resource "azurerm_dns_zone" "this" {
  name                = var.zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}
