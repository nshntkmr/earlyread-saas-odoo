# ─────────────────────────────────────────────────────────────────────────────
# AKS module — Azure Kubernetes Service cluster with system + user pools
#
# Design choices (per parent plan + Codex review):
#   • Azure CNI Overlay (node IPs from VNet, pod IPs from 100.64/16 Pod CIDR)
#   • System pool is mandatory ≥ 4 vCPU SKU (D4as_v5) + min 2 nodes (AKS rule)
#   • User pool sized per env (asymmetric: dev small, staging prod-replica)
#   • OIDC issuer + workload identity ENABLED (required for ESO + cert-manager)
#   • Azure AD integration + Azure RBAC enabled
#   • Local accounts ALSO enabled — supports `az aks get-credentials --admin`
#     bypass for ad-hoc kubectl when Azure RBAC roles not yet granted
#   • AGIC add-on enabled, pointed at the App Gateway provisioned by appgw module
#   • Outbound: uses the env's existing NAT Gateway (attached to AKS subnet in M1)
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = "earlyread-saas-${var.env}-aks"
  location            = var.location
  resource_group_name = var.resource_group_name
  kubernetes_version  = var.kubernetes_version
  dns_prefix          = "earlyread-saas-${var.env}"

  # Workload identity + OIDC — required for ESO and cert-manager auth
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  # Convenience: --admin flag works for ad-hoc kubectl access regardless of RBAC
  local_account_disabled = false

  default_node_pool {
    name           = "syspool"
    vm_size        = var.system_vm_size
    vnet_subnet_id = var.aks_subnet_id

    auto_scaling_enabled = true
    min_count            = var.system_min_count
    max_count            = var.system_max_count

    # Taint system pool so only critical add-ons schedule here (kube-system,
    # AGIC, cert-manager, ESO). User workloads land on the user pool.
    only_critical_addons_enabled = true

    upgrade_settings {
      max_surge = "10%"
    }

    tags = var.tags
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    pod_cidr            = var.pod_cidr
    service_cidr        = "10.100.0.0/16"
    dns_service_ip      = "10.100.0.10"
    load_balancer_sku   = "standard"
    # Use the env's NAT Gateway from M1 for egress (fixed IP for CH/Anthropic
    # allow-listing). M1 already attached the NAT gateway to the AKS subnet.
    outbound_type = "userAssignedNATGateway"
  }

  # AGIC add-on — AKS-managed controller pod that watches Ingress resources
  # and translates them into App Gateway routing rules. Uses its own managed
  # identity (separate from the cluster's), permissions granted below.
  ingress_application_gateway {
    gateway_id = var.appgw_id
  }

  # Azure AD integration. Azure RBAC enabled (graceful path for production
  # later); for now, also rely on local accounts (--admin flag).
  azure_active_directory_role_based_access_control {
    azure_rbac_enabled     = true
    admin_group_object_ids = var.admin_group_object_ids
  }

  tags = var.tags
}

# ─── User node pool ──────────────────────────────────────────────────────────
# Separate from default_node_pool (which is the system pool). Workload pods
# schedule here by virtue of NOT having the CriticalAddonsOnly toleration.

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "userpool"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.user_vm_size
  vnet_subnet_id        = var.aks_subnet_id
  mode                  = "User"

  auto_scaling_enabled = true
  min_count            = var.user_min_count
  max_count            = var.user_max_count

  upgrade_settings {
    max_surge = "33%"
  }

  tags = var.tags
}

# ─── Role assignments — AGIC's managed identity ──────────────────────────────
#
# AGIC needs to read network resources (VNet/subnets) AND modify the App
# Gateway. Network Contributor on the App Gateway is the least-privilege fit;
# Reader on the env RG covers subnet/VNet lookups.

resource "azurerm_role_assignment" "agic_appgw_network_contrib" {
  scope                = var.appgw_id
  role_definition_name = "Network Contributor"
  principal_id         = azurerm_kubernetes_cluster.this.ingress_application_gateway[0].ingress_application_gateway_identity[0].object_id
}

resource "azurerm_role_assignment" "agic_rg_reader" {
  scope                = var.resource_group_id
  role_definition_name = "Reader"
  principal_id         = azurerm_kubernetes_cluster.this.ingress_application_gateway[0].ingress_application_gateway_identity[0].object_id
}

# ─── Role assignment — AKS kubelet → ACR pull ───────────────────────────────
# AKS pulls container images using its kubelet identity. Grant it AcrPull on
# the shared registry so pods can reference earlyreadsaasacreread.azurecr.io
# images without imagePullSecrets.
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

# ─── Optional Azure RBAC cluster-admin role assignments ─────────────────────
# Grants "Azure Kubernetes Service RBAC Cluster Admin" to specified principals.
# Empty list by default — admins use `az aks get-credentials --admin` for now.
resource "azurerm_role_assignment" "cluster_admins" {
  for_each             = toset(var.cluster_admin_oids)
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service RBAC Cluster Admin"
  principal_id         = each.value
}
