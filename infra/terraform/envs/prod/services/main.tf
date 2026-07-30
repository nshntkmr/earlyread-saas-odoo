# ─────────────────────────────────────────────────────────────────────────────
# PROD services layer — cluster-side services inside the prod AKS
#
# Applied AFTER envs/prod/ (which creates AKS, AppGw, UAMIs, KV, and the
# wildcard DNS record).
# ─────────────────────────────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

data "terraform_remote_state" "infra" {
  backend = "azurerm"
  config = {
    resource_group_name  = "earlyread-saas-tfstate-rg"
    storage_account_name = "earlyreadtfstateeread"
    container_name       = "prod"
    key                  = "terraform.tfstate"
  }
}

module "cluster_services" {
  source = "../../../modules/cluster_services"

  env             = var.env
  subscription_id = var.subscription_id
  tenant_id       = data.azurerm_client_config.current.tenant_id

  cert_manager_uami_client_id = data.terraform_remote_state.infra.outputs.cert_manager_uami_client_id
  acme_email                  = var.acme_email
  dns_zone_name               = data.terraform_remote_state.infra.outputs.dns_zone_name

  # ⚠ DIFFERS FROM dev/staging — do not "simplify" this to `resource_group_name`.
  # dev/staging create their own child zone inside the env RG, so there the zone
  # RG and the env RG are the same value. Prod consumes the PRE-EXISTING apex
  # zone, which lives in a different resource group entirely. cert-manager's
  # DNS-01 solver writes TXT challenge records into this RG — point it at prod's
  # RG and every certificate issuance for *.earlyread.ai fails.
  dns_zone_resource_group_name = data.terraform_remote_state.infra.outputs.dns_zone_resource_group_name

  eso_uami_client_id = data.terraform_remote_state.infra.outputs.eso_uami_client_id
  kv_uri             = data.terraform_remote_state.infra.outputs.kv_uri
}
