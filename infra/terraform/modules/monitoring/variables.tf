variable "env"            { type = string }
variable "project"        { type = string }
variable "aws_region"     { type = string }
variable "aws_account_id" { type = string }

variable "api_id"            { type = string }
variable "state_machine_arn" { type = string }
variable "alarm_email"       { type = string  default = "" }

variable "worker_function_names" {
  type    = list(string)
  default = []
}
