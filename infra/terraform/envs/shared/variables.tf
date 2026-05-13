variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.subscription_id))
    error_message = "subscription_id must be a valid GUID."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus2"
}

variable "acr_name" {
  description = "ACR name (5-50 chars, lowercase alphanumeric only, globally unique)."
  type        = string
  default     = "earlyreadsaasacreread"
}
