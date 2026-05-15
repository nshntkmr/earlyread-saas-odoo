# Phase 1a — Azure Deployment Runbook

End-to-end record of the Phase 1a deployment of the Earlyread SaaS platform
(Odoo 19 + React + PostgreSQL) to Azure AKS. Covers dev (fully deployed) and
staging (M1+M2 applied, M3+ parked on vCPU quota). Use this doc to:

- Understand what was built and why each layer exists
- Re-deploy from scratch (DR rebuild, new region, new env)
- Onboard a new contributor to the infra
- Pick up staging M3+ when the vCPU quota arrives

Last updated: end of Phase 1a M5 (commit `41564a5`, May 2026).

---

## Status

| Milestone | dev | staging | Notes |
|---|---|---|---|
| M1 — Networking + DNS | ✅ done | ✅ done | NS records propagated at GoDaddy for both zones |
| M2 — PG + KV + Filestore | ✅ done | ⚠️ needs re-apply | M4b added 3 KV secrets (`odoo-admin-password`, `filestore-account-name`, `filestore-account-key`); staging needs `terraform apply` to seed them. No quota dependency — can run any time. |
| M3 — AKS + AppGw + cert-manager + ESO + workload identity | ✅ done | ⛔ parked | Staging blocked on Total Regional vCPU quota (28 → ~50 needed). Microsoft denied the first quota request; case still open. |
| M4a — Docker image | ✅ done | n/a | Image is shared across envs (one ACR in `earlyread-saas-shared-rg`). Current tag: `41564a5`. |
| M4b — Helm chart | ✅ done | n/a | Same chart serves both envs via per-env `values.<env>.yaml`. |
| M5 — `helm install` on AKS | ✅ done | ⛔ parked on M3 | Dev URL: `https://posterra.dev.earlyread.ai`. Browser-trusted TLS via `letsencrypt-prod`. |

---

## Quick reference (dev)

| Thing | Value |
|---|---|
| Tenant URL | `https://posterra.dev.earlyread.ai` |
| Admin URL | `https://admin.dev.earlyread.ai` |
| AppGw public IP | `172.177.201.128` |
| NAT Gateway public IP (outbound) | `20.110.126.251` (allow-list this on ClickHouse Cloud + any third-party API that filters by IP) |
| Resource Group | `earlyread-saas-dev-rg` |
| Key Vault | `earlyread-saas-dev-kv` |
| PG server | `earlyread-saas-dev-pg.postgres.database.azure.com` (port 5432, private) |
| Storage account (filestore) | `earlyreaddevfseread` (share `odoo-filestore`) |
| AKS cluster | `earlyread-saas-dev-aks` |
| Container Registry | `earlyreadsaasacreread.azurecr.io` (in shared RG) |
| Helm release | `posterra` in namespace `odoo-dev` |
| Image tag | `41564a5` |

```powershell
# Connect kubectl to dev AKS
az aks get-credentials -g earlyread-saas-dev-rg -n earlyread-saas-dev-aks --admin --overwrite-existing

# Get the Odoo admin password (for first browser login)
$kv = "earlyread-saas-dev-kv"
az keyvault secret show --vault-name $kv --name odoo-admin-password --query value -o tsv
```

---

## Architecture — dev

