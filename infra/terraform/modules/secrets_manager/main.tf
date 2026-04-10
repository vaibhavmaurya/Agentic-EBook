resource "aws_secretsmanager_secret" "openai_key" {
  name        = "${var.project}/openai-key"
  description = "OpenAI API key for the ${var.project} ${var.env} environment"

  # Allow immediate deletion in dev (no recovery window)
  recovery_window_in_days = var.env == "dev" ? 0 : 30

  tags = {
    Name = "${var.project}-openai-key-${var.env}"
  }
}

resource "aws_secretsmanager_secret_version" "openai_key_placeholder" {
  secret_id     = aws_secretsmanager_secret.openai_key.id
  secret_string = jsonencode({ api_key = "REPLACE_ME" })

  # Prevent Terraform from overwriting the secret after it's been set manually
  lifecycle {
    ignore_changes = [secret_string]
  }
}
