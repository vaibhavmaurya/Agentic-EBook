variable "env"     { type = string }
variable "project" { type = string }

variable "sfn_execution_role_arn" { type = string }

variable "topic_loader_arn"          { type = string }
variable "topic_context_builder_arn" { type = string }
variable "planner_worker_arn"        { type = string }
variable "research_worker_arn"       { type = string }
variable "verifier_worker_arn"       { type = string }
variable "artifact_persister_arn"    { type = string }
variable "draft_worker_arn"          { type = string }
variable "editorial_worker_arn"      { type = string }
variable "draft_builder_worker_arn"  { type = string }
variable "diff_worker_arn"           { type = string }
variable "approval_worker_arn"       { type = string }
variable "publish_worker_arn"        { type = string }
variable "search_index_worker_arn"   { type = string }
