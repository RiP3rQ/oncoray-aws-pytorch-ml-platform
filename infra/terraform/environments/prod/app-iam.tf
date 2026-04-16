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
}

data "aws_iam_policy_document" "app_irsa_assume_role" {
  for_each = local.app_service_accounts

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(data.aws_eks_cluster.current.identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(data.aws_eks_cluster.current.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values = [
        "system:serviceaccount:${each.value.namespace}:${each.value.service_account}",
      ]
    }
  }
}

resource "aws_iam_role" "app_irsa" {
  for_each = local.app_service_accounts

  name               = "${local.name_prefix}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.app_irsa_assume_role[each.key].json
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

resource "aws_iam_policy" "app_runtime" {
  for_each = {
    api    = data.aws_iam_policy_document.api_runtime.json
    worker = data.aws_iam_policy_document.worker_runtime.json
  }

  name   = "${local.name_prefix}-${each.key}-runtime"
  policy = each.value
}

resource "aws_iam_role_policy_attachment" "app_runtime" {
  for_each = aws_iam_policy.app_runtime

  role       = aws_iam_role.app_irsa[each.key].name
  policy_arn = each.value.arn
}
