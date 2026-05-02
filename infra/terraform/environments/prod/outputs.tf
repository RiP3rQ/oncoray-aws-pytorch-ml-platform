output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "aws_region" {
  description = "Primary AWS region for the production stack."
  value       = data.aws_region.current.name
}

output "vpc_id" {
  description = "Production VPC ID."
  value       = module.vpc.vpc_id
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA-backed add-ons."
  value       = module.eks.oidc_provider_arn
}

output "cloudwatch_workload_log_group_name" {
  description = "CloudWatch log group targeted by Fluent Bit."
  value       = aws_cloudwatch_log_group.eks_workloads.name
}

output "cloudwatch_alarm_topic_arn" {
  description = "SNS topic ARN used for CloudWatch alarm email notifications when alarm_email_addresses is non-empty."
  value       = try(aws_sns_topic.cloudwatch_alarms[0].arn, null)
}

output "frontend_bucket_name" {
  description = "Private S3 bucket for the Astro frontend."
  value       = aws_s3_bucket.frontend.bucket
}

output "prediction_artifacts_bucket_name" {
  description = "Private S3 bucket for prediction artifacts."
  value       = aws_s3_bucket.prediction_artifacts.bucket
}

output "frontend_distribution_id" {
  description = "CloudFront distribution ID for frontend cache invalidation."
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_distribution_domain_name" {
  description = "CloudFront domain name for the frontend."
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_route53_record_names" {
  description = "Frontend Route53 aliases managed by Terraform."
  value       = keys(aws_route53_record.frontend_ipv4)
}

output "api_route53_record_name" {
  description = "API Route53 CNAME managed by Terraform once api_dns_name is supplied."
  value       = try(aws_route53_record.api[0].fqdn, null)
}

output "frontend_waf_acl_arn" {
  description = "Frontend CloudFront WAF Web ACL ARN."
  value       = try(aws_wafv2_web_acl.frontend[0].arn, null)
}

output "api_waf_acl_arn" {
  description = "Regional WAF Web ACL ARN for ALB ingress annotations."
  value       = try(aws_wafv2_web_acl.api[0].arn, null)
}

output "ecr_repository_urls" {
  description = "Backend ECR repository URLs."
  value = {
    api           = aws_ecr_repository.api.repository_url
    model_service = aws_ecr_repository.model_service.repository_url
  }
}

output "postgres" {
  description = "Production PostgreSQL connection endpoints."
  value = {
    address  = aws_db_instance.postgres.address
    endpoint = aws_db_instance.postgres.endpoint
    port     = aws_db_instance.postgres.port
    db_name  = aws_db_instance.postgres.db_name
  }
}

output "redis" {
  description = "Production ElastiCache Redis endpoints."
  value = {
    primary_endpoint = aws_elasticache_replication_group.redis.primary_endpoint_address
    reader_endpoint  = aws_elasticache_replication_group.redis.reader_endpoint_address
    port             = aws_elasticache_replication_group.redis.port
  }
}

output "cluster_addon_role_arns" {
  description = "IRSA roles for cluster add-ons."
  value = var.use_localstack ? {} : {
    aws_load_balancer_controller = aws_iam_role.irsa["aws_load_balancer_controller"].arn
    external_secrets             = aws_iam_role.irsa["external_secrets"].arn
    fluent_bit                   = aws_iam_role.irsa["fluent_bit"].arn
  }
}

output "app_workload_role_arns" {
  description = "IRSA roles for application workloads."
  value       = var.use_localstack ? {} : module.workload_identities[0].role_arns
}

output "kubernetes_service_accounts" {
  description = "Stable Kubernetes service account names expected by Helm values and IRSA."
  value = {
    namespace      = var.kubernetes_namespace
    api            = var.api_service_account_name
    model_service  = var.model_service_service_account_name
    model_runtimes = var.model_runtime_service_account_names
  }
}

output "expected_parameter_store_paths" {
  description = "Recommended SSM Parameter Store keys for app secrets and config."
  value = {
    api = [
      "${local.ssm_parameter_prefix}/api/SECRET_KEY",
      "${local.ssm_parameter_prefix}/api/CORE_API_DATABASE_URL",
      "${local.ssm_parameter_prefix}/api/REDIS_HOST",
      "${local.ssm_parameter_prefix}/api/REDIS_PORT",
      "${local.ssm_parameter_prefix}/api/REDIS_SSL",
      "${local.ssm_parameter_prefix}/api/AWS_REGION",
      "${local.ssm_parameter_prefix}/api/MAIL_USERNAME",
      "${local.ssm_parameter_prefix}/api/MAIL_PASSWORD",
      "${local.ssm_parameter_prefix}/api/MAIL_FROM",
      "${local.ssm_parameter_prefix}/api/MAIL_PORT",
      "${local.ssm_parameter_prefix}/api/MAIL_SERVER",
      "${local.ssm_parameter_prefix}/api/MAIL_FROM_NAME",
      "${local.ssm_parameter_prefix}/api/MAIL_STARTTLS",
      "${local.ssm_parameter_prefix}/api/MAIL_SSL_TLS",
      "${local.ssm_parameter_prefix}/api/USE_CREDENTIALS",
      "${local.ssm_parameter_prefix}/api/VALIDATE_CERTS",
      "${local.ssm_parameter_prefix}/api/S3_BUCKET_NAME",
    ]
    model_service = [
      "${local.ssm_parameter_prefix}/model-service/EFFNETB0_MODEL_ARTIFACT_URL",
      "${local.ssm_parameter_prefix}/model-service/VITB16_MODEL_ARTIFACT_URL",
      "${local.ssm_parameter_prefix}/model-service/HF_USERNAME",
      "${local.ssm_parameter_prefix}/model-service/HF_TOKEN",
    ]
  }
}
