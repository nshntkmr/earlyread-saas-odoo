# ─────────────────────────────────────────────────────────────────────────────
# DEV services layer — cluster-side services inside AKS
#
# Applied AFTER envs/dev/ (which creates AKS, AppGw, UAMIs, KV, DNS zone).
#
# This config reads infra outputs from envs/dev/'s state via
# terraform_remote_state and instantiates the cluster_services module.
# ─────────────────────────────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

# Read infra outputs from envs/dev/'s state
data "terraform_remote_state" "infra" {
  backend = "azurerm"
  config = {
    resource_group_name  = "earlyread-saas-tfstate-rg"
    storage_account_name = "earlyreadtfstateeread"
    container_name       = "dev"
    key                  = "terraform.tfstate"
  }
}

module "cluster_services" {
  source = "../../../modules/cluster_services"

  env             = var.env
  subscription_id = var.subscription_id
  tenant_id       = data.azurerm_client_config.current.tenant_id

  # cert-manager wiring
  cert_manager_uami_client_id   = data.terraform_remote_state.infra.outputs.cert_manager_uami_client_id
  acme_email                    = var.acme_email
  dns_zone_name                 = data.terraform_remote_state.infra.outputs.dns_zone_name
  dns_zone_resource_group_name  = data.terraform_remote_state.infra.outputs.resource_group_name

  # ESO wiring
  eso_uami_client_id = data.terraform_remote_state.infra.outputs.eso_uami_client_id
  kv_uri             = data.terraform_remote_state.infra.outputs.kv_uri
}
