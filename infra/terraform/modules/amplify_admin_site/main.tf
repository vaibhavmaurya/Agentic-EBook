locals {
  app_name = "${var.project}-admin-${var.env}"
}

resource "aws_amplify_app" "admin_site" {
  name        = local.app_name
  description = "Agentic Ebook admin SPA (${var.env})"

  build_spec = <<-EOT
    version: 1
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: dist
        files:
          - "**/*"
      cache:
        paths:
          - node_modules/**/*
  EOT

  environment_variables = {
    VITE_API_ENDPOINT        = var.api_endpoint
    VITE_COGNITO_USER_POOL_ID = var.cognito_user_pool_id
    VITE_COGNITO_CLIENT_ID    = var.cognito_client_id
    NODE_ENV                  = "production"
  }

  tags = {
    Name = local.app_name
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.admin_site.id
  branch_name = var.env == "prod" ? "main" : "dev"
  stage       = var.env == "prod" ? "PRODUCTION" : "DEVELOPMENT"

  enable_auto_build = false
}
