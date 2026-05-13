# Backend configuration is supplied at 'terraform init' time via
# -backend-config=backend.hcl.  Uses a separate key in the dev container so
# this state is distinct from envs/dev/'s state.
terraform {
  backend "azurerm" {}
}
