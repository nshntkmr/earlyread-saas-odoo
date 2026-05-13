# Backend configuration is supplied at 'terraform init' time via
# -backend-config=backend.hcl.  Uses a separate key in the staging container.
terraform {
  backend "azurerm" {}
}
