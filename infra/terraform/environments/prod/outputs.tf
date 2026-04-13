output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA-backed add-ons."
  value       = module.eks.oidc_provider_arn
}

output "frontend_bucket_name" {
  description = "Private S3 bucket for the Astro frontend."
  value       = aws_s3_bucket.frontend.bucket
}

output "frontend_distribution_id" {
  description = "CloudFront distribution ID for frontend cache invalidation."
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_distribution_domain_name" {
  description = "CloudFront domain name for the frontend."
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "worker_queue_url" {
  description = "Primary worker SQS queue URL."
  value       = aws_sqs_queue.worker.url
}

output "worker_dlq_url" {
  description = "Dead-letter queue URL for worker failures."
  value       = aws_sqs_queue.worker_dlq.url
}

output "ecr_repository_urls" {
  description = "Backend ECR repository URLs."
  value = {
    api           = aws_ecr_repository.api.repository_url
    model_service = aws_ecr_repository.model_service.repository_url
  }
}

output "expected_parameter_store_paths" {
  description = "Recommended SSM Parameter Store keys for app secrets and config."
  value = {
    api = [
      "${local.ssm_parameter_prefix}/api/SECRET_KEY",
      "${local.ssm_parameter_prefix}/api/CORE_API_DATABASE_URL",
      "${local.ssm_parameter_prefix}/api/REDIS_HOST",
      "${local.ssm_parameter_prefix}/api/MAIL_USERNAME",
      "${local.ssm_parameter_prefix}/api/MAIL_PASSWORD",
      "${local.ssm_parameter_prefix}/api/S3_BUCKET_NAME",
    ]
    worker = [
      "${local.ssm_parameter_prefix}/worker/AWS_REGION",
      "${local.ssm_parameter_prefix}/worker/SQS_QUEUE_URL",
    ]
    model_service = [
      "${local.ssm_parameter_prefix}/model-service/HF_MODEL_REPOSITORY",
      "${local.ssm_parameter_prefix}/model-service/HF_MODEL_REVISION",
    ]
  }
}
