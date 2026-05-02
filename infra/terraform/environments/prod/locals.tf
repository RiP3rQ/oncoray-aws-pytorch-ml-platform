locals {
  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    var.availability_zone_count,
  )

  name_prefix = "${var.project_name}-${var.environment}"

  eks_cluster_name                   = "${local.name_prefix}-eks"
  frontend_cloudfront_hosted_zone_id = "Z2FDTNDATAQYW2"
  postgres_identifier                = "${local.name_prefix}-postgres"
  postgres_password                  = var.db_password != "" ? var.db_password : random_password.postgres[0].result
  redis_replication_group_id         = "${local.name_prefix}-redis"
  cloudwatch_workload_log_group_name = "/aws/eks/${local.eks_cluster_name}/workloads"

  managed_domain_name = trimspace(var.domain_name)
  managed_zone_enabled = (
    var.create_route53_zone && local.managed_domain_name != ""
  )
  managed_zone_available = (
    var.route53_zone_id != "" || local.managed_zone_enabled
  )
  managed_zone_id = (
    var.route53_zone_id != ""
    ? var.route53_zone_id
    : try(aws_route53_zone.primary[0].zone_id, "")
  )
  frontend_aliases = (
    length(var.frontend_aliases) > 0
    ? var.frontend_aliases
    : (
      local.managed_domain_name != ""
      ? ["app.${local.managed_domain_name}"]
      : []
    )
  )
  api_domain_name = (
    var.api_domain_name != ""
    ? var.api_domain_name
    : (
      local.managed_domain_name != ""
      ? "api.${local.managed_domain_name}"
      : ""
    )
  )
  frontend_custom_domain_enabled = (
    var.frontend_acm_certificate_arn != "" || var.enable_managed_acm_certificates
  )
  frontend_distribution_aliases = (
    local.frontend_custom_domain_enabled
    ? local.frontend_aliases
    : []
  )
  frontend_acm_certificate_arn = (
    var.frontend_acm_certificate_arn != ""
    ? var.frontend_acm_certificate_arn
    : try(aws_acm_certificate_validation.frontend[0].certificate_arn, "")
  )
  api_acm_certificate_arn = try(aws_acm_certificate_validation.api[0].certificate_arn, "")
  route53_frontend_records_enabled = (
    local.managed_zone_available && length(local.frontend_distribution_aliases) > 0
  )
  route53_api_record_enabled = (
    local.managed_zone_available && local.api_domain_name != "" && var.api_dns_name != ""
  )

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

  prediction_artifacts_bucket_name = (
    var.prediction_artifacts_bucket_name != ""
    ? var.prediction_artifacts_bucket_name
    : "${local.name_prefix}-artifacts-${data.aws_caller_identity.current.account_id}"
  )

  cloudtrail_bucket_name = "${local.name_prefix}-cloudtrail-${data.aws_caller_identity.current.account_id}"
  cloudtrail_name        = local.name_prefix

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
