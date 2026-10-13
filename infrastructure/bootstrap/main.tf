terraform {
  required_version = "= 1.13.5"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
variable "region" { type = string }
variable "state_bucket_name" { type = string }
variable "repository" { type = string }
variable "existing_oidc_provider_arn" {
  type    = string
  default = ""
}
variable "apply_policy_arns" {
  type = set(string)
  validation {
    condition     = length(var.apply_policy_arns) > 0
    error_message = "Supply reviewed customer-managed deployment policy ARNs."
  }
}
variable "plan_policy_arns" {
  type = set(string)
  validation {
    condition     = length(var.plan_policy_arns) > 0
    error_message = "Supply reviewed metadata-read policy ARNs for Terraform planning."
  }
}
variable "budget_email" {
  type    = string
  default = ""
}
variable "monthly_budget_usd" {
  type    = number
  default = 15
}
provider "aws" { region = var.region }
locals { tags = { Project = "cloudforge-aws", ManagedBy = "Terraform", Environment = "bootstrap" } }
resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
  tags   = local.tags
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  tags           = local.tags
}
module "identity" {
  for_each          = toset(["dev", "staging", "prod"])
  source            = "../modules/deployment-identity"
  environment       = each.key
  repository        = var.repository
  oidc_arn          = var.existing_oidc_provider_arn != "" ? var.existing_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
  state_bucket_arn  = aws_s3_bucket.state.arn
  apply_policy_arns = var.apply_policy_arns
  plan_policy_arns  = var.plan_policy_arns
  tags              = local.tags
}
resource "aws_budgets_budget" "monthly" {
  count        = var.budget_email != "" ? 1 : 0
  name         = "cloudforge-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$cloudforge-aws"]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
output "state_bucket" { value = aws_s3_bucket.state.id }
output "roles" { value = { for env, identity in module.identity : env => { plan = identity.plan_role_arn, apply = identity.apply_role_arn } } }
