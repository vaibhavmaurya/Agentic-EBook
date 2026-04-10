###############################################################################
# Dev environment — outputs
# Copy these values into .env.local after terraform apply.
###############################################################################

output "dynamodb_table_name" {
  description = "DynamoDB table name → DYNAMODB_TABLE_NAME in .env.local"
  value       = module.dynamodb.table_name
}

output "s3_artifact_bucket" {
  description = "S3 artifact bucket name → S3_ARTIFACT_BUCKET in .env.local"
  value       = module.s3_artifacts.bucket_name
}

output "openai_secret_name" {
  description = "Secrets Manager secret name → OPENAI_SECRET_NAME in .env.local"
  value       = module.secrets_manager.secret_name
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID → COGNITO_USER_POOL_ID in .env.local"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito app client ID → COGNITO_CLIENT_ID in .env.local"
  value       = module.cognito.client_id
}

output "api_endpoint" {
  description = "API Gateway HTTP API endpoint → ADMIN_API_BASE_URL and PUBLIC_API_BASE_URL in .env.local"
  value       = module.api_gateway.api_endpoint
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN → STEP_FUNCTIONS_ARN in .env.local"
  value       = local.state_machine_arn
}

output "schedule_group_name" {
  description = "EventBridge Scheduler group name for per-topic schedules."
  value       = module.eventbridge_scheduler.schedule_group_name
}

output "public_site_domain" {
  description = "Amplify public site default domain."
  value       = module.amplify_public_site.default_domain
}

output "admin_site_domain" {
  description = "Amplify admin site default domain."
  value       = module.amplify_admin_site.default_domain
}
