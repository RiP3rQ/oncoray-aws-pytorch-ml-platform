# Infra Setup

Local-only deployment setup. No AWS calls are made by these files until you run the commands yourself.

Contents:

- `terraform/` for AWS infrastructure scaffolding
- `helm/charts/backend-stack/` for Kubernetes workloads
- `helm/charts/platform-addons/` for ClusterSecretStore config and Fluent Bit
- `helm/values/prod.example.yaml` for production overrides
- `helm/values/addons.example.yaml` for cluster add-on overrides
- `helm/values/ssm-parameters.prod.example.json` for Parameter Store manifest structure
- `scripts/deploy-prod.ps1` to wrap `helm upgrade --install`
- `scripts/install-cluster-addons.ps1` to install controller/operator add-ons
- `scripts/release-prod.ps1` to orchestrate production release end-to-end
- `scripts/destroy-prod.ps1` to wrap teardown
- `../docs/DEPLOYMENT_RUNBOOK.md` for end-to-end operator steps

Recommended flow later:

1. Fill in `infra/terraform/environments/prod/terraform.tfvars`
2. Copy `infra/helm/values/addons.example.yaml` to a real add-ons values file
3. Copy `infra/helm/values/prod.example.yaml` to a real prod values file
4. Copy `infra/helm/values/ssm-parameters.prod.example.json` to a real Parameter Store manifest and fill secrets
5. Run `infra/scripts/release-prod.ps1` for the one-command production path
6. Use `infra/scripts/destroy-prod.ps1` when environment teardown is required

Current status:

- scaffold exists
- Terraform now covers managed data services, app IRSA roles, CloudWatch alarms, WAF, frontend DNS, and prediction artifact storage
- add-on automation now exists for AWS Load Balancer Controller, External Secrets, KEDA, ClusterSecretStore, and Fluent Bit
- one-command production orchestration now exists in `scripts/release-prod.ps1`
- no live AWS resources created
- no live cluster deploys executed
