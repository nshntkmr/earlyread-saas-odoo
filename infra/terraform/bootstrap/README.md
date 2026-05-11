# Bootstrap — one-time Terraform state backend setup

## Why this exists

Terraform's remote state lives in an Azure Storage account. But Terraform can't create that storage account using its own remote state (chicken-and-egg). So we bootstrap it once with `az` CLI commands.

After bootstrap runs successfully, **you never run it again** unless you're rebuilding from scratch.

## What it creates

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `earlyread-saas-tfstate-rg` | Holds the state backend; never deleted |
| Storage Account | `earlyreadtfstate<SUFFIX>` | Holds Terraform state blobs |
| Blob container | `dev` | Dev env's `terraform.tfstate` |
| Blob container | `staging` | Staging env's `terraform.tfstate` |

Storage account hardening:
- TLS 1.2 minimum
- Public blob access disabled
- Soft delete enabled (30 days) — recover from accidental state corruption
- Blob versioning enabled — every state-write keeps a prior version

## How to run

```bash
export SUBSCRIPTION_ID="<your-azure-subscription-id>"
export SUFFIX="eread"          # default; override if you want
export LOCATION="eastus2"      # default; override if you want
bash bootstrap.sh
```

The script:
1. Verifies you're logged in to the right subscription
2. Creates the RG (idempotent — re-run is safe)
3. Creates the storage account (idempotent — fails if name globally taken; pick another SUFFIX)
4. Configures hardening (TLS, public access, soft delete, versioning)
5. Creates the two containers (idempotent)
6. Writes `bootstrap-output.txt` with the `terraform init` commands you'll need

## Re-running

The script is idempotent — every step is `--exists-action ignore` or equivalent. Re-running is safe and a no-op.

## Recovery

If you lose the storage account (deleted, region failure, etc.):
1. Re-run `bootstrap.sh` with the same SUFFIX (will recreate empty)
2. State files are GONE unless you had off-storage backups
3. You'd need to `terraform import` every resource OR `terraform destroy` from a fresh apply

**Recommendation: enable Storage account-level geo-redundant backup once you have prod traffic** (M2 timeframe).
