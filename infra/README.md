# infra/

Azure infrastructure-as-code for the Earlyread SaaS platform.

## Layout

```
infra/
├── README.md                       (this file)
├── .gitignore                      (excludes tfstate, tfvars, .terraform/)
├── .gitattributes                  (forces LF on .sh / .tf / .tfvars / .hcl)
└── terraform/
    ├── bootstrap/                  (one-time state backend setup; not used this deployment)
    │   ├── README.md
    │   └── bootstrap.sh
    ├── modules/                    (reusable building blocks)
    │   ├── network/                (VNet, subnets, NAT gateway)        — M1
    │   ├── dns/                    (Azure public DNS zone)             — M1
    │   ├── postgresql/             (PG Flex + private DNS + VNet link) — M2
    │   ├── keyvault/               (KV + PE + private DNS + secrets)   — M2
    │   └── filestore/              (Storage + Files share + PE + DNS)  — M2
    └── envs/                       (per-environment instantiation)
        ├── dev/
        └── staging/
```

## What's deployed

### M1 — Foundation (shipped)

- Resource Groups: `earlyread-saas-tfstate-rg` (state) + `earlyread-saas-{dev,staging}-rg` (env)
- Virtual Networks (one per env, separate IP ranges)
- 4 subnets per VNet: `aks`, `pg` (delegated to PG Flex), `appgw`, `pe`
- NAT Gateway (one per env, fixed public IP for outbound)
- Azure DNS zones: `dev.earlyread.ai` and `staging.earlyread.ai` (apex stays on GoDaddy, NS records delegated)
- Terraform state backend (Azure Storage with lease lock)

### M2 — Data & secrets layer (this commit)

- **PostgreSQL Flexible Server** per env, VNet-injected into the delegated `pg` subnet
  - Dev: `B_Standard_B1ms` (1vC/2GB Burstable, 32 GB Premium SSD, 7-day backup retention)
  - Staging: `GP_Standard_D2ds_v5` (2vC/8GB General Purpose, 64 GB, 35-day retention, geo-redundant backup, built-in PgBouncer)
  - Both: PG 16, TLS required, single zone, public access disabled
  - Initial DB `posterra_dev` / `posterra_staging` (empty; M5 seeds schema)
- **Azure Key Vault** per env (`earlyread-saas-dev-kv`, `earlyread-saas-stg-kv`)
  - RBAC mode, soft-delete + purge-protection enabled, public-with-firewall (allow-list your IP only)
  - 6 seeded secrets: `pg-admin-password` (auto-gen), `jwt-secret` (auto-gen), `ch-password-prod`, `ai-api-key`, `ai-endpoint`, `ai-model` (last 4 are placeholders / static values; replace via portal before M5)
  - All secrets use `lifecycle.ignore_changes = [value]` so manual rotations don't get reverted
- **Azure Files Premium share** per env (100 GB)
  - Storage accounts `earlyreaddevfseread` / `earlyreadstgfseread`
  - Share name `odoo-filestore`, mounted at `/var/lib/odoo` in AKS pods in M5
- **3 Private DNS Zones per env**: `earlyread-<env>.postgres.database.azure.com`, `privatelink.vaultcore.azure.net`, `privatelink.file.core.windows.net`
- **2 Private Endpoints per env** (KV + Files; PG uses VNet injection not PE)

### Still ahead (M3+)

- AKS cluster + AGIC + cert-manager + ESO (External Secrets Operator) — **M3**
- TLS certs via cert-manager + Let's Encrypt — M3
- Odoo image (Docker) + ACR + Helm chart — M4
- First Odoo deployment + DB schema seed + tenant subdomain works — M5
- WAF flip + observability + alerts — M6
- pg_dump CronJob → Blob backup — M7
- k6 baseline against staging (architectural gate) — M9
- CI/CD (GitHub Actions) — M10
- Docs + runbooks — M11

## Naming convention

| Type | Pattern | Examples |
|---|---|---|
| Hyphen-allowed (RGs, VNets, NAT, subnets, KV, PG, PEs, DNS zones) | `earlyread-saas-<env>-<purpose>` | `earlyread-saas-dev-vnet`, `earlyread-saas-dev-pg`, `earlyread-saas-dev-kv` |
| No-hyphen (Storage accounts — Azure rule) | `earlyread<env>fs<suffix>` for files; `earlyreadtfstate<suffix>` for state | `earlyreaddevfseread`, `earlyreadstgfseread`, `earlyreadtfstateeread` |
| Public DNS zones (domain names) | `<env>.earlyread.ai` | `dev.earlyread.ai` |
| PG private DNS zone | `earlyread-<env>.postgres.database.azure.com` | `earlyread-dev.postgres.database.azure.com` |
| Privatelink DNS zones (per Azure-mandated suffix) | `privatelink.<service>.<domain>` | `privatelink.vaultcore.azure.net`, `privatelink.file.core.windows.net` |

**Staging gets `stg` as an abbreviation** in places where the full name would exceed Azure's 24-char limit (Key Vault, Storage account). Everywhere else: full `staging`.

## Prerequisites

