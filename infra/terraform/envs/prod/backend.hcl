# Terraform remote-state backend config for the PROD environment.
#
# Usage:
#   terraform init -backend-config=backend.hcl
#   terraform init -reconfigure -backend-config=backend.hcl   # to re-init
#
# The values below are not secrets (storage-account name + container name
# are visible to anyone with Reader on the subscription), so this file is
# safe to commit.
#
# NOTE: the tfstate storage account lives in eastus2. That is independent of
# where prod itself is deployed — state location does not constrain the
# resource location.

resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "prod"
key                  = "terraform.tfstate"

# ─── Authentication mode ──────────────────────────────────────────────────────
#
# Current default: Terraform uses the active Service Principal's RBAC
# (Contributor at subscription level) to fetch the storage account access
# key via ARM, then uses that key to read/write state blobs.
#
# For tighter security (no key access at all), uncomment the line below and
# grant the SP 'Storage Blob Data Contributor' on the storage account.
#
# use_azuread_auth = true
