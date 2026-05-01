moved {
  from = aws_iam_role.app_irsa["api"]
  to   = module.workload_identities.aws_iam_role.app["api"]
}

moved {
  from = aws_iam_role.app_irsa["worker"]
  to   = module.workload_identities.aws_iam_role.app["worker"]
}

moved {
  from = aws_iam_role.model_runtime_irsa
  to   = module.workload_identities.aws_iam_role.model_runtime
}

moved {
  from = aws_iam_policy.app_runtime["api"]
  to   = module.workload_identities.aws_iam_policy.app_runtime["api"]
}

moved {
  from = aws_iam_policy.app_runtime["worker"]
  to   = module.workload_identities.aws_iam_policy.app_runtime["worker"]
}

moved {
  from = aws_iam_role_policy_attachment.app_runtime["api"]
  to   = module.workload_identities.aws_iam_role_policy_attachment.app_runtime["api"]
}

moved {
  from = aws_iam_role_policy_attachment.app_runtime["worker"]
  to   = module.workload_identities.aws_iam_role_policy_attachment.app_runtime["worker"]
}
