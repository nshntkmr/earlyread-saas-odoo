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
    # See dev/services/providers.tf for why kubectl is used instead of
    # hashicorp/kubernetes for the CRD-backed manifests.
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
