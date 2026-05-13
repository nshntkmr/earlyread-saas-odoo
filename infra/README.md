# infra/

Azure infrastructure-as-code for the Earlyread SaaS platform.

## Layout

```
infra/
├── README.md                       (this file)
├── .gitignore
├── .gitattributes
└── terraform/
    ├── bootstrap/                  (one-time state backend setup; not used this deployment)
    ├── modules/                    (reusable building blocks)
    │   ├── network/                (VNet, subnets, NAT gateway)              — M1
    │   ├── dns/                    (Azure public DNS zone)                   — M1
    │   ├── postgresql/             (PG Flex + private DNS + VNet link)       — M2
    │   ├── keyvault/               (KV + PE + private DNS + secrets)         — M2
    │   ├── filestore/              (Storage + Files share + PE + DNS)        — M2
    │   ├── acr/                    (Container Registry Standard, shared)     — M3
    │   ├── aks/                    (AKS cluster + node pools + AGIC add-on)  — M3
    │   ├── appgw/                  (App Gateway v2 + WAF v2 + public IP)     — M3
    │   ├── workload_identity/      (UAMIs + federated creds + role grants)   — M3
    │   └── cluster_services/       (cert-manager + ESO via Helm)             — M3
    └── envs/
        ├── shared/                 (apply ONCE; creates shared RG + ACR)     — M3
        ├── dev/                    (M1 + M2 + M3 infra layer)
        │   └── services/           (M3 cluster-side services; apply AFTER dev/)
        └── staging/                (M1 + M2 + M3 infra layer; prod-replica)
            └── services/           (M3 cluster-side services; apply AFTER staging/)
```

## What's deployed

### M1 — Foundation (shipped)

- Resource Groups: `earlyread-saas-tfstate-rg` (state) + `earlyread-saas-{dev,staging}-rg`
- Virtual Networks (one per env, separate IP ranges)
- 4 subnets per VNet: `aks`, `pg` (delegated to PG Flex), `appgw`, `pe`
- NAT Gateway (one per env, fixed public IP for outbound)
- Azure DNS zones: `dev.earlyread.ai` and `staging.earlyread.ai`
- Terraform state backend (Azure Storage with lease lock)

### M2 — Data & secrets layer (shipped)

- PostgreSQL Flexible Server per env, VNet-injected (dev `B1ms`, staging `D2ds_v5` with PgBouncer)
- Azure Key Vault per env with 6 seeded secrets, RBAC mode, private endpoint
- Azure Files Premium share per env (100 GB), private endpoint
- Private DNS zones: 3 per env (PG + KV + Files)

### M3 — Runtime layer (this commit)

**Shared layer** (in new RG `earlyread-saas-shared-rg`):
- Azure Container Registry `earlyreadsaasacreread` (Standard tier, AAD auth, no admin user)

**Per-env**:
- AKS cluster `earlyread-saas-{env}-aks` with **K8s 1.34.6**
  - **Dev**: system pool 2× `D4as_v5` (fixed), user pool 1-2× `D2as_v5`
  - **Staging**: system pool 2-3× `D4as_v5`, user pool 2-3× `D4as_v5` (prod-replica for 20-30 concurrent)
  - Azure CNI Overlay, Pod CIDR `100.64.0.0/16`
  - OIDC issuer + Workload Identity enabled
  - AGIC add-on (managed identity model)
  - Local accounts enabled — `az aks get-credentials --admin` works
- App Gateway v2 + WAF v2 (`Detection` mode initially), autoscale 1-10
- Wildcard DNS A record (`*.{env}.earlyread.ai` → App Gateway public IP)
- User-Assigned Managed Identities (no AAD apps):
  - `earlyread-saas-{env}-eso-id` → Key Vault Secrets User on env KV
  - `earlyread-saas-{env}-cert-id` → DNS Zone Contributor on env DNS zone
- Federated credentials linking each UAMI to its K8s ServiceAccount
- AGIC's managed identity granted Network Contributor on App Gateway + Reader on env RG
- AKS kubelet identity granted AcrPull on the shared ACR

**Per-env services layer** (deployed by `envs/{env}/services/` after infra layer):
- cert-manager Helm release with workload-identity wiring
- Let's Encrypt staging + production ClusterIssuers (DNS-01 via Azure DNS UAMI)
- External Secrets Operator Helm release with workload-identity wiring
- ClusterSecretStore pointing at the env's KV (`{env}-kv-store`)

### Still ahead (M4+)

- Odoo container image (`Dockerfile` + NGINX sidecar) → ACR push — M4
- Helm chart with portal/admin/cron pod roles + Ingress resources — M4
- First Odoo deployment in `odoo-{env}` namespace; first tenant subdomain works — M5
- WAF flip to Prevention + observability + alerts — M6
- pg_dump CronJob → Blob backup — M7
- k6 baseline against staging (architectural gate) — M9
- CI/CD (GitHub Actions) — M10
- Docs + runbooks — M11

