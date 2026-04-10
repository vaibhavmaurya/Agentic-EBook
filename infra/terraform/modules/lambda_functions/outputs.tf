# Populated in M1-S8.
output "api_handler_arn"  { value = "" }
output "api_handler_name" { value = "" }

output "topic_loader_arn"          { value = "" }
output "topic_context_builder_arn" { value = "" }
output "planner_worker_arn"        { value = "" }
output "research_worker_arn"       { value = "" }
output "verifier_worker_arn"       { value = "" }
output "artifact_persister_arn"    { value = "" }
output "draft_worker_arn"          { value = "" }
output "editorial_worker_arn"      { value = "" }
output "draft_builder_worker_arn"  { value = "" }
output "diff_worker_arn"           { value = "" }
output "approval_worker_arn"       { value = "" }
output "publish_worker_arn"        { value = "" }
output "search_index_worker_arn"   { value = "" }
output "digest_worker_arn"         { value = "" }

# List of all worker function names for CloudWatch alarms
output "worker_function_names" { value = [] }
