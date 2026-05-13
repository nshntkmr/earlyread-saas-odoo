# Terraform backend config for the STAGING services layer.
resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "staging"
key                  = "services.tfstate"
