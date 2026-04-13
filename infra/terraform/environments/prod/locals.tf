locals {
  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    var.availability_zone_count,
  )

  name_prefix = "${var.project_name}-${var.environment}"

  eks_cluster_name = "${local.name_prefix}-eks"

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
