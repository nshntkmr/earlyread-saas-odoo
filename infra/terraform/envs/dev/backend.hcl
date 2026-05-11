# Terraform remote-state backend config for the DEV environment.
#
# Usage:
#   terraform init -backend-config=backend.hcl
#   terraform init -reconfigure -backend-config=backend.hcl   # to re-init
#
# The values below are not secrets (storage-account name + container name
# are visible to anyone with Reader on the subscription), so this file is
# safe to commit.

resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "dev"
key                  = "terraform.tfstate"

# ─── Authentication mode ──────────────────────────────────────────────────────
#
# Current default: Terraform uses the active Service Principal's RBAC
# (Contributor at subscription level) to fetch the storage account access
# key via ARM, then uses that key to read/write state blobs. Works as long
# as the storage account has "Allow storage account key access" enabled
# (which is the Azure default).
#
# For tighter security (no key access at all), uncomment the line below and
# grant the SP 'Storage Blob Data Contributor' on the storage account:
#
#   az role assignment create \
#     --assignee <ARM_CLIENT_ID> \
#     --role "Storage Blob Data Contributor" \
#     --scope "/subscriptions/<SUB_ID>/resourceGroups/earlyread-saas-tfstate-rg/providers/Microsoft.Storage/storageAccounts/earlyreadtfstateeread"
#
# use_azuread_auth = true
