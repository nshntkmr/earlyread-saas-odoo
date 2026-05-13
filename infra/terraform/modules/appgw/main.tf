# ─────────────────────────────────────────────────────────────────────────────
# App Gateway v2 module (SKU configurable: Standard_v2 or WAF_v2)
#
# Public HTTPS front door. Terminates TLS, routes by host header to AKS
# Services. AGIC (the AKS add-on) manages the runtime config (backend pools,
# listeners, routing rules) — Terraform only creates the gateway, public IP,
# and baseline defaults.
#
# SKU options:
#   • Standard_v2 — TLS + routing + autoscale + AGIC integration, NO WAF
#                   (~$180/mo fixed). Default for non-prod.
#   • WAF_v2      — adds OWASP rule sets + bot management + custom WAF rules
#                   (~$324/mo fixed). Required for prod / when WAF is desired.
#
# SKU cannot be changed in-place — switching requires recreating the
# App Gateway and re-pointing DNS. Pick the right SKU per-env.
#
# When sku_name = "WAF_v2", waf_mode starts in Detection (logs but doesn't
# block) per parent plan; flips to Prevention in M6 after baseline period.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

resource "azurerm_public_ip" "this" {
  name                = "earlyread-saas-${var.env}-appgw-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "earlyread-saas-${var.env}-appgw"
  tags                = var.tags
}

resource "azurerm_application_gateway" "this" {
  name                = "earlyread-saas-${var.env}-appgw"
  location            = var.location
  resource_group_name = var.resource_group_name

  sku {
    name = var.sku_name
    tier = var.sku_name
  }

  autoscale_configuration {
    min_capacity = 1
    max_capacity = 10
  }

  gateway_ip_configuration {
    name      = "gateway-ip-config"
    subnet_id = var.appgw_subnet_id
  }

  frontend_port {
    name = "port-80"
    port = 80
  }

  frontend_port {
    name = "port-443"
    port = 443
  }

  frontend_ip_configuration {
    name                 = "frontend-public"
    public_ip_address_id = azurerm_public_ip.this.id
  }

  # Placeholder backend pool + settings + listener + rule — AGIC replaces
  # these at runtime when Ingress resources are deployed. They exist only
  # so the AppGw can be created (Azure requires at least one of each).
  backend_address_pool {
    name = "default-backend-pool"
  }

  backend_http_settings {
    name                  = "default-backend-settings"
    cookie_based_affinity = "Disabled"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 60
  }

  http_listener {
    name                           = "default-listener"
    frontend_ip_configuration_name = "frontend-public"
    frontend_port_name             = "port-80"
    protocol                       = "Http"
  }

  request_routing_rule {
    name                       = "default-rule"
    rule_type                  = "Basic"
    priority                   = 100
    http_listener_name         = "default-listener"
    backend_address_pool_name  = "default-backend-pool"
    backend_http_settings_name = "default-backend-settings"
  }

  # waf_configuration block is ONLY valid when sku_name = "WAF_v2".
  # Azure rejects this block on Standard_v2. Dynamic block conditionally
  # emits it based on SKU.
  dynamic "waf_configuration" {
    for_each = var.sku_name == "WAF_v2" ? [1] : []
    content {
      enabled          = true
      firewall_mode    = var.waf_mode
      rule_set_type    = "OWASP"
      rule_set_version = "3.2"
    }
  }

  tags = var.tags

  # AGIC manages backends/listeners/rules at runtime. Ignore drift on these
  # so Terraform doesn't fight AGIC.
  lifecycle {
    ignore_changes = [
      backend_address_pool,
      backend_http_settings,
      http_listener,
      request_routing_rule,
      probe,
      ssl_certificate,
      url_path_map,
      tags,
    ]
  }
}
