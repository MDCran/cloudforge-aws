variable "name" { type = string }
variable "tags" { type = map(string) }
variable "retention_days" { type = number }
variable "cors_origins" { type = list(string) }
variable "eventbridge" { type = bool }

resource "aws_s3_bucket" "this" {
  bucket        = var.name
  force_destroy = false
  tags          = var.tags
}
resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource  = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket     = aws_s3_bucket.this.id
  depends_on = [aws_s3_bucket_versioning.this]
  rule {
    id     = "bounded-retention"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = var.retention_days }
    noncurrent_version_expiration { noncurrent_days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}
resource "aws_s3_bucket_cors_configuration" "this" {
  count  = length(var.cors_origins) > 0 ? 1 : 0
  bucket = aws_s3_bucket.this.id
  cors_rule {
    allowed_origins = var.cors_origins
    allowed_methods = ["POST", "GET"]
    allowed_headers = ["content-type", "x-amz-*"]
    max_age_seconds = 300
  }
}
resource "aws_s3_bucket_notification" "this" {
  count       = var.eventbridge ? 1 : 0
  bucket      = aws_s3_bucket.this.id
  eventbridge = true
}
output "id" { value = aws_s3_bucket.this.id }
output "arn" { value = aws_s3_bucket.this.arn }
