# Infra Setup

Local-only deployment setup. No AWS calls are made by these files until you run the commands yourself.

Contents:

- `terraform/` for AWS infrastructure scaffolding
- `helm/charts/backend-stack/` for Kubernetes workloads
- `helm/charts/platform-addons/` for ClusterSecretStore config and Fluent Bit
- `helm/values/prod.example.yaml` for production overrides
- `helm/values/addons.example.yaml` for cluster add-on overrides
- `scripts/deploy-prod.ps1` to wrap `helm upgrade --install`
- `scripts/install-cluster-addons.ps1` to install controller/operator add-ons
- `scripts/destroy-prod.ps1` to wrap teardown
- `../docs/DEPLOYMENT_RUNBOOK.md` for end-to-end operator steps

Recommended flow later:

1. Fill in `infra/terraform/environments/prod/terraform.tfvars`
2. Apply Terraform when AWS account details are ready
3. Copy `infra/helm/values/addons.example.yaml` to a real add-ons values file
4. Install cluster add-ons with `infra/scripts/install-cluster-addons.ps1`
5. Copy `infra/helm/values/prod.example.yaml` to a real prod values file
6. Build and push backend images
7. Run `infra/scripts/deploy-prod.ps1` with real image repos and tags
8. Use `infra/scripts/destroy-prod.ps1` when environment teardown is required

Current status:

- scaffold exists
- Terraform now covers managed data services, WAF, and frontend DNS
- add-on automation now exists for AWS Load Balancer Controller, External Secrets, ClusterSecretStore, and Fluent Bit
- no live AWS resources created
- no live cluster deploys executed
