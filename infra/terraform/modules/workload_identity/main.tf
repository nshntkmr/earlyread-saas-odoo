# ─────────────────────────────────────────────────────────────────────────────
# Workload Identity module — UAMI-based (no AAD app registrations needed)
#
# Creates user-assigned managed identities for cluster-side services that need
# Azure permissions:
#   • ESO        → reads KV secrets        (Key Vault Secrets User on env KV)
#   • cert-manager → writes DNS TXT records  (DNS Zone Contributor on env DNS zone)
#
# Each UAMI is linked to a K8s ServiceAccount via federated identity credential.
# The K8s SA must be annotated with the UAMI's client_id (done in the
# cluster_services module via Helm chart values).
#
# All operations use the existing Contributor + UAA permissions of the
# Terraform SP — no AAD-side permissions required.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
}

# ─── ESO identity ────────────────────────────────────────────────────────────

resource "azurerm_user_assigned_identity" "eso" {
  name                = "earlyread-saas-${var.env}-eso-id"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# Federated credential — trusts tokens issued by AKS OIDC for this specific SA
resource "azurerm_federated_identity_credential" "eso" {
  name                = "earlyread-saas-${var.env}-eso-fed"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.eso.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:external-secrets-system:external-secrets"
}

resource "azurerm_role_assignment" "eso_kv_secrets_user" {
  scope                = var.kv_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.eso.principal_id
}

# ─── cert-manager identity ──────────────────────────────────────────────────

resource "azurerm_user_assigned_identity" "cert_manager" {
  name                = "earlyread-saas-${var.env}-cert-id"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "cert_manager" {
  name                = "earlyread-saas-${var.env}-cert-fed"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.cert_manager.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:cert-manager:cert-manager"
}

# cert-manager writes TXT records to the env's public DNS zone during the
# DNS-01 ACME challenge with Let's Encrypt.
resource "azurerm_role_assignment" "cert_manager_dns_zone_contrib" {
  scope                = var.dns_zone_id
  role_definition_name = "DNS Zone Contributor"
  principal_id         = azurerm_user_assigned_identity.cert_manager.principal_id
}
