variable "env" {
  description = "Environment slug (dev, staging, prod)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the AKS cluster."
  type        = string
}

variable "resource_group_id" {
  description = "Resource group resource ID (for the AGIC Reader role assignment)."
  type        = string
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version. Pin a specific patch (e.g. 1.34.6) — verify availability with `az aks get-versions --location eastus2`."
  type        = string
}

variable "aks_subnet_id" {
  description = "Subnet resource ID for AKS nodes (CNI Overlay; pods use separate Pod CIDR)."
  type        = string
}

variable "pod_cidr" {
  description = "CIDR for pod IPs (CNI Overlay). 100.64.0.0/16 is the conventional RFC-6598 range."
  type        = string
  default     = "100.64.0.0/16"
}

variable "appgw_id" {
  description = "Application Gateway resource ID. AGIC add-on attaches to this AppGw."
  type        = string
}

variable "acr_id" {
  description = "ACR resource ID. Kubelet identity gets AcrPull on this for image pulls."
  type        = string
}

# ─── System pool — must meet AKS minimums (≥ 4 vCPU + 4 GB RAM, ≥ 2 nodes) ──

variable "system_vm_size" {
  description = "VM size for the system node pool. Must be >= 4 vCPU / 4 GB RAM. v4/v5/v6/v7 D-series generations all qualify — pick a family with available quota AND capacity in your region (check with `az vm list-skus`)."
  type        = string
  default     = "Standard_D4as_v4"
}

variable "system_min_count" {
  description = "System pool minimum node count (AKS requires ≥ 2)."
  type        = number
  default     = 2

  validation {
    condition     = var.system_min_count >= 2
    error_message = "AKS system pool minimum is 2 nodes."
  }
}

variable "system_max_count" {
  description = "System pool maximum node count. Set equal to min_count for fixed sizing (dev)."
  type        = number
  default     = 2
}

# ─── User pool — workload pods ──────────────────────────────────────────────

variable "user_vm_size" {
  description = "VM size for the user node pool. Asymmetric: smaller D2-class for dev, D4-class for staging. Pick a family with available quota AND capacity."
  type        = string
}

variable "user_min_count" {
  description = "User pool minimum node count."
  type        = number
  default     = 1
}

variable "user_max_count" {
  description = "User pool maximum node count."
  type        = number
  default     = 2
}

# ─── Azure AD / RBAC ────────────────────────────────────────────────────────

variable "admin_group_object_ids" {
  description = "Azure AD group object IDs granted system:masters via the AAD integration. Empty list = use --admin flag for ad-hoc kubectl access."
  type        = list(string)
  default     = []
}

variable "cluster_admin_oids" {
  description = "User/group object IDs granted 'Azure Kubernetes Service RBAC Cluster Admin' (Azure RBAC layer, not K8s RBAC)."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
