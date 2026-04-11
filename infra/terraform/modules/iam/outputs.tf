output "api_lambda_role_arn"        { value = aws_iam_role.api_lambda.arn }
output "worker_lambda_role_arn"     { value = aws_iam_role.worker_lambda.arn }
output "digest_lambda_role_arn"     { value = aws_iam_role.digest_lambda.arn }
output "sfn_execution_role_arn"     { value = aws_iam_role.sfn_execution.arn }
output "scheduler_role_arn"         { value = aws_iam_role.scheduler.arn }
output "digest_scheduler_role_arn"  { value = aws_iam_role.digest_scheduler.arn }
