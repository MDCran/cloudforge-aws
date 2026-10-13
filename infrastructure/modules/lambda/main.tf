variable "name" { type = string }
variable "role_arn" { type = string }
variable "artifact" { type = string }
variable "handler" { type = string }
variable "environment" { type = map(string) }
variable "timeout" { type = number }
variable "memory" { type = number }
variable "concurrency" { type = number }
variable "retention" { type = number }
variable "tags" { type = map(string) }
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.retention
  tags              = var.tags
}
resource "aws_lambda_function" "this" {
  function_name                  = var.name
  role                           = var.role_arn
  filename                       = var.artifact
  source_code_hash               = filebase64sha256(var.artifact)
  handler                        = var.handler
  runtime                        = "python3.12"
  architectures                  = ["x86_64"]
  timeout                        = var.timeout
  memory_size                    = var.memory
  reserved_concurrent_executions = var.concurrency
  publish                        = true
  environment { variables = var.environment }
  tags       = var.tags
  depends_on = [aws_cloudwatch_log_group.this]
}
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version
}
output "name" { value = aws_lambda_function.this.function_name }
output "arn" { value = aws_lambda_function.this.arn }
output "alias_arn" { value = aws_lambda_alias.live.arn }
output "invoke_arn" { value = aws_lambda_alias.live.invoke_arn }
