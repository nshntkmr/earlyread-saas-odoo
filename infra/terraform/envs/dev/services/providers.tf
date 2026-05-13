terraform {
  required_version = "~> 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.16"
    }
    # gavinbunney/kubectl is used instead of hashicorp/kubernetes's
    # kubernetes_manifest because kubernetes_manifest validates against the
    # K8s API at PLAN time. cert-manager CRDs (ClusterIssuer) don't exist
    # until cert-manager Helm install completes APPLY-time, so plan fails.
    # kubectl_manifest applies via YAML without schema validation.
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
}

provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
}

# Helm and kubectl providers connect to the AKS cluster using the
# kube_admin_config (local cert-based auth — works because we set
# local_account_disabled = false on the cluster). Using kube_admin_config
# instead of kube_config because kube_config returns AAD-based auth when
# Azure AD RBAC is enabled, which Terraform providers can't use without
# kubelogin / additional setup.

data "azurerm_kubernetes_cluster" "this" {
  name                = "earlyread-saas-${var.env}-aks"
  resource_group_name = "earlyread-saas-${var.env}-rg"
}

provider "helm" {
  kubernetes {
    host                   = data.azurerm_kubernetes_cluster.this.kube_admin_config[0].host
    client_certificate     = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].client_certificate)
    client_key             = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].client_key)
    cluster_ca_certificate = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].cluster_ca_certificate)
  }
}

provider "kubectl" {
  host                   = data.azurerm_kubernetes_cluster.this.kube_admin_config[0].host
  client_certificate     = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].client_certificate)
  client_key             = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].client_key)
  cluster_ca_certificate = base64decode(data.azurerm_kubernetes_cluster.this.kube_admin_config[0].cluster_ca_certificate)
  load_config_file       = false
}
