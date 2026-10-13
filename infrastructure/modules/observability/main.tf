variable "name" { type = string }
variable "environment" { type = string }
variable "api_id" { type = string }
variable "api_function" { type = string }
variable "worker_function" { type = string }
variable "queue_name" { type = string }
variable "dead_name" { type = string }
variable "table_name" { type = string }
variable "alert_email" { type = string }
variable "tags" { type = map(string) }
data "aws_region" "current" {}
resource "aws_sns_topic" "alerts" {
  name              = "${var.name}-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}
resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
locals {
  alarms = {
    api-errors          = { namespace = "AWS/ApiGateway", metric = "5xx", statistic = "Sum", threshold = 5, dimensions = { ApiId = var.api_id } }
    api-latency         = { namespace = "AWS/ApiGateway", metric = "Latency", statistic = "Average", threshold = 2000, dimensions = { ApiId = var.api_id } }
    api-lambda-errors   = { namespace = "AWS/Lambda", metric = "Errors", statistic = "Sum", threshold = 1, dimensions = { FunctionName = var.api_function } }
    worker-errors       = { namespace = "AWS/Lambda", metric = "Errors", statistic = "Sum", threshold = 1, dimensions = { FunctionName = var.worker_function } }
    worker-duration     = { namespace = "AWS/Lambda", metric = "Duration", statistic = "Average", threshold = 45000, dimensions = { FunctionName = var.worker_function } }
    queue-age           = { namespace = "AWS/SQS", metric = "ApproximateAgeOfOldestMessage", statistic = "Maximum", threshold = 300, dimensions = { QueueName = var.queue_name } }
    dead-messages       = { namespace = "AWS/SQS", metric = "ApproximateNumberOfMessagesVisible", statistic = "Maximum", threshold = 1, dimensions = { QueueName = var.dead_name } }
    table-throttles     = { namespace = "AWS/DynamoDB", metric = "ThrottledRequests", statistic = "Sum", threshold = 1, dimensions = { TableName = var.table_name } }
    processing-failures = { namespace = "CloudForge", metric = "Failed", statistic = "Sum", threshold = 1, dimensions = { Environment = var.environment } }
  }
}
resource "aws_cloudwatch_metric_alarm" "this" {
  for_each            = local.alarms
  alarm_name          = "${var.name}-${each.key}"
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  dimensions          = each.value.dimensions
  threshold           = each.value.threshold
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}
resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name
  dashboard_body = jsonencode({ widgets = [
    {
      type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
        title = "HTTP requests and errors", region = data.aws_region.current.region, period = 300, stat = "Sum",
    metrics = [["AWS/ApiGateway", "Count", "ApiId", var.api_id], ["AWS/ApiGateway", "5xx", "ApiId", var.api_id]] } },
    {
      type = "metric", x = 12, y = 0, width = 12, height = 6, properties = {
        title = "Function invocations", region = data.aws_region.current.region, period = 300, stat = "Sum",
    metrics = [["AWS/Lambda", "Invocations", "FunctionName", var.api_function], ["AWS/Lambda", "Invocations", "FunctionName", var.worker_function]] } },
    {
      type = "metric", x = 0, y = 6, width = 12, height = 6, properties = {
        title = "Worker duration and queue backlog", region = data.aws_region.current.region, period = 300,
    metrics = [["AWS/Lambda", "Duration", "FunctionName", var.worker_function, { stat = "Average" }], ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.queue_name, { yAxis = "right", stat = "Maximum" }]] } },
    {
      type = "metric", x = 12, y = 6, width = 12, height = 6, properties = {
        title = "Completed / failed jobs", region = data.aws_region.current.region, period = 300, stat = "Sum",
    metrics = [["CloudForge", "Completed", "Environment", var.environment], ["CloudForge", "Failed", "Environment", var.environment]] } },
    {
      type = "metric", x = 0, y = 12, width = 12, height = 6, properties = {
        title = "Dead-letter messages", region = data.aws_region.current.region, period = 300, stat = "Maximum",
    metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dead_name]] } },
    {
      type = "alarm", x = 12, y = 12, width = 12, height = 6, properties = {
    title = "Environment health", alarms = [for alarm in aws_cloudwatch_metric_alarm.this : alarm.arn] } }
  ] })
}
output "dashboard" { value = aws_cloudwatch_dashboard.this.dashboard_name }
