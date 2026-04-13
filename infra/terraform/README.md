# Terraform Infra

Initial production scaffold for `pytorch-model`.

Current scope:

- VPC with public and private subnets
- EKS cluster with separate general and model-service node groups
- ECR repositories for `api` and `model-service`
- private S3 bucket + CloudFront distribution for frontend delivery
- SQS queue + DLQ for worker jobs
- expected Parameter Store path outputs for later secret population

Still pending after this scaffold:

- RDS PostgreSQL
- ElastiCache Redis
- Route53 records
- WAF
- production secret values and External Secrets Operator wiring
- CI/CD execution against real AWS account

Usage:

```powershell
cd infra/terraform/environments/prod
terraform init
terraform plan -var-file=terraform.tfvars
```

Start from `terraform.tfvars.example` and copy to `terraform.tfvars`.
