# Backend configuration is supplied at 'terraform init' time via
# -backend-config=backend.hcl.  Uses a separate key in the prod container.
terraform {
  backend "azurerm" {}
}
