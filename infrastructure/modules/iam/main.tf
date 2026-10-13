variable "name" { type = string }
variable "statements" { type = any }
variable "tags" { type = map(string) }
resource "aws_iam_role" "this" {
  name = var.name
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
  tags = var.tags
}
resource "aws_iam_role_policy" "this" {
  name   = "execution"
  role   = aws_iam_role.this.id
  policy = jsonencode({ Version = "2012-10-17", Statement = var.statements })
}
output "arn" { value = aws_iam_role.this.arn }
