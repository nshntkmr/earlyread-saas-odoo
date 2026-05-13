# ─────────────────────────────────────────────────────────────────────────────
# STAGING services layer — cluster-side services inside the staging AKS
#
# Applied AFTER envs/staging/ (which creates AKS, AppGw, UAMIs, KV, DNS zone).
# ─────────────────────────────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

data "terraform_remote_state" "infra" {
  backend = "azurerm"
  config = {
    resource_group_name  = "earlyread-saas-tfstate-rg"
    storage_account_name = "earlyreadtfstateeread"
    container_name       = "staging"
    key                  = "terraform.tfstate"
  }
}

module "cluster_services" {
  source = "../../../modules/cluster_services"

  env             = var.env
  subscription_id = var.subscription_id
  tenant_id       = data.azurerm_client_config.current.tenant_id

  cert_manager_uami_client_id  = data.terraform_remote_state.infra.outputs.cert_manager_uami_client_id
  acme_email                   = var.acme_email
  dns_zone_name                = data.terraform_remote_state.infra.outputs.dns_zone_name
  dns_zone_resource_group_name = data.terraform_remote_state.infra.outputs.resource_group_name

  eso_uami_client_id = data.terraform_remote_state.infra.outputs.eso_uami_client_id
  kv_uri             = data.terraform_remote_state.infra.outputs.kv_uri
}
