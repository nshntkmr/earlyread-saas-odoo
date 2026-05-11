variable "zone_name" {
  description = "Fully qualified zone name (e.g. dev.earlyread.ai)."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group that holds the DNS zone."
  type        = string
}

variable "tags" {
  description = "Tags applied to the DNS zone resource."
  type        = map(string)
  default     = {}
}
