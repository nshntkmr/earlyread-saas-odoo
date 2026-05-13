# ─────────────────────────────────────────────────────────────────────────────
# Cluster Services module — runs INSIDE the AKS cluster
#
# Applied as part of envs/<env>/services/, NOT envs/<env>/. Splits cluster
# infra (azurerm only) from cluster runtime services (azurerm + helm + kubectl)
# to avoid race conditions on first apply.
#
# Resources created:
#   • cert-manager Helm release with workload identity wiring
#   • Let's Encrypt staging ClusterIssuer (DNS-01 via Azure DNS UAMI)
#   • Let's Encrypt production ClusterIssuer (same; switch issuer ref in M5)
#   • ESO Helm release with workload identity wiring
#   • ClusterSecretStore pointing at the env's KV (via the ESO UAMI)
#
# Uses gavinbunney/kubectl (not hashicorp/kubernetes) for the ClusterIssuer
# and ClusterSecretStore resources because those reference CRDs that don't
# exist until cert-manager / ESO Helm installs complete. The hashicorp
# kubernetes_manifest resource validates against the API at PLAN time, which
# fails when the CRDs don't exist yet. kubectl_manifest does not — it just
# applies the YAML at apply time.
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.16"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
}

# ─── cert-manager ────────────────────────────────────────────────────────────

resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  version          = var.cert_manager_chart_version

  # CRDs installed by the chart so kubectl_manifest resources below find them.
  set {
    name  = "installCRDs"
    value = "true"
  }

  # Wire workload identity onto the cert-manager ServiceAccount + pod labels.
  set {
    name  = "serviceAccount.labels.azure\\.workload\\.identity/use"
    value = "true"
  }
  set {
    name  = "serviceAccount.annotations.azure\\.workload\\.identity/client-id"
    value = var.cert_manager_uami_client_id
  }
  set {
    name  = "podLabels.azure\\.workload\\.identity/use"
    value = "true"
  }
}

# Let's Encrypt staging issuer (higher rate limits, friendlier for debugging).
# M5 first cert request will use this; flip to letsencrypt-prod after verifying.
resource "kubectl_manifest" "letsencrypt_staging" {
  yaml_body = yamlencode({
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "letsencrypt-staging"
    }
    spec = {
      acme = {
        server = "https://acme-staging-v02.api.letsencrypt.org/directory"
        email  = var.acme_email
        privateKeySecretRef = {
          name = "letsencrypt-staging-key"
        }
        solvers = [{
          dns01 = {
            azureDNS = {
              resourceGroupName = var.dns_zone_resource_group_name
              subscriptionID    = var.subscription_id
              hostedZoneName    = var.dns_zone_name
              environment       = "AzurePublicCloud"
              managedIdentity = {
                clientID = var.cert_manager_uami_client_id
              }
            }
          }
        }]
      }
    }
  })

  depends_on = [helm_release.cert_manager]
}

# Let's Encrypt production issuer (rate-limited; flip to this when staging
# has been verified end-to-end).
resource "kubectl_manifest" "letsencrypt_prod" {
  yaml_body = yamlencode({
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "letsencrypt-prod"
    }
    spec = {
      acme = {
        server = "https://acme-v02.api.letsencrypt.org/directory"
        email  = var.acme_email
        privateKeySecretRef = {
          name = "letsencrypt-prod-key"
        }
        solvers = [{
          dns01 = {
            azureDNS = {
              resourceGroupName = var.dns_zone_resource_group_name
              subscriptionID    = var.subscription_id
              hostedZoneName    = var.dns_zone_name
              environment       = "AzurePublicCloud"
              managedIdentity = {
                clientID = var.cert_manager_uami_client_id
              }
            }
          }
        }]
      }
    }
  })

  depends_on = [helm_release.cert_manager]
}

# ─── External Secrets Operator ───────────────────────────────────────────────

resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets-system"
  create_namespace = true
  version          = var.eso_chart_version

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "serviceAccount.labels.azure\\.workload\\.identity/use"
    value = "true"
  }
  set {
    name  = "serviceAccount.annotations.azure\\.workload\\.identity/client-id"
    value = var.eso_uami_client_id
  }
  set {
    name  = "podLabels.azure\\.workload\\.identity/use"
    value = "true"
  }
  set {
    name  = "webhook.podLabels.azure\\.workload\\.identity/use"
    value = "true"
  }
  set {
    name  = "certController.podLabels.azure\\.workload\\.identity/use"
    value = "true"
  }
}

# ClusterSecretStore — the integration point between ESO and the env's KV.
# Helm chart M5 will create ExternalSecret resources that reference this
# store name.
resource "kubectl_manifest" "kv_cluster_secret_store" {
  yaml_body = yamlencode({
    apiVersion = "external-secrets.io/v1beta1"
    kind       = "ClusterSecretStore"
    metadata = {
      name = "${var.env}-kv-store"
    }
    spec = {
      provider = {
        azurekv = {
          authType = "WorkloadIdentity"
          serviceAccountRef = {
            name      = "external-secrets"
            namespace = "external-secrets-system"
          }
          vaultUrl = var.kv_uri
          tenantId = var.tenant_id
        }
      }
    }
  })

  depends_on = [helm_release.external_secrets]
}
