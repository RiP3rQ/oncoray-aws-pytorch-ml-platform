variable "project_name" {
  description = "Project slug used in resource names."
  type        = string
  default     = "pytorch-model"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "Primary AWS region."
  type        = string
  default     = "eu-central-1"
}

variable "expected_aws_account_id" {
  description = "Expected 12-digit AWS account ID for production safety checks. Leave empty only for non-production emulator flows."
  type        = string
  default     = ""

  validation {
    condition     = var.expected_aws_account_id == "" || can(regex("^[0-9]{12}$", var.expected_aws_account_id))
    error_message = "expected_aws_account_id must be empty or a 12-digit AWS account ID."
  }
}

variable "expected_aws_principal_arn" {
  description = "Expected AWS caller ARN for production safety checks. Leave empty only for non-production emulator flows."
  type        = string
  default     = ""

  validation {
    condition     = var.expected_aws_principal_arn == "" || startswith(var.expected_aws_principal_arn, "arn:aws:iam::")
    error_message = "expected_aws_principal_arn must be empty or an IAM principal ARN."
  }
}

variable "use_localstack" {
  description = "Whether to route AWS provider calls to LocalStack for local infrastructure verification."
  type        = bool
  default     = false
}

variable "localstack_endpoint" {
  description = "LocalStack edge endpoint used when use_localstack is true."
  type        = string
  default     = "http://localhost:4566"
}

variable "availability_zone_count" {
  description = "How many AZs to spread the VPC across."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "availability_zone_count must be between 2 and 3."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the production VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "cluster_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.30"
}

variable "eks_cluster_enabled_log_types" {
  description = "EKS control-plane log types sent to CloudWatch Logs."
  type        = list(string)
  default = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint."
  type        = list(string)

  validation {
    condition = (
      length(var.cluster_endpoint_public_access_cidrs) > 0 &&
      alltrue([
        for cidr in var.cluster_endpoint_public_access_cidrs : cidr != "0.0.0.0/0"
      ])
    )
    error_message = "cluster_endpoint_public_access_cidrs must be set explicitly and must not include 0.0.0.0/0."
  }
}

variable "general_node_instance_types" {
  description = "CPU-focused instance types for API and Model Runtime workloads."
  type        = list(string)
  default     = ["c6a.large"]
}

variable "frontend_bucket_name" {
  description = "Override for the private frontend bucket name."
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Root DNS domain for production when Terraform manages Route53 and ACM for an externally registered domain."
  type        = string
  default     = ""
}

variable "create_route53_zone" {
  description = "Whether Terraform should create a public Route53 hosted zone for domain_name."
  type        = bool
  default     = false
}

variable "enable_managed_acm_certificates" {
  description = "Whether Terraform should request and validate ACM certificates for frontend and API domains."
  type        = bool
  default     = false
}

variable "frontend_aliases" {
  description = "Optional CloudFront aliases for app.<domain>."
  type        = list(string)
  default     = []
}

variable "frontend_acm_certificate_arn" {
  description = "Optional ACM certificate ARN for CloudFront aliases. Must be in us-east-1."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Hosted zone ID used for frontend and API DNS records."
  type        = string
  default     = ""
}

variable "api_domain_name" {
  description = "Optional Route53 record name for api.<domain>."
  type        = string
  default     = ""
}

variable "api_dns_name" {
  description = "Optional live ALB DNS name for the API ingress. Used for Route53 CNAME creation after first ingress deploy."
  type        = string
  default     = ""
}

variable "kubernetes_namespace" {
  description = "Namespace used for production workloads."
  type        = string
  default     = "pytorch-model-prod"
}

variable "api_service_account_name" {
  description = "Stable Kubernetes service account name for the API workload."
  type        = string
  default     = "pytorch-model-api"
}

variable "model_runtime_service_account_names" {
  description = "Stable Kubernetes service account names for the single Model Runtime Host workload."
  type        = map(string)
  default = {
    host = "pytorch-model-model-runtime-host"
  }
}

variable "enable_frontend_waf" {
  description = "Whether to attach a WAFv2 Web ACL to the CloudFront distribution."
  type        = bool
  default     = false
}

variable "enable_api_waf" {
  description = "Whether to create a regional WAFv2 Web ACL for the API ingress."
  type        = bool
  default     = false
}

variable "enable_cloudtrail" {
  description = "Whether to create an account-level multi-region CloudTrail for production API activity auditing."
  type        = bool
  default     = true
}

variable "frontend_waf_rate_limit" {
  description = "Requests per 5-minute window before CloudFront WAF rate limiting blocks an IP."
  type        = number
  default     = 2000
}

variable "api_waf_rate_limit" {
  description = "Requests per 5-minute window before API WAF rate limiting blocks an IP."
  type        = number
  default     = 1000
}

variable "db_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "pytorchmodel"
}

variable "db_username" {
  description = "Master username for the production PostgreSQL instance."
  type        = string
  default     = "appuser"
}

variable "db_password" {
  description = "Master password for the production PostgreSQL instance. Leave empty to let Terraform generate one."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition     = var.db_password == "" || (length(var.db_password) >= 16 && var.db_password != "replace-me-db-password")
    error_message = "db_password must be empty for Terraform generation or at least 16 characters and not use the example placeholder."
  }
}

variable "db_engine_version" {
  description = "PostgreSQL engine version for RDS."
  type        = string
  default     = "16.13"
}

variable "db_instance_class" {
  description = "Instance class for production PostgreSQL."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GiB for PostgreSQL."
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum autoscaled storage in GiB for PostgreSQL."
  type        = number
  default     = 100
}

variable "db_backup_retention_period" {
  description = "Backup retention period for PostgreSQL."
  type        = number
  default     = 7
}

variable "db_skip_final_snapshot" {
  description = "Whether Terraform destroy should skip the final RDS snapshot."
  type        = bool
  default     = false
}

variable "db_deletion_protection" {
  description = "Whether deletion protection should be enabled for PostgreSQL."
  type        = bool
  default     = true
}

variable "prediction_artifacts_bucket_name" {
  description = "Override for the private S3 bucket used for prediction artifacts."
  type        = string
  default     = ""
}

variable "log_retention_in_days" {
  description = "Retention for CloudWatch log groups managed by this stack."
  type        = number
  default     = 30
}

variable "api_alb_arn_suffix" {
  description = "Optional ALB ARN suffix used for API CloudWatch alarms once ingress exists."
  type        = string
  default     = ""
}

variable "api_target_group_arn_suffix" {
  description = "Optional target group ARN suffix used for API CloudWatch alarms once ingress exists."
  type        = string
  default     = ""
}

variable "enable_container_insights_node_condition_alarm" {
  description = "Whether to create an EKS node-condition alarm from Container Insights metrics. Requires Container Insights metrics to be enabled on the cluster."
  type        = bool
  default     = false
}

variable "alarm_email_addresses" {
  description = "Email addresses subscribed to CloudWatch alarm notifications."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Extra resource tags."
  type        = map(string)
  default     = {}
}
