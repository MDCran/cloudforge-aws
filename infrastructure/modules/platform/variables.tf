variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Choose dev, staging, or prod."
  }
}
variable "region" { type = string }
variable "origins" {
  type = list(string)
  validation {
    condition     = length(var.origins) > 0 && alltrue([for origin in var.origins : origin != "*" && (startswith(origin, "https://") || startswith(origin, "http://localhost:") || startswith(origin, "http://127.0.0.1:"))])
    error_message = "Supply explicit HTTPS or loopback origins."
  }
}
variable "callback_urls" { type = list(string) }
variable "logout_urls" { type = list(string) }
variable "artifact_dir" { type = string }
variable "alert_email" { type = string }
variable "protect_data" { type = bool }
variable "retention_days" { type = number }
variable "log_retention" { type = number }
variable "worker_memory" { type = number }
variable "api_concurrency" { type = number }
variable "worker_concurrency" { type = number }
