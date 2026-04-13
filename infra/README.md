# Infra Setup

Local-only deployment setup. No AWS calls are made by these files until you run the commands yourself.

Contents:

- `terraform/` for AWS infrastructure scaffolding
- `helm/charts/backend-stack/` for Kubernetes workloads
- `helm/values/prod.example.yaml` for production overrides
- `scripts/deploy-prod.ps1` to wrap `helm upgrade --install`
- `scripts/destroy-prod.ps1` to wrap teardown
- `../docs/DEPLOYMENT_RUNBOOK.md` for end-to-end operator steps

Recommended flow later:

1. Fill in `infra/terraform/environments/prod/terraform.tfvars`
2. Apply Terraform when AWS account details are ready
3. Copy `infra/helm/values/prod.example.yaml` to a real prod values file
4. Build and push backend images
5. Run `infra/scripts/deploy-prod.ps1` with real image repos and tags
6. Use `infra/scripts/destroy-prod.ps1` when environment teardown is required

Current status:

- scaffold exists
- no live AWS resources created
- no live cluster deploys executed
