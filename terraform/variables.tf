variable "google_api_key" {
  description = "The API key for Google GenAI"
  type        = string
  sensitive   = true # This prevents it from showing in CLI logs
}

variable "jqunats_api_key" {
  description = "The API key for J-Quants"
  type        = string
  sensitive   = true
}

variable "dash_password" {
  description = "The password for Dash"
  type        = string
  sensitive   = true
}