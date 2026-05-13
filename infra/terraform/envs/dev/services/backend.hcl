# Terraform backend config for the DEV services layer (cert-manager + ESO).
# Uses a separate state key in the dev container so it doesn't collide with
# the infra-layer state (envs/dev/'s terraform.tfstate).

resource_group_name  = "earlyread-saas-tfstate-rg"
storage_account_name = "earlyreadtfstateeread"
container_name       = "dev"
key                  = "services.tfstate"