### 1. Network topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Azure Subscription                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Resource Group: earlyread-saas-shared-rg                            │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │  ACR: earlyreadsaasacreread                                 │     │   │
│  │  │  Image: odoo:41564a5  (Odoo 19 + posterra_portal +          │     │   │
│  │  │         dashboard_builder + clickhouse-connect + anthropic) │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                ▲                                            │
│                                │ AcrPull (granted to AKS kubelet identity)  │
│  ┌─────────────────────────────┴───────────────────────────────────────┐   │
│  │  Resource Group: earlyread-saas-dev-rg                               │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │  VNet: earlyread-saas-dev-vnet  (10.10.0.0/16)              │     │   │
│  │  │                                                              │     │   │
│  │  │   ┌─────────────────┐  ┌──────────────────────┐            │     │   │
│  │  │   │ aks-snet         │  │ pg-snet               │            │     │   │
│  │  │   │ 10.10.0.0/22     │  │ 10.10.4.0/24          │            │     │   │
│  │  │   │ AKS nodes        │  │ delegated to          │            │     │   │
│  │  │   │ Pod CIDR (CNI    │  │ Microsoft.DBforPG     │            │     │   │
│  │  │   │ Overlay)         │  │ → PG Flex private     │            │     │   │
│  │  │   │ 100.64.0.0/16    │  │   access              │            │     │   │
│  │  │   └─────────────────┘  └──────────────────────┘            │     │   │
│  │  │                                                              │     │   │
│  │  │   ┌─────────────────┐  ┌──────────────────────┐            │     │   │
│  │  │   │ appgw-snet       │  │ pe-snet               │            │     │   │
│  │  │   │ 10.10.5.0/24     │  │ 10.10.6.0/24          │            │     │   │
│  │  │   │ App Gateway v2   │  │ Private Endpoints     │            │     │   │
│  │  │   │ Standard_v2      │  │ for KV + Storage      │            │     │   │
│  │  │   └─────────────────┘  └──────────────────────┘            │     │   │
│  │  │                                                              │     │   │
│  │  │   Private DNS zones (linked to VNet):                       │     │   │
│  │  │     • privatelink.vaultcore.azure.net      (KV)            │     │   │
│  │  │     • privatelink.file.core.windows.net    (Storage)       │     │   │
│  │  │     • privatelink.postgres.database.azure.com (PG Flex)    │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  │                                                                       │   │
│  │   Public IPs:                                                         │   │
│  │     • AppGw PIP: 172.177.201.128 (HTTPS in)                          │   │
│  │     • NAT GW PIP: 20.110.126.251 (egress out)                        │   │
│  │                                                                       │   │
│  │   Resources:                                                          │   │
│  │     • Key Vault: earlyread-saas-dev-kv     (PE in pe-snet, 9 secrets)│   │
│  │     • Storage:   earlyreaddevfseread       (PE in pe-snet, 1 share)  │   │
│  │     • PG Flex:   earlyread-saas-dev-pg     (private access, pg-snet) │   │
│  │     • AKS:       earlyread-saas-dev-aks    (D4as_v4 system + D2s_v4) │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Azure DNS Zone: dev.earlyread.ai                                    │   │
│  │    • NS records delegated from GoDaddy (manual one-time step at M1)  │   │
│  │    • Wildcard A: *.dev.earlyread.ai → 172.177.201.128 (AppGw PIP)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Request path — `https://posterra.dev.earlyread.ai/web/login`

```
Browser
  │ HTTPS request, SNI = posterra.dev.earlyread.ai
  ▼
Azure DNS resolves → 172.177.201.128
  ▼
App Gateway v2 (earlyread-saas-dev-appgw)
  │ • TLS terminated using posterra-wildcard-tls cert (from cert-manager)
  │ • Wildcard host listener matches *.dev.earlyread.ai
  │ • Routes to backend pool = AKS pod IPs (managed by AGIC)
  ▼
NGINX sidecar in posterra-combined pod (port 8080)
  │ • Static-asset paths served directly from shared emptyDir volume
  │ • Everything else proxied to localhost:8069
  ▼
Odoo container in same pod (port 8069)
  │ • App resolver reads "posterra" from host header
  │ • Looks up saas.app.app_key='posterra'
  │ • Queries DB via PG Flex private endpoint (10.10.4.x)
  │ • Reads attachments from /var/lib/odoo (Azure Files share)
  ▼
HTTP response → back through NGINX → AppGw → browser
```

### 3. Cluster control plane — what wires the request path together