- **Azure CLI** (`az --version` → 2.50+ recommended) — `winget install Microsoft.AzureCLI`
- **Terraform** (`terraform version` → 1.10+) — `winget install Hashicorp.Terraform`
- **Azure subscription** with HIPAA BAA in place
- **Service Principal** (via `az ad sp create-for-rbac`) with the following roles:
  - `Contributor` at subscription scope (creates RGs, VNets, PG, KV, Storage, etc.)
  - `User Access Administrator` at subscription scope (creates the M2 KV role assignment for itself)
  - `Storage Blob Data Contributor` at the `earlyread-saas-tfstate-rg` storage account (read/write tfstate blobs — optional if Storage Account Key Access is enabled)

Set these env vars for Terraform:
```powershell
$env:ARM_CLIENT_ID       = "<sp-application-id>"
$env:ARM_CLIENT_SECRET   = "<sp-secret>"
$env:ARM_TENANT_ID       = "<tenant-id>"
$env:ARM_SUBSCRIPTION_ID = "<subscription-id>"
```

## How to apply

### State backend (one-time)

Already provisioned manually for this deployment:
- RG: `earlyread-saas-tfstate-rg`
- Storage Account: `earlyreadtfstateeread`
- Containers: `dev`, `staging`

The script `bootstrap/bootstrap.sh` is retained as the canonical recipe for future re-provisioning or new environments.

### Apply dev

```powershell
cd infra\terraform\envs\dev
copy terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: fill in subscription_id; update allowed_ips if your IP changes

terraform init -backend-config=backend.hcl
terraform plan -out dev.tfplan
terraform apply dev.tfplan
```

After M1 apply outputs DNS nameservers, **add 4 NS records on `dev` host at GoDaddy** (see [M1 verification](#m1-validation) below).

### Apply staging

```powershell
cd ..\staging
copy terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: same subscription_id, same allowed_ips

terraform init -backend-config=backend.hcl
terraform plan -out staging.tfplan
terraform apply staging.tfplan
```

After M1 apply outputs DNS nameservers, **add 4 NS records on `staging` host at GoDaddy**.

## M1 Validation

```powershell
# DNS delegation propagated (after GoDaddy update)
nslookup -type=NS dev.earlyread.ai
nslookup -type=NS staging.earlyread.ai

# All M1 + M2 resource groups present
az group list --query "[?starts_with(name, 'earlyread-saas-')]" -o table
```

## M2 Validation

```powershell
# Key Vault — should show 6 seeded secrets
az keyvault secret list --vault-name earlyread-saas-dev-kv -o table
az keyvault secret list --vault-name earlyread-saas-stg-kv -o table

# PG server FQDN visible (resolves to private IP only from inside VNet)
terraform -chdir=infra\terraform\envs\dev output pg_fqdn
terraform -chdir=infra\terraform\envs\staging output pg_fqdn

# Storage accounts + Files share
az storage share list --account-name earlyreaddevfseread --auth-mode login -o table
az storage share list --account-name earlyreadstgfseread --auth-mode login -o table

# Private endpoints exist
az network private-endpoint list -g earlyread-saas-dev-rg -o table
az network private-endpoint list -g earlyread-saas-staging-rg -o table
```

## Cost estimate

| Item | Dev $/mo | Staging $/mo |
|---|---|---|
| Resource Groups, VNets, Subnets, DNS zones | 0 | 0 |
| NAT Gateway (compute + ~50 GB egress) | ~50 | ~50 |
| PG Flexible Server | ~15 | ~130 |
| Premium Files (100 GB) + Storage account | ~16 | ~16 |
| Key Vault | <1 | <1 |
| 2× Private Endpoints | ~15 | ~15 |
| 3× Private DNS zones | ~1.50 | ~1.50 |
| Public DNS zone | ~0.50 | ~0.50 |
| **Per-env subtotal** | **~$100** | **~$215** |

Plus state backend storage (<$1) and provider/data egress (~$5-10) shared.

**Combined M1 + M2 total: ~$320/mo** for both envs.

## Notes

- **All `.tfvars` files are gitignored.** Only `.tfvars.example` templates are committed. `backend.hcl` is committed (no secrets in it; just storage account name + container).
- **KV / Storage firewalls allow only your IP** (in `allowed_ips`) plus the `AzureServices` bypass. When your laptop IP changes, update `terraform.tfvars` and re-apply.
- **AKS pods (M3+) reach KV / Storage via the Private Endpoints**, not subnet service endpoints. This is intentional — service endpoints would require enabling `Microsoft.KeyVault` / `Microsoft.Storage` on the AKS subnet (which M1 didn't do, and PEs are the more secure forward-looking pattern). Resolution is transparent via the private DNS zones linked to each VNet.
- **`use_azuread_auth = true` in `backend.hcl`** is commented-out — would tighten state backend to RBAC-only (no shared keys). Switch to it once SP has `Storage Blob Data Contributor` on the state storage account.
- **PG password rotation**: managed via Key Vault. Set new value with `az keyvault secret set --vault-name <kv> --name pg-admin-password --value <new>`. Then `az postgres flexible-server update --resource-group <rg> --name <server> --admin-password <new>`. Terraform `lifecycle.ignore_changes` keeps it from reverting.
- **Replace placeholders before M5**: `ch-password-prod`, `ai-api-key`. Use portal or `az keyvault secret set`.
- **NSGs (firewall rules)** are still deferred to M3 — AKS and AppGw need workload-aware rules.
