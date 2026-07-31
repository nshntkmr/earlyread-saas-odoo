# Terraform backend config for the PROD services layer.
resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "prod"
key                  = "services.tfstate"
