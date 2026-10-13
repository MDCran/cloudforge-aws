mock_provider "aws" {}
variables {
  name           = "cloudforge-test-private-uploads"
  tags           = { Environment = "test" }
  retention_days = 7
  cors_origins   = ["http://localhost:5173"]
  eventbridge    = true
}
run "private_storage" {
  command = plan
  assert {
    condition     = aws_s3_bucket_public_access_block.this.block_public_policy && aws_s3_bucket_public_access_block.this.restrict_public_buckets
    error_message = "Storage must reject public access."
  }
  assert {
    condition     = aws_s3_bucket_versioning.this.versioning_configuration[0].status == "Enabled"
    error_message = "Version-specific processing requires versioned uploads."
  }
  assert {
    condition     = aws_s3_bucket_notification.this[0].eventbridge
    error_message = "Upload notifications must reach EventBridge."
  }
}
