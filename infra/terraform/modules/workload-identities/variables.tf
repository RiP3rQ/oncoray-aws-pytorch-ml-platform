variable "app_service_accounts" {
  description = "Application workload service accounts keyed by workload name."
  type = map(object({
    namespace       = string
    service_account = string
  }))
}

variable "app_runtime_policy_json" {
  description = "Runtime IAM policy documents keyed by workload name."
  type        = map(string)
}

variable "model_runtime_service_accounts" {
  description = "Model Runtime service accounts keyed by model slug."
  type = map(object({
    namespace       = string
    service_account = string
  }))
}

variable "name_prefix" {
  description = "Name prefix used for IAM roles and policies."
  type        = string
}

variable "oidc_issuer_url" {
  description = "EKS OIDC issuer URL."
  type        = string
}

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN."
  type        = string
}
