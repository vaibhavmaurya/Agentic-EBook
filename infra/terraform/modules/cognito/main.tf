resource "aws_cognito_user_pool" "main" {
  name = "${var.project}-${var.env}"

  # Admins sign in with email
  username_attributes = ["email"]

  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Name = "${var.project}-${var.env}"
  }
}

resource "aws_cognito_user_pool_client" "admin_spa" {
  name         = "${var.project}-admin-spa-${var.env}"
  user_pool_id = aws_cognito_user_pool.main.id

  # SPA — no client secret (public client)
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  # Tokens valid for development convenience; tighten for prod
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}

resource "aws_cognito_user_group" "admins" {
  name         = "admins"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Platform administrators — access to all /admin/* API routes"
}
