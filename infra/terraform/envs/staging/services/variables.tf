variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.subscription_id))
    error_message = "subscription_id must be a valid GUID."
  }
}

variable "env" {
  description = "Environment slug. DO NOT change for this directory."
  type        = string
  default     = "staging"

  validation {
    condition     = var.env == "staging"
    error_message = "This directory is hardcoded for env=staging."
  }
}

variable "acme_email" {
  description = "Email for Let's Encrypt registration. Used only for cert-renewal-warning notifications."
  type        = string
  default     = "nishant.singh@humbianalytics.com"
}
