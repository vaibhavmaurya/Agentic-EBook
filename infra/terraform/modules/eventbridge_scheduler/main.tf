# Platform-level schedule group.
# Per-topic schedules are created dynamically at runtime by the API Lambda —
# NOT managed by Terraform (per architecture constraint).
resource "aws_scheduler_schedule_group" "topics" {
  name = "${var.project}-${var.env}-topics"

  tags = {
    Name = "${var.project}-${var.env}-topics"
  }
}
