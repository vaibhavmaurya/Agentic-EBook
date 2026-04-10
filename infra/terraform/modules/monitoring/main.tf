locals {
  name_prefix = "${var.project}-${var.env}"
}

# ── SNS topic for alarms ─────────────────────────────────────────────────────

resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ── Lambda error alarms (one per worker function) ────────────────────────────

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(var.worker_function_names)

  alarm_name          = "${each.key}-errors"
  alarm_description   = "Lambda function ${each.key} error rate elevated"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.key
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
}

# ── Step Functions execution failures ────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "sfn_failures" {
  alarm_name          = "${local.name_prefix}-sfn-failures"
  alarm_description   = "Step Functions pipeline execution failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
}

# ── API Gateway 5xx errors ────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name_prefix}-api-5xx"
  alarm_description   = "API Gateway 5xx error rate elevated"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = var.api_id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
}

# ── CloudWatch dashboard ──────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name_prefix

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "API Gateway Requests & Errors"
          region = var.aws_region
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", var.api_id],
            ["AWS/ApiGateway", "5XXError", "ApiId", var.api_id],
            ["AWS/ApiGateway", "4XXError", "ApiId", var.api_id],
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Step Functions Executions"
          region = var.aws_region
          metrics = [
            ["AWS/States", "ExecutionsStarted", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", var.state_machine_arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", var.state_machine_arn],
          ]
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
        }
      }
    ]
  })
}
