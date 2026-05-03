output "app_role_arns" {
  description = "IRSA role ARNs keyed by application workload name."
  value = {
    for name, role in aws_iam_role.app : name => role.arn
  }
}

output "model_runtime_role_arn" {
  description = "IRSA role ARN shared by Model Runtime workloads."
  value       = aws_iam_role.model_runtime.arn
}

output "role_arns" {
  description = "IRSA role ARNs keyed by workload name."
  value = merge(
    {
      for name, role in aws_iam_role.app : name => role.arn
    },
    {
      model_runtime_host = aws_iam_role.model_runtime.arn
    },
  )
}