```
AKS Cluster (earlyread-saas-dev-aks)
│
├── Namespace: kube-system
│   ├── AGIC controller (programs App Gateway from Ingress resources)
│   │   └── identity: AKS add-on managed identity
│   │       NEEDS Network Contributor on appgw-snet (see Known Gaps #1)
│   ├── CoreDNS, kube-proxy, etc. (standard AKS system pods)
│
├── Namespace: cert-manager  (installed by M3 services layer)
│   ├── cert-manager controller (issues TLS certs from letsencrypt)
│   │   └── identity: cert-manager UAMI (DNS Zone Contributor on dev.earlyread.ai)
│
├── Namespace: external-secrets  (installed by M3 services layer)
│   ├── external-secrets controller (syncs KV → K8s Secrets)
│   │   └── identity: ESO UAMI (Key Vault Secrets User on KV)
│
└── Namespace: odoo-dev  (created by helm install at M5)
    ├── ClusterSecretStore: dev-kv-store      → points at KV via ESO UAMI
    ├── ClusterIssuer: letsencrypt-prod        → DNS-01 solver via cert-manager UAMI
    │
    ├── ServiceAccount: posterra              (plain SA, no Azure perms)
    ├── ConfigMap: posterra-nginx              (nginx.conf for the sidecar)
    │
    ├── ExternalSecret: odoo-secrets           → Secret: odoo-secrets (7 keys:
    │   PG_PASSWORD, ODOO_ADMIN_PASSWORD, POSTERRA_JWT_SECRET,
    │   POSTERRA_CH_PASSWORD_PROD, POSTERRA_AI_API_KEY/ENDPOINT/MODEL)
    │
    ├── ExternalSecret: azure-files-secret     → Secret: azure-files-secret (2 keys:
    │   azurestorageaccountname, azurestorageaccountkey)
    │
    ├── PV: posterra-filestore-odoo-dev        (CSI file.csi.azure.com, Retain)
    ├── PVC: posterra-filestore                 (Bound to PV, RWX, 100Gi)
    │
    ├── Deployment: posterra-combined           (replicas=1, Recreate strategy)
    │   Pod template:
    │     • initContainer copy-static (copies addon static/ to shared emptyDir)
    │     • Container odoo (port 8069, mounts /var/lib/odoo from PVC)
    │     • Container nginx (port 8080, mounts /etc/nginx/nginx.conf from CM)
    │
    ├── Service: posterra-combined              (ClusterIP, port 8080 → nginx)
    ├── Ingress: posterra                       (AGIC; *.dev.earlyread.ai → service)
    ├── Certificate: posterra-wildcard-tls     (issued by letsencrypt-prod)
    └── Secret: posterra-wildcard-tls           (TLS pair, created by cert-manager)
```

---

## What was built — dev (per milestone, with commands)

All Terraform commands run from `C:\Users\nisha\Odoo_Dev`. SP env vars
(`ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`)
must be exported in the shell. Terraform state lives in Azure Storage backed
by `infra/terraform/envs/<env>/backend.hcl`.

### M0 — Shared (one-time, before any env)

Created the shared resource group + Container Registry that both dev and
staging use. Run once per subscription.

```powershell
cd infra/terraform/envs/shared
terraform init -backend-config=backend.hcl
terraform plan -out=shared.tfplan
terraform apply shared.tfplan
# Creates: earlyread-saas-shared-rg + ACR earlyreadsaasacreread
```

### M1 — Networking + DNS

Created the VNet, four subnets, NAT Gateway, and Azure DNS zone for dev.

```powershell
cd infra/terraform/envs/dev
terraform init -backend-config=backend.hcl
$ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
$env:TF_VAR_allowed_ips = '["' + $ip + '"]'
terraform plan -out=dev.tfplan
terraform apply dev.tfplan
```

**Manual step (one-time)**: at GoDaddy, add the four NS records from
`terraform output -json dns_zone_nameservers` as NS records on host `dev`
under `earlyread.ai`. Wait 15-60 min for propagation, then verify:

