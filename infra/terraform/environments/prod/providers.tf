provider "aws" {
  region = var.aws_region

  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [var.localstack_endpoint] : []

    content {
      acm         = endpoints.value
      cloudfront  = endpoints.value
      cloudwatch  = endpoints.value
      ec2         = endpoints.value
      ecr         = endpoints.value
      eks         = endpoints.value
      elasticache = endpoints.value
      elbv2       = endpoints.value
      iam         = endpoints.value
      kms         = endpoints.value
      logs        = endpoints.value
      rds         = endpoints.value
      route53     = endpoints.value
      s3          = endpoints.value
      sqs         = endpoints.value
      ssm         = endpoints.value
      sts         = endpoints.value
      wafv2       = endpoints.value
    }
  }

  default_tags {
    tags = local.common_tags
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [var.localstack_endpoint] : []

    content {
      acm         = endpoints.value
      cloudfront  = endpoints.value
      cloudwatch  = endpoints.value
      ec2         = endpoints.value
      ecr         = endpoints.value
      eks         = endpoints.value
      elasticache = endpoints.value
      elbv2       = endpoints.value
      iam         = endpoints.value
      kms         = endpoints.value
      logs        = endpoints.value
      rds         = endpoints.value
      route53     = endpoints.value
      s3          = endpoints.value
      sqs         = endpoints.value
      ssm         = endpoints.value
      sts         = endpoints.value
      wafv2       = endpoints.value
    }
  }

  default_tags {
    tags = local.common_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
