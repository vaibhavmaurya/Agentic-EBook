variable "env"            { type = string }
variable "project"        { type = string }
variable "aws_region"     { type = string }
variable "aws_account_id" { type = string }

variable "dynamodb_table_arn" { type = string }
variable "s3_bucket_arn"      { type = string }
variable "openai_secret_arn"  { type = string }
variable "state_machine_arn"  { type = string }
variable "ses_sender_email"   { type = string }
variable "digest_lambda_arn"  { type = string }
