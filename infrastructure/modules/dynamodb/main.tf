variable "name" { type = string }
variable "tags" { type = map(string) }
variable "protect" { type = bool }
resource "aws_dynamodb_table" "this" {
  name                        = var.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = var.protect
  tags                        = var.tags
  dynamic "attribute" {
    for_each = toset(["pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk"])
    content {
      name = attribute.value
      type = "S"
    }
  }
  global_secondary_index {
    name            = "by-owner"
    projection_type = "ALL"
    key_schema {
      attribute_name = "gsi1pk"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "gsi1sk"
      key_type       = "RANGE"
    }
  }
  global_secondary_index {
    name            = "by-status"
    projection_type = "ALL"
    key_schema {
      attribute_name = "gsi2pk"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "gsi2sk"
      key_type       = "RANGE"
    }
  }
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = var.protect }
}
output "name" { value = aws_dynamodb_table.this.name }
output "arn" { value = aws_dynamodb_table.this.arn }
