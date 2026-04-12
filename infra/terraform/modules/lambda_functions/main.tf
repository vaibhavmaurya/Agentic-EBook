locals {
  name_prefix = "${var.project}-${var.env}"

  # Common environment variables injected into every Lambda
  common_env = {
    DYNAMODB_TABLE_NAME = var.dynamodb_table_name
    S3_ARTIFACT_BUCKET  = var.s3_bucket_name
    OPENAI_SECRET_NAME  = var.openai_secret_name
    STEP_FUNCTIONS_ARN  = var.state_machine_arn
    AWS_REGION_NAME     = var.aws_region
    ENV                 = var.env
    AMPLIFY_APP_ID      = var.amplify_public_app_id
    AMPLIFY_BRANCH      = var.amplify_branch
  }

  # Pipeline worker function definitions: name → handler file (relative to skeleton/)
  workers = {
    topic-loader          = "handler.lambda_handler"
    topic-context-builder = "handler.lambda_handler"
    planner-worker        = "handler.lambda_handler"
    research-worker       = "handler.lambda_handler"
    verifier-worker       = "handler.lambda_handler"
    artifact-persister    = "handler.lambda_handler"
    draft-worker          = "handler.lambda_handler"
    editorial-worker      = "handler.lambda_handler"
    draft-builder-worker  = "handler.lambda_handler"
    diff-worker           = "handler.lambda_handler"
    approval-worker       = "handler.lambda_handler"
    publish-worker        = "handler.lambda_handler"
    search-index-worker   = "handler.lambda_handler"
  }
}

# ── Skeleton deployment package (used by all functions in M1) ───────────────

data "archive_file" "skeleton" {
  type        = "zip"
  source_dir  = "${path.module}/skeleton"
  output_path = "${path.module}/skeleton.zip"
}

# ── CloudWatch log groups (explicit so retention is set before first invocation)

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "digest" {
  name              = "/aws/lambda/${local.name_prefix}-digest"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "workers" {
  for_each          = local.workers
  name              = "/aws/lambda/${local.name_prefix}-${each.key}"
  retention_in_days = 14
}

# ── API handler Lambda ───────────────────────────────────────────────────────

resource "aws_lambda_function" "api" {
  function_name    = "${local.name_prefix}-api"
  role             = var.api_lambda_role_arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.skeleton.output_path
  source_code_hash = data.archive_file.skeleton.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = local.common_env
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

# ── Digest Lambda ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "digest" {
  function_name    = "${local.name_prefix}-digest"
  role             = var.digest_lambda_role_arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.skeleton.output_path
  source_code_hash = data.archive_file.skeleton.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = local.common_env
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.digest]
}

# Allow EventBridge Scheduler to invoke the digest Lambda
resource "aws_lambda_permission" "scheduler_invoke_digest" {
  statement_id  = "AllowEventBridgeScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.digest.function_name
  principal     = "scheduler.amazonaws.com"
}

# ── Pipeline worker Lambdas (one per Step Functions state) ───────────────────

resource "aws_lambda_function" "workers" {
  for_each = local.workers

  function_name    = "${local.name_prefix}-${each.key}"
  role             = var.worker_lambda_role_arn
  runtime          = "python3.12"
  handler          = each.value
  filename         = data.archive_file.skeleton.output_path
  source_code_hash = data.archive_file.skeleton.output_base64sha256
  # Research/Writer/Editor agents may run long; give them headroom
  timeout     = 900
  memory_size = 512

  environment {
    variables = local.common_env
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_cloudwatch_log_group.workers]
}
