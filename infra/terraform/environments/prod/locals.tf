locals {
  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    var.availability_zone_count,
  )

  name_prefix = "${var.project_name}-${var.environment}"

  eks_cluster_name = "${local.name_prefix}-eks"
  frontend_cloudfront_hosted_zone_id = "Z2FDTNDATAQYW2"
  postgres_identifier                = "${local.name_prefix}-postgres"
  redis_replication_group_id         = "${local.name_prefix}-redis"
  cloudwatch_workload_log_group_name = "/aws/eks/${local.eks_cluster_name}/workloads"
  route53_frontend_records_enabled   = var.route53_zone_id != "" && length(var.frontend_aliases) > 0
  route53_api_record_enabled         = var.route53_zone_id != "" && var.api_domain_name != "" && var.api_dns_name != ""

  public_subnets = [
    for idx, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, idx + 8)
  ]

  private_subnets = [
    for idx, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, idx)
  ]

  frontend_bucket_name = (
    var.frontend_bucket_name != ""
    ? var.frontend_bucket_name
    : "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  )

  worker_queue_name = (
    var.worker_queue_name != ""
    ? var.worker_queue_name
    : "${local.name_prefix}-worker"
  )

  worker_dlq_name = "${local.worker_queue_name}-dlq"

  api_repository_name           = "${var.project_name}/api"
  model_service_repository_name = "${var.project_name}/model-service"
  ssm_parameter_prefix          = "/${var.project_name}/${var.environment}"
  addon_service_accounts = {
    aws_load_balancer_controller = {
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller"
    }
    external_secrets = {
      namespace       = "external-secrets"
      service_account = "external-secrets"
    }
    fluent_bit = {
      namespace       = "amazon-cloudwatch"
      service_account = "fluent-bit"
    }
  }

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "pytorch-model"
    },
    var.tags,
  )
}
