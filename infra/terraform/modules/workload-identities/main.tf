locals {
  oidc_condition_prefix = replace(var.oidc_issuer_url, "https://", "")
}

data "aws_iam_policy_document" "app_assume_role" {
  for_each = var.app_service_accounts

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_condition_prefix}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_condition_prefix}:sub"
      values = [
        "system:serviceaccount:${each.value.namespace}:${each.value.service_account}",
      ]
    }
  }
}

resource "aws_iam_role" "app" {
  for_each = var.app_service_accounts

  name               = "${var.name_prefix}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.app_assume_role[each.key].json
}

data "aws_iam_policy_document" "model_runtime_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_condition_prefix}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_condition_prefix}:sub"
      values = [
        for account in values(var.model_runtime_service_accounts) :
        "system:serviceaccount:${account.namespace}:${account.service_account}"
      ]
    }
  }
}

resource "aws_iam_role" "model_runtime" {
  name               = "${var.name_prefix}-model-service"
  assume_role_policy = data.aws_iam_policy_document.model_runtime_assume_role.json
}

resource "aws_iam_policy" "app_runtime" {
  for_each = var.app_runtime_policy_json

  name   = "${var.name_prefix}-${each.key}-runtime"
  policy = each.value
}

resource "aws_iam_role_policy_attachment" "app_runtime" {
  for_each = aws_iam_policy.app_runtime

  role       = aws_iam_role.app[each.key].name
  policy_arn = each.value.arn
}
