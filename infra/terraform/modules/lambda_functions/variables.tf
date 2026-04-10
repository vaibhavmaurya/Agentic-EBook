variable "env"        { type = string }
variable "project"    { type = string }
variable "aws_region" { type = string }

variable "dynamodb_table_name" { type = string }
variable "s3_bucket_name"      { type = string }
variable "openai_secret_name"  { type = string }
variable "state_machine_arn"   { type = string }

variable "api_lambda_role_arn"    { type = string }
variable "worker_lambda_role_arn" { type = string }
variable "digest_lambda_role_arn" { type = string }
