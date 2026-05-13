variable "env" {
  description = "Environment slug (dev, staging, prod)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the App Gateway + public IP."
  type        = string
}

variable "appgw_subnet_id" {
  description = "Dedicated subnet ID for App Gateway v2 (M1 created this, /24 minimum)."
  type        = string
}

variable "sku_name" {
  description = "App Gateway SKU. 'Standard_v2' (~$180/mo, no WAF) or 'WAF_v2' (~$324/mo, OWASP rule sets + bot management). SKU cannot be changed in-place — switching later requires gateway recreation + DNS cutover."
  type        = string
  default     = "Standard_v2"

  validation {
    condition     = contains(["Standard_v2", "WAF_v2"], var.sku_name)
    error_message = "sku_name must be 'Standard_v2' or 'WAF_v2'."
  }
}

variable "waf_mode" {
  description = "WAF mode. Only used when sku_name = WAF_v2. Start with Detection (logs only); flip to Prevention in M6."
  type        = string
  default     = "Detection"

  validation {
    condition     = contains(["Detection", "Prevention"], var.waf_mode)
    error_message = "waf_mode must be 'Detection' or 'Prevention'."
  }
}

variable "tags" {
  description = "Tags applied to App Gateway + public IP."
  type        = map(string)
  default     = {}
}