```powershell
nslookup -type=NS dev.earlyread.ai
# Expect the four ns1-04.azure-dns.* records
```

### M2 — Data plane + secrets

Provisioned PostgreSQL Flexible Server (private access into pg-snet),
Key Vault (private endpoint into pe-snet, public endpoint with IP allow-list
for Terraform-from-laptop seeding), and Azure Files share (private endpoint
in pe-snet).

```powershell
cd infra/terraform/envs/dev
$ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
$env:TF_VAR_allowed_ips = '["' + $ip + '"]'
terraform plan -out=dev.tfplan
terraform apply dev.tfplan
```

After apply, populate the placeholder secrets manually (KV module has
`lifecycle.ignore_changes = [value]` so manual values stick across re-applies):

```powershell
$kv = "earlyread-saas-dev-kv"

# ClickHouse password (the same env var name your CH cluster uses)
az keyvault secret set --vault-name $kv --name ch-password-prod --value "<real-ch-password>"

# Anthropic API key for the AI SQL Assistant
az keyvault secret set --vault-name $kv --name ai-api-key --value "<real-anthropic-key>"
```

### M3 — Cluster + Ingress + cert-manager + ESO

Two Terraform layers because M3 introduces Kubernetes-side resources that
need the cluster to exist first.

#### M3 infra (azurerm provider only): AKS + AppGw + workload identity

```powershell
cd infra/terraform/envs/dev
$ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
$env:TF_VAR_allowed_ips = '["' + $ip + '"]'
terraform plan -out=dev.tfplan
terraform apply dev.tfplan
```

Notes:
- AKS uses `D4as_v4` (system pool) + `D2s_v4` (user pool). v5 SKUs were the
  original target but eastus2 quota for `D4as_v5` is 0 and Microsoft denied
  the quota request. v4 has 10-vCPU regional quota out of the box.
- App Gateway is `Standard_v2` (no WAF). Variable `appgw_sku` lets you flip
  to `WAF_v2` later for prod without code change.
- Workload Identity creates two UAMIs:
  - **ESO UAMI** with `Key Vault Secrets User` on the KV
  - **cert-manager UAMI** with `DNS Zone Contributor` on the dev DNS zone
  Federated credentials bind these UAMIs to the K8s ServiceAccounts
  `external-secrets/external-secrets` and `cert-manager/cert-manager`.

#### M3 services (kubernetes + helm + kubectl providers): cert-manager, ESO, ClusterIssuer, ClusterSecretStore

```powershell
cd infra/terraform/envs/dev/services
terraform init -backend-config=backend.hcl
terraform plan -out=dev-services.tfplan
terraform apply dev-services.tfplan
```

Installs:
- cert-manager (Helm chart from Jetstack)
- external-secrets (Helm chart from external-secrets.io)
- `ClusterIssuer letsencrypt-staging` (DNS-01 via cert-manager UAMI)
- `ClusterIssuer letsencrypt-prod` (same, prod issuer)
- `ClusterSecretStore dev-kv-store` (points at the dev KV via ESO UAMI)

