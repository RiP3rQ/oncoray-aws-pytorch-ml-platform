data "aws_eks_cluster" "current" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}

resource "aws_cloudwatch_log_group" "eks_workloads" {
  name              = local.cloudwatch_workload_log_group_name
  retention_in_days = var.log_retention_in_days
}

data "aws_iam_policy_document" "irsa_assume_role" {
  for_each = local.addon_service_accounts

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

resource "aws_iam_role" "irsa" {
  for_each = local.addon_service_accounts

  name               = "${local.name_prefix}-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.irsa_assume_role[each.key].json
}

resource "aws_iam_policy" "aws_load_balancer_controller" {
  name   = "${local.name_prefix}-aws-load-balancer-controller"
  policy = file("${path.module}/policies/aws-load-balancer-controller-iam-policy.json")
}

resource "aws_iam_policy" "external_secrets" {
  name   = "${local.name_prefix}-external-secrets"
  policy = data.aws_iam_policy_document.external_secrets.json
}

resource "aws_iam_policy" "fluent_bit" {
  name   = "${local.name_prefix}-fluent-bit"
  policy = data.aws_iam_policy_document.fluent_bit.json
}

data "aws_iam_policy_document" "external_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "ssm:DescribeParameters",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_parameter_prefix}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "fluent_bit" {
  statement {
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = [
      "${aws_cloudwatch_log_group.eks_workloads.arn}:*",
    ]
  }
}

resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller" {
  role       = aws_iam_role.irsa["aws_load_balancer_controller"].name
  policy_arn = aws_iam_policy.aws_load_balancer_controller.arn
}

resource "aws_iam_role_policy_attachment" "external_secrets" {
  role       = aws_iam_role.irsa["external_secrets"].name
  policy_arn = aws_iam_policy.external_secrets.arn
}

resource "aws_iam_role_policy_attachment" "fluent_bit" {
  role       = aws_iam_role.irsa["fluent_bit"].name
  policy_arn = aws_iam_policy.fluent_bit.arn
}
