variable "name" { type = string }
variable "tags" { type = map(string) }
variable "worker_timeout" { type = number }
resource "aws_sqs_queue" "dead" {
  name                      = "${var.name}-dead"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = var.tags
}
resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.worker_timeout * 6
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dead.arn, maxReceiveCount = 5 })
  tags                       = var.tags
}
resource "aws_sqs_queue_redrive_allow_policy" "this" {
  queue_url            = aws_sqs_queue.dead.url
  redrive_allow_policy = jsonencode({ redrivePermission = "byQueue", sourceQueueArns = [aws_sqs_queue.this.arn] })
}
output "arn" { value = aws_sqs_queue.this.arn }
output "url" { value = aws_sqs_queue.this.url }
output "name" { value = aws_sqs_queue.this.name }
output "dead_arn" { value = aws_sqs_queue.dead.arn }
output "dead_name" { value = aws_sqs_queue.dead.name }