## Naming convention

| Type | Pattern | Examples |
|---|---|---|
| Hyphen-allowed | `earlyread-saas-<env>-<purpose>` | `earlyread-saas-dev-aks`, `earlyread-saas-dev-appgw`, `earlyread-saas-dev-kv` |
| No-hyphen (Storage, ACR) | `earlyread<...>` | `earlyreadtfstateeread`, `earlyreaddevfseread`, `earlyreadsaasacreread` |
| Public DNS zones | `<env>.earlyread.ai` | `dev.earlyread.ai` |
| PG private DNS zone | `earlyread-<env>.postgres.database.azure.com` | `earlyread-dev.postgres.database.azure.com` |
| Privatelink DNS zones | `privatelink.<service>.<domain>` | `privatelink.vaultcore.azure.net` |
| UAMIs (M3) | `earlyread-saas-<env>-<service>-id` | `earlyread-saas-dev-eso-id`, `earlyread-saas-dev-cert-id` |

Staging uses `stg` abbreviation in places that hit Azure's 24-char limit (KV, Storage). Everywhere else: full `staging`.

## Prerequisites

- **Azure CLI** ≥ 2.50 — `winget install Microsoft.AzureCLI`
- **Terraform** ≥ 1.10 — `winget install Hashicorp.Terraform`
- **Azure subscription** with HIPAA BAA in place
- **Service Principal** with:
  - `Contributor` at subscription scope
  - `User Access Administrator` at subscription scope (for role assignments in M2 and M3)

Set these env vars for Terraform:
```powershell
$env:ARM_CLIENT_ID       = "<sp-application-id>"
$env:ARM_CLIENT_SECRET   = "<sp-secret>"
$env:ARM_TENANT_ID       = "<tenant-id>"
$env:ARM_SUBSCRIPTION_ID = "<subscription-id>"
```

## How to apply (one-time + per-env)

### Step 0 — Create the `shared` blob container (one-time)

```powershell
az storage container create `
  --name shared `
  --account-name earlyreadtfstateeread `
  --auth-mode login
```

### Step 1 — Apply the shared layer (one-time, creates ACR)

```powershell
cd infra\terraform\envs\shared
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars      # fill in subscription_id

terraform init -backend-config=backend.hcl
terraform plan -out shared.tfplan
terraform apply shared.tfplan
```

Creates `earlyread-saas-shared-rg` + `earlyreadsaasacreread`. After this, both dev and staging can reference the ACR via data source.

### Step 2 — Apply dev infra layer

```powershell
cd ..\dev
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars      # fill in subscription_id + allowed_ips

terraform init -upgrade -backend-config=backend.hcl
terraform plan -out dev.tfplan
terraform apply dev.tfplan    # ~15-20 min (AKS creation is the long pole)
```

Apply outputs:
- DNS nameservers — add as NS records on `dev` host at GoDaddy (already done in M1; only needed for fresh deploys)
- App Gateway public IP — already targeted by the wildcard A record automatically
- NAT public IP — already known: `20.110.126.251`

### Step 3 — Apply dev services layer (cluster-side: cert-manager + ESO)

```powershell
cd services
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars

terraform init -backend-config=backend.hcl
terraform plan -out dev-services.tfplan
terraform apply dev-services.tfplan    # ~3-5 min (Helm releases + K8s manifests)
```

### Step 4 — Repeat for staging (infra + services)

```powershell
cd ..\..\staging
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars

terraform init -upgrade -backend-config=backend.hcl
terraform plan -out staging.tfplan
terraform apply staging.tfplan

cd services
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars

terraform init -backend-config=backend.hcl
terraform plan -out staging-services.tfplan
terraform apply staging-services.tfplan
```

## Validation drills

### M1 + M2 (still apply)

```powershell
nslookup -type=NS dev.earlyread.ai
nslookup -type=NS staging.earlyread.ai
az group list --query "[?starts_with(name, 'earlyread-saas-')]" -o table
az keyvault secret list --vault-name earlyread-saas-dev-kv -o table
```

### M3 — AKS reachability + cluster services

```powershell
# Get cluster admin kubeconfig (--admin bypasses Azure RBAC)
az aks get-credentials --resource-group earlyread-saas-dev-rg `
                       --name earlyread-saas-dev-aks --admin

# 4 nodes Ready (2 system + 2 user for staging; 2 system + 1-2 user for dev)
kubectl get nodes

# Cluster-side services running
kubectl get pods -n kube-system
kubectl get pods -n cert-manager
kubectl get pods -n external-secrets-system

# ClusterIssuers ready
kubectl get clusterissuer
# letsencrypt-staging   READY=True
# letsencrypt-prod      READY=True

# ClusterSecretStore ready
kubectl get clustersecretstore
# dev-kv-store          READY=True

# App Gateway visible from outside (returns 404 — no Ingress yet, that's M5)
$ip = az network public-ip show -g earlyread-saas-dev-rg -n earlyread-saas-dev-appgw-pip --query ipAddress -o tsv
curl -I http://$ip

# Wildcard DNS resolves
nslookup posterra.dev.earlyread.ai
# Should return the App Gateway public IP

# ACR login server resolves
az acr show -n earlyreadsaasacreread --query loginServer -o tsv
# earlyreadsaasacreread.azurecr.io
```

