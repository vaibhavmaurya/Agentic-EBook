variable "env"     { type = string }
variable "project" { type = string }

variable "scheduler_role_arn"    { type = string }
variable "state_machine_arn"     { type = string }
variable "digest_lambda_arn"     { type = string }
variable "digest_lambda_role_arn" { type = string }

# Cron expression for the weekly digest — default: every Monday at 08:00 UTC
variable "digest_schedule_expression" {
  type    = string
  default = "cron(0 8 ? * MON *)"
}
