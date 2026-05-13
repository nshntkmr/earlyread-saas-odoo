variable "name" {
  description = "ACR name (5-50 chars, lowercase alphanumeric only, globally unique)."
  type        = string

  validation {
    condition     = length(var.name) >= 5 && length(var.name) <= 50 && can(regex("^[a-z0-9]+$", var.name))
    error_message = "ACR name must be 5-50 chars, lowercase alphanumeric only (no hyphens or underscores)."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the ACR."
  type        = string
}

variable "tags" {
  description = "Tags applied to the ACR."
  type        = map(string)
  default     = {}
}
