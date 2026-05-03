# Infra Setup

AWS production scaffold for `pytorch-model`.

Goal: keep deploy understandable. Terraform creates AWS resources. Helm deploys Kubernetes workloads. Small scripts are convenience wrappers only.

## Contents

- `terraform/` AWS infrastructure
- `helm/charts/backend-stack/` API and Model Runtime workloads
- `helm/charts/platform-addons/` ClusterSecretStore config and Fluent Bit
- `helm/values/prod.example.yaml` production workload values template
- `helm/values/addons.example.yaml` add-on values template
- `helm/values/localstack.example.yaml` LocalStack/Kubernetes chart verification values
- `scripts/deploy-prod.ps1` thin `helm upgrade --install` wrapper for backend workloads
- `scripts/install-cluster-addons.ps1` add-on install helper
- `scripts/destroy-prod.ps1` teardown helper
- `scripts/validate-local.ps1` offline-safe local validation
- `../docs/DEPLOYMENT_RUNBOOK.md` operator runbook

## Supported Flow

1. Run `bun run infra:bootstrap` to check local tools.
2. Run `bun run infra:validate`.
3. Fill `infra/terraform/environments/prod/terraform.tfvars`.
4. Run Terraform `init`, `plan`, and `apply`.
5. Run `aws eks update-kubeconfig`.
6. Fill `infra/helm/values/addons.yaml` and `infra/helm/values/prod.yaml`.
7. Install cluster add-ons.
8. Populate SSM Parameter Store values.
9. Build and push ECR images.
10. Deploy backend with `bun run prod:deploy:backend -- ...`.
11. Build frontend, sync to S3, invalidate CloudFront.

No one-command full production release script is supported until first live AWS deployment proves the flow.

LocalStack verification is supported with `infra/terraform/environments/prod/localstack.tfvars.example` and `infra/helm/values/localstack.example.yaml`.

## Tool Bootstrap

```powershell
bun run infra:bootstrap
bun run infra:bootstrap:install
```

`infra:bootstrap` checks tools and prints install commands. `infra:bootstrap:install` uses `winget` to install Terraform, Helm, AWS CLI, and kubectl.

## Current Status

- Terraform scaffold exists for budget-first VPC, EKS, ECR, S3/CloudFront, RDS, Route53, CloudWatch, SNS email alarms, CloudTrail, and IAM/IRSA. WAF is optional and disabled by default.
- Helm charts exist for backend workloads and platform add-on config.
- Thin local helpers exist for validation, add-ons, backend deploy, and destroy.
- No live AWS resources have been created from this repo in this workspace.
