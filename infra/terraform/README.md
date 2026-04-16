# Terraform Infra

Initial production scaffold for `pytorch-model`.

Current scope:

- VPC with public and private subnets
- EKS cluster with separate general and model-service node groups
- ECR repositories for `api` and `model-service`
- private S3 bucket + CloudFront distribution for frontend delivery
- private S3 bucket for prediction artifacts
- CloudFront WAF and regional API WAF policy
- Route53 frontend aliases and optional API CNAME
- SQS queue + DLQ for worker jobs
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis replication group
- CloudWatch log group for workload shipping
- CloudWatch alarms for queue depth, database pressure, cache pressure, and optional API ALB health
- IRSA roles for AWS Load Balancer Controller, External Secrets, Fluent Bit, API, and worker
- expected Parameter Store path outputs for later secret population

Still pending after this scaffold:

- remote backend creation and live state bucket/table
- production secret values and External Secrets Operator wiring
- CI/CD execution against real AWS account

Usage:

```powershell
cd infra/terraform/environments/prod
terraform init
terraform plan -var-file=terraform.tfvars
```

Start from `terraform.tfvars.example` and copy to `terraform.tfvars`.
For remote state, also start from `backend.hcl.example`.
