# infra/

Azure infrastructure-as-code for the Earlyread SaaS platform.

## Layout

```
infra/
├── README.md                       (this file)
├── .gitignore                      (excludes tfstate, tfvars, .terraform/)
└── terraform/
    ├── bootstrap/                  (one-time state backend setup)
    │   ├── README.md
    │   └── bootstrap.sh
    ├── modules/                    (reusable building blocks)
    │   ├── network/                (VNet, subnets, NAT gateway)
    │   └── dns/                    (Azure DNS zone)
    └── envs/                       (per-environment instantiation)
        ├── dev/
        └── staging/
```

## What's in M1 (this commit)

Per the parent plan ([Phase 1a M1](../.claude/plans/c-users-nisha-claude-plans-phase-4-data-delightful-wombat.md)):

- Resource Groups: `earlyread-saas-tfstate-rg` (state) + `earlyread-saas-{dev,staging}-rg` (env)
- Virtual Networks (one per env, separate IP ranges)
- 4 subnets per VNet: `aks`, `pg`, `appgw`, `pe`
- NAT Gateway (one per env, fixed public IP for outbound)
- Azure DNS zones: `dev.earlyread.ai` and `staging.earlyread.ai` (apex stays on GoDaddy)
- Terraform state backend (Azure Storage with lease lock)

**M1 does NOT yet create:** AKS, PostgreSQL, Key Vault, Azure Files, App Gateway, TLS certs, Posterra. Those land in M2-M5.

## Naming convention

| Type | Pattern | Examples |
|---|---|---|
| Hyphen-allowed (RGs, VNets, NAT, subnets, etc.) | `earlyread-saas-<env>-<purpose>` | `earlyread-saas-dev-vnet`, `earlyread-saas-dev-natgw` |
| No-hyphen (Storage, ACR — Azure rule) | `earlyread<purpose><suffix>` | `earlyreadtfstateeread` |
| DNS zones (domain names) | `<env>.earlyread.ai` | `dev.earlyread.ai` |

## Prerequisites

- **Azure CLI** (`az --version` → 2.50+ recommended) — `winget install Microsoft.AzureCLI` on Windows
- **Terraform** (`terraform version` → 1.10+) — `winget install Hashicorp.Terraform` on Windows
- **Azure subscription** with HIPAA BAA in place
- `az login` against the target subscription
- Subscription-level `Owner` or `Contributor` on the subscription (needed to create RGs, VNets, DNS zones)

## How to apply (first-time, full sequence)

### Step 1 — Bootstrap the Terraform state backend (one time, ever)

```bash
cd infra/terraform/bootstrap
export SUBSCRIPTION_ID="<your-subscription-id>"
export SUFFIX="eread"   # or override to your preference
export LOCATION="eastus2"
bash bootstrap.sh
```

The script:
1. Creates `earlyread-saas-tfstate-rg` in your chosen region
2. Creates Storage account `earlyreadtfstate${SUFFIX}` with HTTPS-only, no public access, soft-delete + versioning
3. Creates two blob containers (`dev`, `staging`)
4. Prints the `terraform init` command for each env

Save the output — you'll paste those `-backend-config=...` flags into the next step.

### Step 2 — Initialize and apply dev

```bash
cd ../envs/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars and fill in subscription_id

terraform init \
  -backend-config=resource_group_name=earlyread-saas-tfstate-rg \
  -backend-config=storage_account_name=earlyreadtfstateeread \
  -backend-config=container_name=dev \
  -backend-config=key=terraform.tfstate

terraform plan -out=dev.tfplan       # review what's going to be created
terraform apply dev.tfplan
```

The `terraform apply` outputs four DNS nameservers like `ns1-04.azure-dns.com.`. **Add these as NS records at GoDaddy** on the `dev` host of `earlyread.ai`. Same for staging.

### Step 3 — Repeat for staging

```bash
cd ../staging
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

terraform init \
  -backend-config=resource_group_name=earlyread-saas-tfstate-rg \
  -backend-config=storage_account_name=earlyreadtfstateeread \
  -backend-config=container_name=staging \
  -backend-config=key=terraform.tfstate

terraform plan -out=staging.tfplan
terraform apply staging.tfplan
```

### Step 4 — Verify

```bash
# DNS zone should resolve (NXDOMAIN is correct — zone exists, no records yet)
dig +short test.dev.earlyread.ai
dig NS dev.earlyread.ai

# Check resource groups
az group list -o table | grep earlyread-saas
```

In the Azure portal you should see:

- 3 RGs: `earlyread-saas-tfstate-rg`, `earlyread-saas-dev-rg`, `earlyread-saas-staging-rg`
- 2 VNets, 8 subnets, 2 NAT Gateways, 2 public IPs, 2 DNS zones
- 1 Storage account (in tfstate RG) with 2 containers

## Cost estimate after M1

| Item | $/mo |
|---|---|
| Resource Groups, VNets, Subnets | 0 |
| NAT Gateway (2× — one per env, ~50 GB egress each) | ~100 |
| Azure DNS zones (2× $0.50) | ~1 |
| TF state Storage account | <1 |
| **M1 monthly subtotal** | **~$102** |

Big-ticket compute (PG, AKS, App Gateway) lands in M2/M3.

## Notes

- **All `.tfvars` files are gitignored.** Only `.tfvars.example` templates are committed.
- **State file is lease-locked.** Two simultaneous `terraform apply` runs will fail loudly rather than corrupt state.
- **NSGs (firewall rules)** are deferred to M3 because AKS and App Gateway need workload-aware rules. M1 leaves subnets without NSGs attached.
- **`pg` subnet is pre-delegated to `Microsoft.DBforPostgreSQL/flexibleServers`** so M2 can drop a PG server in without an extra subnet update.
