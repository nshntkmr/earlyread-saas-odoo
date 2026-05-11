#!/usr/bin/env bash
# Bootstrap the Terraform remote state backend.
# Run ONCE per cloud account/installation. Idempotent — safe to re-run.
#
# Required env vars:
#   SUBSCRIPTION_ID  Azure subscription ID
#
# Optional env vars (with defaults):
#   SUFFIX           Storage account suffix for global uniqueness  (default: eread)
#   LOCATION         Azure region                                  (default: eastus2)
#
# Usage:
#   export SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"
#   bash bootstrap.sh
set -euo pipefail

# ── Required input ────────────────────────────────────────────────────────────
: "${SUBSCRIPTION_ID:?Set SUBSCRIPTION_ID env var (your Azure subscription ID)}"

# ── Defaults ──────────────────────────────────────────────────────────────────
SUFFIX="${SUFFIX:-eread}"
LOCATION="${LOCATION:-eastus2}"
TFSTATE_RG="earlyread-saas-tfstate-rg"
STORAGE_NAME="earlyreadtfstate${SUFFIX}"
PROJECT_TAG="earlyread-saas"
OUTPUT_FILE="bootstrap-output.txt"

# ── Validate inputs ───────────────────────────────────────────────────────────
if [[ ${#STORAGE_NAME} -gt 24 ]]; then
  echo "ERROR: Storage account name '${STORAGE_NAME}' exceeds 24 chars (Azure limit)." >&2
  echo "       Pick a shorter SUFFIX (current is '${SUFFIX}')." >&2
  exit 1
fi
if ! [[ "$STORAGE_NAME" =~ ^[a-z0-9]+$ ]]; then
  echo "ERROR: Storage account name '${STORAGE_NAME}' must be lowercase alphanumeric only." >&2
  echo "       Pick a SUFFIX with only [a-z0-9] (current is '${SUFFIX}')." >&2
  exit 1
fi

# ── Verify Azure CLI auth ─────────────────────────────────────────────────────
echo "==> Setting active subscription to ${SUBSCRIPTION_ID}"
az account set --subscription "$SUBSCRIPTION_ID"

ACTIVE_SUB=$(az account show --query id -o tsv)
if [[ "$ACTIVE_SUB" != "$SUBSCRIPTION_ID" ]]; then
  echo "ERROR: Active subscription is '${ACTIVE_SUB}', expected '${SUBSCRIPTION_ID}'." >&2
  echo "       Run 'az login' and try again." >&2
  exit 1
fi
echo "    Active subscription confirmed."

# ── 1. Resource Group ─────────────────────────────────────────────────────────
echo "==> Creating Resource Group '${TFSTATE_RG}' in ${LOCATION}"
az group create \
  --name "$TFSTATE_RG" \
  --location "$LOCATION" \
  --tags "project=${PROJECT_TAG}" "purpose=tfstate" "managed_by=manual" \
  --output none
echo "    OK"

# ── 2. Storage Account ────────────────────────────────────────────────────────
echo "==> Creating Storage Account '${STORAGE_NAME}'"
if az storage account show --name "$STORAGE_NAME" --resource-group "$TFSTATE_RG" --output none 2>/dev/null; then
  echo "    Already exists; skipping create."
else
  az storage account create \
    --name "$STORAGE_NAME" \
    --resource-group "$TFSTATE_RG" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --min-tls-version TLS1_2 \
    --allow-blob-public-access false \
    --tags "project=${PROJECT_TAG}" "purpose=tfstate" "managed_by=manual" \
    --output none
  echo "    OK"
fi

# ── 3. Storage hardening (idempotent) ─────────────────────────────────────────
echo "==> Enabling soft delete (30d) and blob versioning"
az storage account blob-service-properties update \
  --account-name "$STORAGE_NAME" \
  --resource-group "$TFSTATE_RG" \
  --enable-versioning true \
  --enable-delete-retention true \
  --delete-retention-days 30 \
  --output none
echo "    OK"

# ── 4. Containers (one per env) ───────────────────────────────────────────────
for env in dev staging; do
  echo "==> Ensuring container '${env}' exists"
  az storage container create \
    --name "$env" \
    --account-name "$STORAGE_NAME" \
    --auth-mode login \
    --output none
  echo "    OK"
done

# ── 5. Write output for terraform init ────────────────────────────────────────
cat > "$OUTPUT_FILE" <<EOF
# Bootstrap output ($(date -u +%Y-%m-%dT%H:%M:%SZ))
# Use these values when running 'terraform init' for each env.

# ── DEV ───────────────────────────────────────────────────────────────────────
cd ../envs/dev
terraform init \\
  -backend-config=resource_group_name=${TFSTATE_RG} \\
  -backend-config=storage_account_name=${STORAGE_NAME} \\
  -backend-config=container_name=dev \\
  -backend-config=key=terraform.tfstate

# ── STAGING ───────────────────────────────────────────────────────────────────
cd ../envs/staging
terraform init \\
  -backend-config=resource_group_name=${TFSTATE_RG} \\
  -backend-config=storage_account_name=${STORAGE_NAME} \\
  -backend-config=container_name=staging \\
  -backend-config=key=terraform.tfstate

# ── ENV VARS ──────────────────────────────────────────────────────────────────
# Set these in your shell before running terraform commands:
export ARM_SUBSCRIPTION_ID="${SUBSCRIPTION_ID}"
EOF

echo
echo "==> DONE"
echo "    Bootstrap output written to: $(pwd)/${OUTPUT_FILE}"
echo "    (gitignored — safe to keep locally)"
echo
echo "    Next: cd ../envs/dev && follow terraform init / plan / apply steps"
echo "          (see ${OUTPUT_FILE} for exact backend-config flags)"
