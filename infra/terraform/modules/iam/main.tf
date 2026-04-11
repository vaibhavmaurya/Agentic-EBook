locals {
  name_prefix = "${var.project}-${var.env}"
}

# ── Shared assume-role policy for Lambda ────────────────────────────────────

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ── API Lambda role ──────────────────────────────────────────────────────────
# Permissions: DynamoDB CRUD on the single table, start SFN executions,
# EventBridge Scheduler CRUD (for per-topic schedule management), SES send.

resource "aws_iam_role" "api_lambda" {
  name               = "${local.name_prefix}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "api_lambda" {
  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
      "dynamodb:Scan",
    ]
    resources = [
      var.dynamodb_table_arn,
      "${var.dynamodb_table_arn}/index/*",
    ]
  }

  statement {
    sid    = "StartSFN"
    effect = "Allow"
    actions = [
      "states:StartExecution",
      "states:DescribeExecution",
    ]
    resources = [var.state_machine_arn]
  }

  statement {
    sid    = "EventBridgeScheduler"
    effect = "Allow"
    actions = [
      "scheduler:CreateSchedule",
      "scheduler:UpdateSchedule",
      "scheduler:DeleteSchedule",
      "scheduler:GetSchedule",
      "scheduler:ListSchedules",
    ]
    resources = ["arn:aws:scheduler:${var.aws_region}:${var.aws_account_id}:schedule/default/*"]
  }

  statement {
    sid    = "IAMPassRoleForScheduler"
    effect = "Allow"
    actions = ["iam:PassRole"]
    resources = ["arn:aws:iam::${var.aws_account_id}:role/${local.name_prefix}-scheduler"]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${local.name_prefix}-api:*"]
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name   = "api-lambda-policy"
  role   = aws_iam_role.api_lambda.id
  policy = data.aws_iam_policy_document.api_lambda.json
}

# ── Worker Lambda role ───────────────────────────────────────────────────────
# Permissions: DynamoDB CRUD, S3 full access to artifact bucket, Secrets Manager
# read (OpenAI key), SFN SendTaskSuccess/Failure (approval callback), SES send.

resource "aws_iam_role" "worker_lambda" {
  name               = "${local.name_prefix}-worker-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "worker_lambda" {
  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
    ]
    resources = [
      var.dynamodb_table_arn,
      "${var.dynamodb_table_arn}/index/*",
    ]
  }

  statement {
    sid    = "S3Artifacts"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "SecretsManager"
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [var.openai_secret_arn]
  }

  statement {
    sid    = "SFNCallback"
    effect = "Allow"
    actions = [
      "states:SendTaskSuccess",
      "states:SendTaskFailure",
      "states:SendTaskHeartbeat",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SES"
    effect = "Allow"
    actions = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["arn:aws:ses:${var.aws_region}:${var.aws_account_id}:identity/${var.ses_sender_email}"]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${local.name_prefix}-worker-*:*"]
  }
}

resource "aws_iam_role_policy" "worker_lambda" {
  name   = "worker-lambda-policy"
  role   = aws_iam_role.worker_lambda.id
  policy = data.aws_iam_policy_document.worker_lambda.json
}

# ── Digest Lambda role ───────────────────────────────────────────────────────
# Permissions: DynamoDB query (read recent publish events), SES send.

resource "aws_iam_role" "digest_lambda" {
  name               = "${local.name_prefix}-digest-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "digest_lambda" {
  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:PutItem",
      "dynamodb:Scan",
    ]
    resources = [
      var.dynamodb_table_arn,
      "${var.dynamodb_table_arn}/index/*",
    ]
  }

  statement {
    sid    = "SES"
    effect = "Allow"
    actions = ["ses:SendEmail", "ses:SendRawEmail", "sesv2:SendEmail"]
    resources = ["arn:aws:ses:${var.aws_region}:${var.aws_account_id}:identity/${var.ses_sender_email}"]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${local.name_prefix}-digest:*"]
  }
}

resource "aws_iam_role_policy" "digest_lambda" {
  name   = "digest-lambda-policy"
  role   = aws_iam_role.digest_lambda.id
  policy = data.aws_iam_policy_document.digest_lambda.json
}

# ── EventBridge Scheduler role (digest Lambda invoke) ────────────────────────
# Allows EventBridge Scheduler to invoke the digest Lambda directly.

resource "aws_iam_role" "digest_scheduler" {
  name = "${local.name_prefix}-digest-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "scheduler.amazonaws.com" }
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = var.aws_account_id
        }
      }
    }]
  })
}

data "aws_iam_policy_document" "digest_scheduler" {
  statement {
    sid     = "InvokeDigestLambda"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [var.digest_lambda_arn]
  }
}

resource "aws_iam_role_policy" "digest_scheduler" {
  name   = "digest-scheduler-policy"
  role   = aws_iam_role.digest_scheduler.id
  policy = data.aws_iam_policy_document.digest_scheduler.json
}

# ── Step Functions execution role ────────────────────────────────────────────
# Allows SFN to invoke all worker Lambda functions and write CloudWatch logs.

resource "aws_iam_role" "sfn_execution" {
  name = "${local.name_prefix}-sfn-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "states.amazonaws.com" }
    }]
  })
}

data "aws_iam_policy_document" "sfn_execution" {
  statement {
    sid    = "InvokeLambda"
    effect = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:${local.name_prefix}-*",
    ]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sfn_execution" {
  name   = "sfn-execution-policy"
  role   = aws_iam_role.sfn_execution.id
  policy = data.aws_iam_policy_document.sfn_execution.json
}

# ── EventBridge Scheduler role ───────────────────────────────────────────────
# Allows EventBridge Scheduler to start Step Functions executions.

resource "aws_iam_role" "scheduler" {
  name = "${local.name_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = {
        Service = "scheduler.amazonaws.com"
      }
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = var.aws_account_id
        }
      }
    }]
  })
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid    = "StartSFN"
    effect = "Allow"
    actions = ["states:StartExecution"]
    resources = [var.state_machine_arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "scheduler-policy"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
