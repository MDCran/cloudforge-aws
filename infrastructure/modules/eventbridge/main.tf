variable "name" { type = string }
variable "bucket" { type = string }
variable "queue_arn" { type = string }
variable "queue_url" { type = string }
variable "tags" { type = map(string) }
resource "aws_cloudwatch_event_rule" "uploads" {
  name = var.name
  event_pattern = jsonencode({ source = ["aws.s3"], "detail-type" = ["Object Created"],
  detail = { bucket = { name = [var.bucket] }, object = { key = [{ prefix = "uploads/" }] } } })
  tags = var.tags
}
resource "aws_cloudwatch_event_target" "queue" {
  rule = aws_cloudwatch_event_rule.uploads.name
  arn  = var.queue_arn
  retry_policy {
    maximum_event_age_in_seconds = 86400
    maximum_retry_attempts       = 185
  }
  depends_on = [aws_sqs_queue_policy.events]
}
resource "aws_sqs_queue_policy" "events" {
  queue_url = var.queue_url
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sqs:SendMessage",
    Resource = var.queue_arn, Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.uploads.arn } }
  }] })
}
