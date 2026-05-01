locals {
  app_service_accounts = {
    api = {
      namespace       = var.kubernetes_namespace
      service_account = var.api_service_account_name
    }
    worker = {
      namespace       = var.kubernetes_namespace
      service_account = var.worker_service_account_name
    }
  }

  model_runtime_service_accounts = {
    for slug, service_account in var.model_runtime_service_account_names : slug => {
      namespace       = var.kubernetes_namespace
      service_account = service_account
    }
  }
}

data "aws_iam_policy_document" "api_runtime" {
  statement {
    sid    = "AllowWorkerQueueSend"
    effect = "Allow"
    actions = [
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:SendMessage",
    ]
    resources = [
      aws_sqs_queue.worker.arn,
    ]
  }

  statement {
    sid    = "AllowPredictionArtifactsBucketRead"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.prediction_artifacts.arn,
    ]
  }

  statement {
    sid    = "AllowPredictionArtifactsObjectWrite"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetObject",
      "s3:PutObject",
      "s3:PutObjectTagging",
    ]
    resources = [
      "${aws_s3_bucket.prediction_artifacts.arn}/*",
    ]
  }
}

data "aws_iam_policy_document" "worker_runtime" {
  statement {
    sid    = "AllowWorkerQueueConsume"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [
      aws_sqs_queue.worker.arn,
    ]
  }
}

module "workload_identities" {
  count  = var.use_localstack ? 0 : 1
  source = "../../modules/workload-identities"

  app_runtime_policy_json = {
    api    = data.aws_iam_policy_document.api_runtime.json
    worker = data.aws_iam_policy_document.worker_runtime.json
  }
  app_service_accounts           = local.app_service_accounts
  model_runtime_service_accounts = local.model_runtime_service_accounts
  name_prefix                    = local.name_prefix
  oidc_issuer_url                = data.aws_eks_cluster.current[0].identity[0].oidc[0].issuer
  oidc_provider_arn              = module.eks.oidc_provider_arn
}
