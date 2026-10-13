variable "name" { type = string }
variable "lambda_name" { type = string }
variable "invoke_arn" { type = string }
variable "issuer" { type = string }
variable "audience" { type = string }
variable "origins" { type = list(string) }
variable "retention" { type = number }
variable "tags" { type = map(string) }
resource "aws_apigatewayv2_api" "this" {
  name          = var.name
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins  = var.origins
    allow_methods  = ["GET", "POST", "OPTIONS"]
    allow_headers  = ["authorization", "content-type", "idempotency-key"]
    expose_headers = ["x-correlation-id"]
    max_age        = 300
  }
  tags = var.tags
}
resource "aws_apigatewayv2_authorizer" "this" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  jwt_configuration {
    issuer   = var.issuer
    audience = [var.audience]
  }
}
resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}
resource "aws_apigatewayv2_route" "secured" {
  for_each = toset(["POST /v1/jobs", "GET /v1/jobs", "GET /v1/jobs/{jobId}",
    "POST /v1/jobs/{jobId}/cancel", "POST /v1/uploads/presign",
  "GET /v1/jobs/{jobId}/result", "GET /v1/metrics/summary"])
  api_id               = aws_apigatewayv2_api.this.id
  route_key            = each.key
  target               = "integrations/${aws_apigatewayv2_integration.this.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.this.id
  authorization_scopes = ["cloudforge-api/jobs"]
}
resource "aws_cloudwatch_log_group" "access" {
  name              = "/cloudforge/${var.name}/access"
  retention_in_days = var.retention
  tags              = var.tags
}
resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit   = 20
    throttling_rate_limit    = 10
    detailed_metrics_enabled = true
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({ requestId = "$context.requestId", route = "$context.routeKey",
    status = "$context.status", latency = "$context.responseLatency" })
  }
  tags = var.tags
}
resource "aws_lambda_permission" "invoke" {
  statement_id  = "ApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_name
  qualifier     = "live"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
output "url" { value = aws_apigatewayv2_api.this.api_endpoint }
output "id" { value = aws_apigatewayv2_api.this.id }
