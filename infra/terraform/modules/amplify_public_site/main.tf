locals {
  app_name = "${var.project}-public-${var.env}"
}

resource "aws_amplify_app" "public_site" {
  name        = local.app_name
  description = "Agentic Ebook public reader site (${var.env})"

  # Astro static export — built and deployed via CI or manual push
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
    VITE_API_ENDPOINT = var.api_endpoint
    NODE_ENV          = "production"
  }

  tags = {
    Name = local.app_name
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.public_site.id
  branch_name = var.env == "prod" ? "main" : "dev"
  stage       = var.env == "prod" ? "PRODUCTION" : "DEVELOPMENT"

  enable_auto_build = false
}
