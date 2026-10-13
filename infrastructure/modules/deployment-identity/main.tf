variable "repository" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.repository))
    error_message = "Use owner/repository."
  }
}
variable "environment" { type = string }
variable "oidc_arn" { type = string }
variable "state_bucket_arn" { type = string }
variable "apply_policy_arns" { type = set(string) }
variable "plan_policy_arns" { type = set(string) }
variable "tags" { type = map(string) }
data "aws_partition" "current" {}
resource "aws_iam_role" "plan" {
  name = "cloudforge-github-${var.environment}-plan"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = var.oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = "repo:${var.repository}:ref:refs/heads/main"
    } }
  }] })
  tags = var.tags
}
resource "aws_iam_role" "apply" {
  name = "cloudforge-github-${var.environment}-apply"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = var.oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = "repo:${var.repository}:environment:${var.environment}"
    } }
  }] })
  tags = var.tags
}
resource "aws_iam_role_policy_attachment" "read" {
  for_each   = var.plan_policy_arns
  role       = aws_iam_role.plan.name
  policy_arn = each.value
}
resource "aws_iam_role_policy_attachment" "apply" {
  for_each   = var.apply_policy_arns
  role       = aws_iam_role.apply.name
  policy_arn = each.value
}
resource "aws_iam_role_policy" "state" {
  for_each = { plan = aws_iam_role.plan.id, apply = aws_iam_role.apply.id }
  name     = "environment-state"
  role     = each.value
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    {
      Effect = "Allow", Action = ["s3:ListBucket"], Resource = var.state_bucket_arn,
    Condition = { StringLike = { "s3:prefix" = ["${var.environment}/*"] } } },
    {
      Effect = "Allow", Action = each.key == "apply" ? ["s3:GetObject", "s3:PutObject"] : ["s3:GetObject"],
    Resource = "${var.state_bucket_arn}/${var.environment}/terraform.tfstate" },
    {
      Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
    Resource = "${var.state_bucket_arn}/${var.environment}/terraform.tfstate.tflock" }
  ] })
}
output "plan_role_arn" { value = aws_iam_role.plan.arn }
output "apply_role_arn" { value = aws_iam_role.apply.arn }
