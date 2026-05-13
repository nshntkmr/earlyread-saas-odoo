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

variable "waf_mode" {
  description = "WAF mode. Start with Detection (logs only); flip to Prevention in M6."
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
