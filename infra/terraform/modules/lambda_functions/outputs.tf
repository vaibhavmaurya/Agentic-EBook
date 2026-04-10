output "api_handler_arn"  { value = aws_lambda_function.api.arn }
output "api_handler_name" { value = aws_lambda_function.api.function_name }

output "topic_loader_arn"          { value = aws_lambda_function.workers["topic-loader"].arn }
output "topic_context_builder_arn" { value = aws_lambda_function.workers["topic-context-builder"].arn }
output "planner_worker_arn"        { value = aws_lambda_function.workers["planner-worker"].arn }
output "research_worker_arn"       { value = aws_lambda_function.workers["research-worker"].arn }
output "verifier_worker_arn"       { value = aws_lambda_function.workers["verifier-worker"].arn }
output "artifact_persister_arn"    { value = aws_lambda_function.workers["artifact-persister"].arn }
output "draft_worker_arn"          { value = aws_lambda_function.workers["draft-worker"].arn }
output "editorial_worker_arn"      { value = aws_lambda_function.workers["editorial-worker"].arn }
output "draft_builder_worker_arn"  { value = aws_lambda_function.workers["draft-builder-worker"].arn }
output "diff_worker_arn"           { value = aws_lambda_function.workers["diff-worker"].arn }
output "approval_worker_arn"       { value = aws_lambda_function.workers["approval-worker"].arn }
output "publish_worker_arn"        { value = aws_lambda_function.workers["publish-worker"].arn }
output "search_index_worker_arn"   { value = aws_lambda_function.workers["search-index-worker"].arn }
output "digest_worker_arn"         { value = aws_lambda_function.digest.arn }

output "worker_function_names" {
  value = [for k, fn in aws_lambda_function.workers : fn.function_name]
}
