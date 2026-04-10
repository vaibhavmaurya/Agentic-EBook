output "secret_arn"  { value = aws_secretsmanager_secret.openai_key.arn }
output "secret_name" { value = aws_secretsmanager_secret.openai_key.name }
