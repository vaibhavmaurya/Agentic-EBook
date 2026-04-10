output "schedule_group_name" { value = aws_scheduler_schedule_group.topics.name }
output "scheduler_role_arn"  { value = var.scheduler_role_arn }
