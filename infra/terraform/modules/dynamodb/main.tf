resource "aws_dynamodb_table" "main" {
  name         = "${var.project}-${var.env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # GSI1 — list topics/reviews sorted by order
  attribute {
    name = "ENTITY_TYPE"
    type = "S"
  }

  attribute {
    name = "ORDER_KEY"
    type = "S"
  }

  # GSI2 — operational monitoring by run status
  attribute {
    name = "RUN_STATUS"
    type = "S"
  }

  attribute {
    name = "UPDATED_AT"
    type = "S"
  }

  # GSI3 — pending review queue
  attribute {
    name = "REVIEW_STATUS"
    type = "S"
  }

  # GSI4 — schedule views
  attribute {
    name = "SCHEDULE_BUCKET"
    type = "S"
  }

  attribute {
    name = "NEXT_RUN_AT"
    type = "S"
  }

  # GSI5 — feedback analysis per topic
  attribute {
    name = "FEEDBACK_TOPIC"
    type = "S"
  }

  attribute {
    name = "CREATED_AT"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI1-EntityType-OrderKey"
    hash_key        = "ENTITY_TYPE"
    range_key       = "ORDER_KEY"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "GSI2-RunStatus-UpdatedAt"
    hash_key        = "RUN_STATUS"
    range_key       = "UPDATED_AT"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "GSI3-ReviewStatus-UpdatedAt"
    hash_key        = "REVIEW_STATUS"
    range_key       = "UPDATED_AT"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "GSI4-ScheduleBucket-NextRunAt"
    hash_key        = "SCHEDULE_BUCKET"
    range_key       = "NEXT_RUN_AT"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "GSI5-FeedbackTopic-CreatedAt"
    hash_key        = "FEEDBACK_TOPIC"
    range_key       = "CREATED_AT"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.project}-${var.env}"
  }
}
