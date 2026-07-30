# Backend configuration is supplied at 'terraform init' time via
# -backend-config=... flags (see ../../bootstrap/bootstrap-output.txt).
# Storage account / container / key are NOT committed.
terraform {
  backend "azurerm" {}
}
