variable "env"     { type = string }
variable "project" { type = string }

variable "cognito_user_pool_arn" { type = string }
variable "cognito_user_pool_id"  { type = string }
variable "cognito_client_id"     { type = string }

variable "api_handler_arn"  { type = string }
variable "api_handler_name" { type = string }
