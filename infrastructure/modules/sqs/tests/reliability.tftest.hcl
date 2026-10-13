mock_provider "aws" {}
variables {
  name           = "cloudforge-test-jobs"
  tags           = { Environment = "test" }
  worker_timeout = 60
}
run "queue_has_retry_budget" {
  command = apply
  assert {
    condition     = aws_sqs_queue.this.visibility_timeout_seconds == 360
    error_message = "The visibility timeout must cover six Lambda execution windows."
  }
  assert {
    condition     = jsondecode(aws_sqs_queue.this.redrive_policy).maxReceiveCount == 5
    error_message = "Five delivery attempts must be allowed before dead-lettering."
  }
  assert {
    condition     = aws_sqs_queue.dead.message_retention_seconds == 1209600
    error_message = "Dead-letter records need 14 days of retention."
  }
}
