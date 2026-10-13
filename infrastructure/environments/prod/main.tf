variable "region" {
  type    = string
  default = "us-east-1"
}
variable "origins" {
  type    = list(string)
  default = ["https://console.example.com"]
}
variable "callback_urls" {
  type    = list(string)
  default = ["https://console.example.com/callback"]
}
variable "logout_urls" {
  type    = list(string)
  default = ["https://console.example.com/"]
}
variable "artifact_dir" {
  type    = string
  default = "../../../artifacts"
}
variable "alert_email" {
  type    = string
  default = ""
}
variable "protect_data" {
  type    = bool
  default = true
}
variable "retention_days" {
  type    = number
  default = 90
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 365
    error_message = "Object retention must be from 1 to 365 days."
  }
}
variable "log_retention" {
  type    = number
  default = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention)
    error_message = "Choose a supported CloudWatch retention period."
  }
}
variable "worker_memory" {
  type    = number
  default = 1024
  validation {
    condition     = var.worker_memory >= 512 && var.worker_memory <= 10240
    error_message = "Worker memory must be 512–10240 MiB."
  }
}
variable "worker_concurrency" {
  type    = number
  default = 20
  validation {
    condition     = var.worker_concurrency >= 1 && var.worker_concurrency <= 100
    error_message = "Worker reserved concurrency must be 1–100."
  }
}
variable "api_concurrency" {
  type    = number
  default = 40
  validation {
    condition     = var.api_concurrency >= 1 && var.api_concurrency <= 200
    error_message = "API reserved concurrency must be 1–200."
  }
}
module "platform" {
  source             = "../../modules/platform"
  environment        = "prod"
  region             = var.region
  origins            = var.origins
  callback_urls      = var.callback_urls
  logout_urls        = var.logout_urls
  artifact_dir       = abspath(var.artifact_dir)
  alert_email        = var.alert_email
  protect_data       = var.protect_data
  retention_days     = var.retention_days
  log_retention      = var.log_retention
  worker_memory      = var.worker_memory
  worker_concurrency = var.worker_concurrency
  api_concurrency    = var.api_concurrency
}
output "api_url" { value = module.platform.api_url }
output "user_pool_id" { value = module.platform.user_pool_id }
output "client_id" { value = module.platform.client_id }
output "auth_url" { value = module.platform.auth_url }
output "dashboard_name" { value = module.platform.dashboard_name }
output "upload_bucket" { value = module.platform.upload_bucket }
output "result_bucket" { value = module.platform.result_bucket }
output "table_name" { value = module.platform.table_name }
output "queue_url" { value = module.platform.queue_url }
