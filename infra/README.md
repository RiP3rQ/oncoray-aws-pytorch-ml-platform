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
- `scripts/validate-local.ps1` for offline-safe local validation with no AWS calls
- `../docs/DEPLOYMENT_RUNBOOK.md` for end-to-end operator steps

Recommended flow later:

1. Run `bun run infra:bootstrap` to check local Terraform/Helm/AWS/Kubernetes tooling
2. Run `bun run infra:validate` for offline-safe checks first
3. Run `bun run infra:validate:helm` once Helm is installed and you want chart lint/render checks
4. Run `bun run infra:terraform:init` if Terraform reports missing modules
5. Run `bun run infra:test:terraform:workload-identities` after Terraform providers are initialized
6. Fill in `infra/terraform/environments/prod/terraform.tfvars`
7. Copy `infra/helm/values/addons.example.yaml` to a real add-ons values file
8. Copy `infra/helm/values/prod.example.yaml` to a real prod values file
9. Copy `infra/helm/values/ssm-parameters.prod.example.json` to a real Parameter Store manifest and fill secrets
10. Run `infra/scripts/release-prod.ps1` for the one-command production path
11. Use `infra/scripts/destroy-prod.ps1` when environment teardown is required

Tool bootstrap:

```powershell
bun run infra:bootstrap
bun run infra:bootstrap:install
```

`infra:bootstrap` only checks tools and prints install commands. `infra:bootstrap:install` uses `winget` to install Terraform, Helm, AWS CLI, and kubectl. If Terraform init fails because `.terraform` module cache files are locked, close tools using that directory and remove `infra/terraform/environments/prod/.terraform` manually before re-running `bun run infra:terraform:init`.

Current status:

- scaffold exists
- Terraform now covers managed data services, app IRSA roles, CloudWatch alarms, WAF, frontend DNS, and prediction artifact storage
- add-on automation now exists for AWS Load Balancer Controller, External Secrets, KEDA, ClusterSecretStore, and Fluent Bit
- one-command production orchestration now exists in `scripts/release-prod.ps1`
- no live AWS resources created
- no live cluster deploys executed
