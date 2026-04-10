resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.project}-artifacts-${var.env}"
  force_destroy = var.env == "dev" ? true : false

  tags = {
    Name = "${var.project}-artifacts-${var.env}"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  # Clean up incomplete multipart uploads quickly
  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # Archive raw research artifacts to Glacier after 90 days
  rule {
    id     = "archive-raw-to-glacier"
    status = "Enabled"

    filter {
      prefix = "topics/"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  # Expire noncurrent versions after 30 days to control storage costs
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
