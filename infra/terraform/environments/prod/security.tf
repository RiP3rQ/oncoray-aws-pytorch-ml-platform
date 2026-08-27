resource "aws_s3_bucket" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = local.cloudtrail_bucket_name
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "cloudtrail_bucket" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  statement {
    sid    = "AllowCloudTrailAclCheck"
    effect = "Allow"

    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail[0].arn]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.cloudtrail_name}"]
    }
  }

  statement {
    sid    = "AllowCloudTrailWrite"
    effect = "Allow"

    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.cloudtrail[0].arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*",
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.cloudtrail_name}"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail[0].id
  policy = data.aws_iam_policy_document.cloudtrail_bucket[0].json
}

resource "aws_cloudtrail" "main" {
  count = var.enable_cloudtrail && !var.use_localstack ? 1 : 0

  name                          = local.cloudtrail_name
  s3_bucket_name                = aws_s3_bucket.cloudtrail[0].id
  enable_log_file_validation    = true
  include_global_service_events = true
  is_multi_region_trail         = true

  event_selector {
    include_management_events = true
    read_write_type           = "All"
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail]
}
