# Terraform remote-state backend config for the SHARED layer.
#
# Usage:
#   terraform init -backend-config=backend.hcl
#
# Pre-requisite: the 'shared' container must exist in the tfstate storage
# account.  Create it once with:
#
#   az storage container create \
#     --name shared \
#     --account-name earlyreadtfstateeread \
#     --auth-mode login

resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "shared"
key                  = "terraform.tfstate"