**Manual step (one-time per env)**: grant the AGIC managed identity
`Network Contributor` on the AppGw subnet. Without this, AGIC can update the
HTTP listener on the AppGw (port 80) but fails when adding the HTTPS listener
(port 443) because that requires `Microsoft.Network/virtualNetworks/subnets/join/action`.
See [Known Gaps](#known-gaps--manual-workarounds) for the canonical fix.

```powershell
$agicObjectId = az aks show -g earlyread-saas-dev-rg -n earlyread-saas-dev-aks `
  --query "addonProfiles.ingressApplicationGateway.identity.objectId" -o tsv
$subnetId = az network vnet subnet show -g earlyread-saas-dev-rg `
  --vnet-name earlyread-saas-dev-vnet -n earlyread-saas-dev-appgw-snet `
  --query id -o tsv
az role assignment create `
  --assignee-object-id $agicObjectId `
  --assignee-principal-type ServicePrincipal `
  --role "Network Contributor" `
  --scope $subnetId
```

### M4a — Docker image

Builds the Odoo image with both addons + Python deps and pushes to the
shared ACR. Run from the project root so `.dockerignore` correctly excludes
`.claude/`, `.git/`, `infra/terraform/`, `**/node_modules`, etc.

```powershell
cd C:\Users\nisha\Odoo_Dev
$tag = git rev-parse --short HEAD
az acr build --registry earlyreadsaasacreread --image "odoo:$tag" .
# Verify
az acr repository show --name earlyreadsaasacreread --image "odoo:$tag"
```

The image:
- Base: `odoo:19.0`
- Adds: `clickhouse-connect`, `anthropic` (PyPI), `gettext-base`, `postgresql-client` (apt)
- Copies: `posterra_portal/` and `dashboard_builder/` to `/mnt/extra-addons/`
- Custom entrypoint waits for PG (`pg_isready`), renders `/tmp/odoo.conf` from
  the baked-in template via `envsubst`, then `exec odoo -c /tmp/odoo.conf`

### M4b — Helm chart + KV secret additions

Two changes in one logical milestone:

**Chart** at [`infra/helm/posterra/`](../../infra/helm/posterra/):
- `values.yaml` — common defaults
- `values.dev.yaml` — combined-mode (one pod runs portal+admin+cron)
- `values.staging.yaml` — split mode (separate portal/admin/cron Deployments)
- Templates render the Deployment, NGINX-sidecar Service, AGIC Ingress,
  cert-manager-driven Certificate, ExternalSecrets, static PV+PVC, init Job
- `init.mode: install` for first deploy (runs `odoo -i ...`); flip to
  `upgrade` after first install (runs `odoo -u ...` for migrations)

**Terraform KV additions** in `envs/dev/main.tf`:
- `random_password.odoo_admin` (32-char password, `_` and `-` specials only)
- KV secret `odoo-admin-password` (from random_password)
- KV secret `filestore-account-name` (from `var.filestore_storage_name`)
- KV secret `filestore-account-key` (placeholder `REPLACE_ME`)

Apply:

```powershell
cd infra/terraform/envs/dev
$ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
$env:TF_VAR_allowed_ips = '["' + $ip + '"]'
terraform plan -out=dev.tfplan
terraform apply dev.tfplan

# Replace the filestore-account-key placeholder with the real key
$kv = "earlyread-saas-dev-kv"
$rg = "earlyread-saas-dev-rg"
$sa = "earlyreaddevfseread"
$key = az storage account keys list --account-name $sa --resource-group $rg --query "[0].value" -o tsv
az keyvault secret set --vault-name $kv --name filestore-account-key --value $key | Out-Null
```

### M5 — `helm install` on AKS

The integration test that proves M1-M4 work together.

```powershell
cd C:\Users\nisha\Odoo_Dev

# Pre-flight (fail fast on issues)
az aks get-credentials -g earlyread-saas-dev-rg -n earlyread-saas-dev-aks --admin --overwrite-existing
kubectl get pods -A -l app.kubernetes.io/name=external-secrets   # ESO running
kubectl get pods -A -l app.kubernetes.io/instance=cert-manager    # cert-manager running
kubectl get clustersecretstore dev-kv-store                       # Ready=True
kubectl get clusterissuer letsencrypt-staging                     # Ready=True

# Validate the chart renders before touching the cluster
helm lint infra/helm/posterra -f infra/helm/posterra/values.dev.yaml

# Install — CRITICAL: --timeout 15m, NO --wait
# (--wait deadlocks because Helm would block on Deployment readiness, which
#  needs schema, which only runs in the post-install hook)
helm install posterra infra/helm/posterra `
  -n odoo-dev --create-namespace `
  -f infra/helm/posterra/values.dev.yaml `
  --timeout 15m
```

#### Verification ladder

```powershell
kubectl get externalsecret -n odoo-dev          # both Ready=True
kubectl get secret odoo-secrets azure-files-secret -n odoo-dev
kubectl get pvc -n odoo-dev                      # posterra-filestore Bound
kubectl get jobs -n odoo-dev                     # posterra-init-1 Completed 1/1
kubectl get pods -n odoo-dev                     # posterra-combined-... Ready 2/2
kubectl get certificate -n odoo-dev              # posterra-wildcard-tls READY=True
kubectl get ingress -n odoo-dev                  # ADDRESS = AppGw IP
curl.exe -kI https://posterra.dev.earlyread.ai/web/login   # HTTP 200 (-k while on staging issuer)
```

#### Flip to letsencrypt-prod for browser-trusted certs

After staging-issuer flow is verified, edit `values.dev.yaml`:

```diff
 certManager:
-  clusterIssuer: letsencrypt-staging
+  clusterIssuer: letsencrypt-prod
```

```powershell
helm upgrade posterra infra/helm/posterra `
  -n odoo-dev `
  -f infra/helm/posterra/values.dev.yaml `
  --timeout 5m

# Wait 1-3 min, then verify
kubectl get certificate posterra-wildcard-tls -n odoo-dev    # still READY=True, AGE small (re-issued)
curl.exe -I https://posterra.dev.earlyread.ai/web/login      # HTTP 200, no -k flag needed
```

#### Bug fixed during M5: addon manifest load order (commit `41564a5`)

The first M5 attempt failed with `ValueError: External ID not found:
posterra_portal.menu_posterra_config`. Six view files in `posterra_portal`
each defined a `<menuitem>` with `parent="menu_posterra_config"`, but the
parent menu is defined in `views/menuitems.xml` which loads at manifest
position 22 — long after the offending files (positions 3–8). The bug
never surfaced locally because dev DBs already have the menus and `-u`
resolves parent refs from the DB; M5 was the first fresh `-i` install in
months. Fix: moved the 6 stray menuitems into `views/menuitems.xml`,
matching the convention `dashboard_builder` already follows.

---

## What was done — staging

### M0 — Shared
Same shared resources as dev (one ACR, one shared RG). Already applied during dev M0.

### M1 — Networking + DNS  ✅ done
Same as dev with VNet `10.20.0.0/16`. NS records propagated at GoDaddy for
`staging.earlyread.ai`. Verified with `nslookup`.

### M2 — PG + KV + Filestore  ⚠️ needs re-apply
Original M2 applied; KV has the original 6 secrets (`pg-admin-password`,
`jwt-secret`, `ch-password-prod`, `ai-api-key`, `ai-endpoint`, `ai-model`).
M4b's Terraform changes added 3 more secret slots
(`odoo-admin-password`, `filestore-account-name`, `filestore-account-key`)
to both `envs/dev/main.tf` and `envs/staging/main.tf`. **Dev was re-applied;
staging was not.** Re-apply when convenient (no quota dependency):

```powershell
cd infra/terraform/envs/staging
$ip = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
$env:TF_VAR_allowed_ips = '["' + $ip + '"]'
terraform plan -out=staging.tfplan
# Expect: 4 to add (1 random_password + 3 KV secrets), nothing destroyed
terraform apply staging.tfplan

# Then: real filestore key
$kv = "earlyread-saas-staging-kv"
$rg = "earlyread-saas-staging-rg"
$sa = "earlyreadstgfseread"
$key = az storage account keys list --account-name $sa --resource-group $rg --query "[0].value" -o tsv
az keyvault secret set --vault-name $kv --name filestore-account-key --value $key

# And the third-party placeholders
az keyvault secret set --vault-name $kv --name ch-password-prod --value "<real-ch-password>"
az keyvault secret set --vault-name $kv --name ai-api-key --value "<real-anthropic-key>"
```

### M3 — AKS + AppGw + cert-manager + ESO  ⛔ parked
Blocked on Total Regional vCPU quota in `eastus2`. Staging needs ~50 vCPU
(2× D4as_v5 system + 2-3× D4as_v5 user) but the regional quota is currently
28. Microsoft support case open; first quota request was denied citing
regional capacity constraints.

When quota lands, the steps are identical to dev M3 but from
`infra/terraform/envs/staging/`. Don't forget the manual AGIC subnet role
grant (Known Gap #1).

### M4 / M5  ⛔ parked on M3
Chart and values files ready (`values.staging.yaml` already committed for
split-mode deploy: separate portal + admin + cron Deployments with HPA + PDB).
When staging M3 is green, proceed with M4 image rebuild (same image works
across envs) and M5 `helm install -n odoo-staging -f values.staging.yaml`.

---

## Known gaps & manual workarounds

### #1 — AGIC subnet permission not in Terraform (manual `az` per env)

The M3 AKS Terraform module enables the AGIC add-on but doesn't grant the
add-on's managed identity `Microsoft.Network/virtualNetworks/subnets/join/action`
on the AppGw subnet. Result: AGIC programs the HTTP listener (port 80) but
fails on the HTTPS listener (port 443) with
`ApplicationGatewayInsufficientPermissionOnSubnet`.

**Symptom**: `Test-NetConnection ... -Port 443` fails (`TcpTestSucceeded: False`)
even when cert + secret + ingress all show healthy.

**Workaround per env** — run after M3 services apply:

```powershell
$agicObjectId = az aks show -g earlyread-saas-<env>-rg -n earlyread-saas-<env>-aks `
  --query "addonProfiles.ingressApplicationGateway.identity.objectId" -o tsv
$subnetId = az network vnet subnet show -g earlyread-saas-<env>-rg `
  --vnet-name earlyread-saas-<env>-vnet -n earlyread-saas-<env>-appgw-snet `
  --query id -o tsv
az role assignment create `
  --assignee-object-id $agicObjectId `
  --assignee-principal-type ServicePrincipal `
  --role "Network Contributor" `
  --scope $subnetId
kubectl rollout restart deployment -n kube-system -l app=ingress-appgw
```

**Permanent fix** (deferred): add an `azurerm_role_assignment` to the AKS
or AppGw module wiring `module.aks.agic_identity_object_id` to the appgw
subnet with `Network Contributor`. ~5 lines HCL.

### #2 — Init Job design causes brief crash-loop on first install

The chart's init Job runs as a `post-install,pre-upgrade` Helm hook. On
first install, the Deployment's pod starts before the Job runs the schema
bootstrap — Odoo crash-loops for 2-3 min on missing schema until the post-install
hook completes. Self-resolves; no user impact in steady state.

**Phase 2 cleanup**: replace with either a two-step deploy (replicas=0 → init
→ upgrade replicas) or an initContainer in serving pods that gates on a
Job-written `init-complete` ConfigMap. Tracked as a NOTE in
[`infra/helm/posterra/templates/job-init.yaml`](../../infra/helm/posterra/templates/job-init.yaml).

### #3 — Staging vCPU quota not yet approved

Microsoft support case for Total Regional vCPU quota increase
(`eastus2`, 28 → ~50) is open but first request was denied. Until approved,
staging M3+ cannot proceed.

---

## Day-2 ops

### Add a new tenant (e.g. InHome HHA)

Zero infra changes; admin UI work only.

1. Browser to `https://admin.dev.earlyread.ai/web/login`, sign in as admin
2. Settings → Apps → Create
3. Fill `App Key = inhome`, `Display Name = InHome HHA`, configure scope groups, branding, etc.
4. Save
5. `https://inhome.dev.earlyread.ai` is live — wildcard DNS + wildcard cert + wildcard Ingress all already cover it.

### Deploy a new image

1. Push code changes; let CI build a new commit on `main`
2. Build the image:

   ```powershell
   cd C:\Users\nisha\Odoo_Dev
   $tag = git rev-parse --short HEAD
   az acr build --registry earlyreadsaasacreread --image "odoo:$tag" .
   ```

3. Update `infra/helm/posterra/values.dev.yaml`:

   ```diff
    image:
   -  tag: "<old-sha>"
   +  tag: "<new-sha>"
   ```

4. Commit + push, then upgrade:

   ```powershell
   helm upgrade posterra infra/helm/posterra `
     -n odoo-dev `
     -f infra/helm/posterra/values.dev.yaml `
     --timeout 10m
   ```

   The pre-upgrade hook runs `odoo -u` (because `init.mode: upgrade` was
   flipped after first install). Combined-mode dev has Recreate strategy →
   ~30-60s downtime per upgrade.

### Rotate a secret (e.g. PG admin password)

1. Generate new value, set in KV:

   ```powershell
   $newPwd = -join ((33..126) | Get-Random -Count 32 | ForEach-Object {[char]$_})
   az keyvault secret set --vault-name $kv --name pg-admin-password --value $newPwd
   ```

2. Update PG with the new password (admin task, outside Terraform).
3. Force ESO to re-sync (or wait up to 1h refresh interval):

   ```powershell
   kubectl annotate externalsecret odoo-secrets -n odoo-dev force-sync=$(Get-Date -Format o) --overwrite
   ```

4. Roll the pod to pick up the new env var value:

   ```powershell
   kubectl rollout restart deployment posterra-combined -n odoo-dev
   ```

### Re-deploy the dev env from scratch

If you ever need to nuke and re-deploy dev (e.g. major refactor, region change):

1. `helm uninstall posterra -n odoo-dev`
2. (Optional, if PV is in `Released` state) `kubectl patch pv posterra-filestore-odoo-dev -p '{\"spec\":{\"claimRef\": null}}'`
3. (Optional, for truly fresh DB) Drop and recreate `posterra_dev` via a one-shot psql pod inside AKS
4. `terraform destroy` from `envs/dev/services/` then `envs/dev/`
5. (When needed) re-apply `envs/dev/` then `envs/dev/services/`
6. Re-do the manual AGIC subnet role grant (Known Gap #1)
7. Re-apply M4b KV secret population (`az keyvault secret set` for filestore key + third-party API keys)
8. `helm install` (M5)

The Azure Files share has `Retain` reclaim policy on the PV, so filestore
data survives PV/PVC deletion. The Storage Account itself is destroyed by
`terraform destroy` though, so the share data IS lost on a full destroy —
back up first if needed.

---

## Reference — files in this repo

| Path | Purpose |
|---|---|
| `infra/terraform/envs/dev/` | Dev infra (M1, M2, M3 infra, M4b KV) |
| `infra/terraform/envs/dev/services/` | Dev cluster-side services (M3 services) |
| `infra/terraform/envs/staging/` | Staging infra (mirror of dev) |
| `infra/terraform/envs/staging/services/` | Staging cluster-side services (mirror of dev) |
| `infra/terraform/envs/shared/` | Shared resources (ACR), one-time |
| `infra/terraform/modules/` | Reusable modules: network, dns, postgresql, keyvault, filestore, aks, appgw, workload_identity |
| `infra/docker/Dockerfile` | M4a image build |
| `infra/docker/entrypoint.sh` | Container entrypoint (waits for PG, renders odoo.conf, exec odoo) |
| `infra/docker/odoo.conf.template` | INI template for odoo.conf, rendered via envsubst |
| `infra/helm/posterra/` | Helm chart (M4b) |
| `infra/helm/posterra/values.dev.yaml` | Per-env values for dev (combined mode) |
| `infra/helm/posterra/values.staging.yaml` | Per-env values for staging (split mode) |
| `docs/runbooks/phase-1a-deploy.md` | This file |
