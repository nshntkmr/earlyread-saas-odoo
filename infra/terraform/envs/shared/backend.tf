# Backend configuration is supplied at 'terraform init' time via
# -backend-config=backend.hcl.  State for the shared layer lives in its own
# container in the same storage account as dev/staging states.
terraform {
  backend "azurerm" {}
}