### Smoke test — synthetic ExternalSecret resolves

This confirms ESO + workload identity + KV chain works end-to-end before M5.

```powershell
# Create a test ExternalSecret that pulls 'jwt-secret' from KV
kubectl create namespace test
kubectl apply -f - <<EOF
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: test-jwt-secret
  namespace: test
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: dev-kv-store
    kind: ClusterSecretStore
  target:
    name: test-jwt-secret
  data:
    - secretKey: jwt
      remoteRef:
        key: jwt-secret
EOF

# Wait a moment, then verify
kubectl get externalsecret -n test test-jwt-secret
# READY=True; SECRETSTOREREF=dev-kv-store

kubectl get secret -n test test-jwt-secret -o jsonpath='{.data.jwt}' | base64 -d
# Should print the JWT secret from KV

# Cleanup
kubectl delete namespace test
```

## Cost estimate

| Component | Dev $/mo | Staging $/mo |
|---|---|---|
| M1 — RGs, VNets, NAT, DNS zone | ~50 | ~50 |
| M2 — PG, KV, Files, PEs | ~50 | ~165 |
| M3 — AKS system pool (D4as_v5 × 2) | ~140 | ~140-210 |
| M3 — AKS user pool | ~70 (D2 × 1-2) | ~280-420 (D4 × 2-3) |
| M3 — App Gateway v2 + WAF v2 | ~255 | ~255 |
| M3 — Container Insights / Log Analytics | ~15 | ~30 |
| **Per-env subtotal (M1+M2+M3)** | **~$580** | **~$920-1,130** |

Plus shared: ACR Standard ~$20/mo; state backend < $1/mo.

**Combined running total after M3: ~$1,520-1,730/mo** for both envs.

## Notes

### M3-specific gotchas

- **AKS system pool minimums** (hard Azure rule): ≥ 2 nodes AND ≥ 4 vCPU SKU. Using D4as_v5 to comply.
- **AKS uses local accounts** for `--admin` kubectl access. To lock down: set `local_account_disabled = true` in the aks module (post-M9 when prod-ready).
- **AGIC writes App Gateway routing rules, NOT DNS records**. Our wildcard `*.<env>.earlyread.ai` A record (managed by Terraform) handles DNS for all tenant subdomains uniformly.
- **Apply order is strict**: shared → env infra → env services. Cannot apply services before AKS exists.
- **Two-phase apply per env** avoids the chicken-and-egg of helm/kubernetes providers needing a kubeconfig that doesn't exist until AKS is created.
- **Let's Encrypt staging issuer first** — first cert via `letsencrypt-staging` (rate-limit-friendly); flip to `letsencrypt-prod` in M5 after end-to-end verification.
- **WAF starts in Detection mode** — logs but doesn't block. Flip to Prevention in M6 after 2 weeks of baseline.

### M3-specific costs

- AKS control plane: free (paid SLA tier exists; not using)
- AKS nodes: VM compute + Premium SSD OS disks (~$5/disk)
- Container Insights (Log Analytics): ingest-billed; default 30 days retention
- ACR Standard: $20/mo, 10 GB storage included
- ACR Standard limitations: NO private endpoint, NO geo-replication (Premium-only). Acceptable for non-prod; upgrade before prod.

### Operational

- All `.tfvars` files are gitignored. Only `.tfvars.example` templates are committed.
- `backend.hcl` is committed (no secrets in it; just storage account name + container).
- KV / Storage firewalls allow only your IP (in `allowed_ips`) plus `AzureServices` bypass.
- AKS pods (M3+) reach KV / Storage via the Private Endpoints, not subnet service endpoints (we explicitly chose PE path in M2).
- PG password rotation managed via Key Vault — `lifecycle.ignore_changes` keeps Terraform from reverting manual updates.
- Replace `REPLACE_ME` placeholders in KV before M5 (`ch-password-prod`, `ai-api-key`).
- NSGs (firewall rules at subnet level) are deferred to M6 (AKS + AppGw need workload-aware rules; deferred so dev can iterate freely first).

### ACR upgrade trigger

ACR Standard is sufficient for M3-M4 non-prod. Upgrade to Premium before:
- Prod deployment (requires private endpoint for ACR pulls)
- Geo-replication (DR posture)
- Customer-managed encryption keys
