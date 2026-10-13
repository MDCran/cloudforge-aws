variable "name" { type = string }
variable "callback_urls" { type = list(string) }
variable "logout_urls" { type = list(string) }
variable "tags" { type = map(string) }
resource "aws_cognito_user_pool" "this" {
  name = var.name
  admin_create_user_config { allow_admin_create_user_only = true }
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  user_pool_add_ons { advanced_security_mode = "OFF" }
  tags = var.tags
}
resource "aws_cognito_resource_server" "api" {
  identifier   = "cloudforge-api"
  name         = "CloudForge jobs"
  user_pool_id = aws_cognito_user_pool.this.id
  scope {
    scope_name        = "jobs"
    scope_description = "Manage owned CSV processing jobs"
  }
}
resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${var.name}-web"
  user_pool_id                         = aws_cognito_user_pool.this.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "cloudforge-api/jobs"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  prevent_user_existence_errors        = "ENABLED"
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  depends_on = [aws_cognito_resource_server.api]
}
resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.name
  user_pool_id = aws_cognito_user_pool.this.id
}
resource "aws_cognito_user_group" "operators" {
  name         = "operators"
  user_pool_id = aws_cognito_user_pool.this.id
}
output "pool_id" { value = aws_cognito_user_pool.this.id }
output "client_id" { value = aws_cognito_user_pool_client.web.id }
output "endpoint" { value = aws_cognito_user_pool.this.endpoint }
output "domain" { value = aws_cognito_user_pool_domain.this.domain }
