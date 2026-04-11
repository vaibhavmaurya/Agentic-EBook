# Platform-level schedule group.
# Per-topic schedules are created dynamically at runtime by the API Lambda —
# NOT managed by Terraform (per architecture constraint).
resource "aws_scheduler_schedule_group" "topics" {
  name = "${var.project}-${var.env}-topics"

  tags = {
    Name = "${var.project}-${var.env}-topics"
  }
}

# ── Weekly digest schedule (Terraform-managed, not per-topic) ─────────────────

resource "aws_scheduler_schedule" "weekly_digest" {
  name       = "${var.project}-${var.env}-weekly-digest"
  group_name = "default"

  schedule_expression          = var.digest_schedule_expression
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 30
  }

  target {
    arn      = var.digest_lambda_arn
    role_arn = var.digest_scheduler_role_arn

    input = jsonencode({
      source = "eventbridge_scheduler"
      name   = "weekly_digest"
    })

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}
