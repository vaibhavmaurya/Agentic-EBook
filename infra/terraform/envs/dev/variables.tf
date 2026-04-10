###############################################################################
# Dev environment — input variables
###############################################################################

variable "env" {
  description = "Environment name used in resource naming and tagging."
  type        = string
  default     = "dev"
}

variable "project" {
  description = "Project name prefix used in all resource names."
  type        = string
  default     = "ebook-platform"
}

variable "aws_region" {
  description = "AWS region to deploy all resources into."
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account ID. Used for constructing ARNs in IAM policies."
  type        = string
}

variable "ses_sender_email" {
  description = "Email address verified in SES used as the From address for admin notifications and weekly digests."
  type        = string
}

variable "owner_email" {
  description = "Email address of the ebook owner. Receives the weekly digest."
  type        = string
}

variable "alarm_email" {
  description = "Optional email to subscribe to CloudWatch alarm SNS topic. Leave empty to skip subscription."
  type        = string
  default     = ""
}
