# Production Deployment Runbook

This runbook is canonical operator path for AWS production deploy.

Rule: Terraform owns AWS resources. Helm owns Kubernetes workloads. Frontend deploy is S3 sync plus CloudFront invalidation. Helper scripts stay thin.

## Current Truth

Repo has production scaffold and a completed first live AWS 24-hour prototype deployment, followed by teardown.

Current readiness snapshot as of 2026-05-03:

- LocalStack apply, endpoint checks, Helm install, Helm uninstall, and clean Terraform destroy have passed.
- Namecheap root domain is selected: `oncoray.online`.
- live AWS account is selected: `123456789012`.
- live AWS CLI profile is selected and validated: `pytorch-model-prod`.
- live AWS principal is validated: `arn:aws:iam::123456789012:user/pytorch-model-cli-user`.
- gitignored `infra/terraform/environments/prod/terraform.tfvars` exists locally for DNS bootstrap, including the
  account/principal guards, domain settings, and a private operator `/32` EKS API allowlist entry. Do not move this file
  into tracked source.
- DNS-bootstrap preflight has passed with `-RequireAwsIdentity`.
- targeted Terraform plan/apply for `aws_route53_zone.primary[0]` created the Route53 hosted zone for `oncoray.online`.
- Namecheap nameservers were updated to Route53 output and DNS delegation propagated enough for ACM validation.
- full Terraform apply created VPC, EKS, ECR, S3/CloudFront, RDS PostgreSQL, CloudTrail, CloudWatch, IAM, and Route53
  frontend records. RDS engine default was corrected from unavailable `16.4` to supported `16.13` in `eu-central-1`.
- prototype SSM values were validated against Terraform `expected_parameter_store_paths`; all 14 expected parameters were
  uploaded and verified in AWS SSM Parameter Store.
- EKS kubeconfig is configured locally and one managed node is `Ready`.
- completed step: install platform add-ons using gitignored `infra/helm/values/addons.yaml`. First install attempt exposed a
  PowerShell/Helm escaping bug for IRSA annotation keys; the helper now passes single escaped dots in `eks.amazonaws.com`.
  Second install attempt deployed AWS Load Balancer Controller, then hit its webhook readiness race before External
  Secrets install; the helper now waits for the controller rollout. Third attempt deployed External Secrets, then hit a
  CRD establishment race before platform chart; the helper now waits for required External Secrets CRDs and controller
  rollout. Helm then rejected `external-secrets.io/v1beta1`; platform and backend charts now use
  `external-secrets.io/v1`, which is served by the installed CRDs. Final retry deployed AWS Load Balancer Controller,
  External Secrets, and platform add-ons; ClusterSecretStore is Ready and Fluent Bit rolled out. Local dead proxy
  variables must be cleared for kube API calls.
- gitignored `infra/helm/values/prod.yaml` has been created with real domains, IRSA role ARNs, ACM certificate ARN, ECR
  repositories, image tag `sha-97f9f0cfa5f7`, and Model Runtime Host enabled.
- API and Model Service images have been built locally and pushed to ECR with tag `sha-97f9f0cfa5f7`.
- full production preflight has passed for Terraform, backend Helm, platform Helm, and AWS identity.
- first backend Helm install exposed a migration hook ordering bug: the pre-install Job ran before the ServiceAccount and
  ExternalSecret resources existed, so Kubernetes rejected the hook pod. The chart now runs migrations as a
  `post-install,post-upgrade` hook, and `deploy-prod.ps1` forces `migrations.enabled=true` while waiting for hook Jobs
  and workload readiness.
- first migration retry failed because Alembic wrote a URL-encoded RDS password containing `%` into ConfigParser without
  escaping; `apps/api/src/migrations/env.py` now escapes `%` before `set_main_option`.
- backend became healthy after the first-deploy fixes. API pod was `1/1 Running`, Model Runtime Host pod was
  `1/1 Running`, and logs confirmed both approved Hugging Face `/resolve/main/` artifact URLs fetched and loaded
  in-cluster. For this one-node prototype, API autoscaling is disabled and Model Runtime Host requests are lowered while
  limits remain higher.
- Terraform created `api.oncoray.online` CNAME to the ingress ALB. Public API smoke passed with local proxy env cleared:
  `/livez` returned `200` and `/readyz` returned `200` with database check true.
- API ALB CloudWatch alarms were created after capturing ALB and target group suffixes.
- frontend built with `PUBLIC_API_BASE_URL=https://api.oncoray.online`, synced to
  `s3://pytorch-model-prod-frontend-123456789012`, and CloudFront invalidation `IEXAMPLEINVALIDATION1` started.
  Public frontend smoke passed: `https://app.oncoray.online/` returned `200`.
- frontend route smoke found CloudFront served dashboard HTML for `/login` and `/register`, causing the browser auth
  guard to reload continuously. Terraform now adds a CloudFront Function that rewrites Astro static routes to S3
  `*/index.html` objects. Live frontend aliases now include both `app.oncoray.online` and `oncoray.online`, with
  Route53 A/AAAA aliases to CloudFront.
- browser smoke verified `https://app.oncoray.online/` navigates once to `/login`, renders `Log In | OncoRay`, shows the
  login button, and emits no console errors. Direct HTTPS smoke verified `https://app.oncoray.online/login`, `/register`,
  and apex `https://oncoray.online/login` through CloudFront.
- CORS preflight works from both `https://app.oncoray.online` and `https://oncoray.online`. Backend Helm prod values
  include both origins in `CORS_ALLOWED_ORIGINS`, API rollout completed, and `/readyz` still returns database healthy.
- first AWS prototype deployment served API and frontend, then teardown was verified. Terraform state was empty and the
  remaining KMS key entered the expected AWS `PendingDeletion` state.
- second deployment should start from DNS bootstrap with fresh Route53 nameservers, fresh SSM upload, fresh image tags,
  and backend Helm deploy through `deploy-prod.ps1`. No manual migration Job or ad hoc CLI patch is part of normal path.

Exists:

- Terraform root: `infra/terraform/environments/prod`
- backend Helm chart: `infra/helm/charts/backend-stack`
- platform add-ons chart: `infra/helm/charts/platform-addons`
- backend values template: `infra/helm/values/prod.example.yaml`
- add-on values template: `infra/helm/values/addons.example.yaml`
- thin backend deploy helper: `infra/scripts/deploy-prod.ps1`
- add-on helper: `infra/scripts/install-cluster-addons.ps1`
- destroy helper: `infra/scripts/destroy-prod.ps1`
- offline validator: `infra/scripts/validate-local.ps1`

Not supported:

- one-command full release orchestration
- generated deployment contracts
- generated Helm override files as release artifacts

Those can return later after first live deploy proves repeated pain.

## Production Shape

- Frontend: Astro static build to private S3, served by CloudFront.
- API: FastAPI Deployment on EKS, public through ALB ingress.
- Model Runtime: `apps/model-service` Deployments on EKS, internal ClusterIP only.
- Data/services: RDS PostgreSQL, ECR, SSM Parameter Store, CloudWatch, SNS email alarm topic.

`apps/pytorch-engine` is training/experimentation only. It is not production runtime.

## Prerequisites

Operator machine:

- Terraform `>= 1.6`
- AWS CLI v2
- kubectl
- Helm 3
- Docker
- Bun

AWS account permissions:

- VPC, EKS, IAM, ECR, S3, CloudFront, Route53, ACM, WAF, SSM, RDS, CloudWatch, SNS.

Production AWS identity:

- account ID: `123456789012`
- IAM user ARN: `arn:aws:iam::123456789012:user/pytorch-model-cli-user`
- recommended AWS CLI profile: `pytorch-model-prod`
- Terraform/account guard value: `expected_aws_account_id = "123456789012"`
- Terraform/principal guard value:
  `expected_aws_principal_arn = "arn:aws:iam::123456789012:user/pytorch-model-cli-user"`

Configure local AWS CLI for live operations:

```powershell
aws configure --profile pytorch-model-prod
$env:AWS_PROFILE = "pytorch-model-prod"
$env:AWS_REGION = "eu-central-1"
$env:AWS_DEFAULT_REGION = "eu-central-1"
aws sts get-caller-identity --region eu-central-1
```

The STS identity must return account `123456789012` and ARN
`arn:aws:iam::123456789012:user/pytorch-model-cli-user`. Production preflight with `-RequireAwsIdentity` rejects any
other account or principal before Terraform plan/apply.

Domains/certs:

- frontend domain, usually `app.<domain>`
- API domain, usually `api.<domain>`
- Route53 public hosted zone. The domain may be registered outside AWS, for example in Namecheap.
- CloudFront ACM cert in `us-east-1`, either supplied by ARN or managed by Terraform.
- API ALB ACM cert in app region, either supplied by ARN or managed by Terraform.

## 1. Validate Local Repo

```powershell
bun run infra:bootstrap
bun run infra:validate
```

Optional Helm render checks:

```powershell
bun run infra:validate:helm
```

Before DNS bootstrap, run production preflight for Terraform-only inputs:

```powershell
bun run prod:preflight -- -Phase DnsBootstrap -RequireAwsIdentity
```

This checks required tooling, `terraform.tfvars`, unresolved placeholders, Terraform formatting, and Terraform
validation. It does not apply infrastructure.

Current status: this DNS-bootstrap preflight has passed for `pytorch-model-prod`.

Before full backend deployment, run production preflight after creating all real gitignored values files:

```powershell
bun run prod:preflight -- -Phase FullDeploy -RequireAwsIdentity
```

This additionally checks `addons.yaml`, `prod.yaml`, and Helm rendering. It does not deploy workloads.

## LocalStack Verification

Use LocalStack to verify AWS Terraform wiring without touching real AWS.

LocalStack mode is opt-in:

```powershell
terraform -chdir=infra/terraform/environments/prod init -backend=false
terraform -chdir=infra/terraform/environments/prod plan -var-file=localstack.tfvars.example
terraform -chdir=infra/terraform/environments/prod apply -var-file=localstack.tfvars.example -auto-approve
```

The LocalStack profile uses `use_localstack = true`, redirects AWS provider endpoints to `http://localhost:4566`, disables EKS node groups and IRSA/OIDC, and keeps real production defaults unchanged.

Create a kubeconfig for LocalStack EKS:

```powershell
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "eu-central-1"
aws --endpoint-url=http://localhost:4566 eks update-kubeconfig --name pytorch-model-local-eks --region eu-central-1 --kubeconfig tmp/localstack-kubeconfig
```

Use `NO_PROXY` for LocalStack Kubernetes calls:

```powershell
$env:KUBECONFIG = "$PWD/tmp/localstack-kubeconfig"
$env:NO_PROXY = "localhost,127.0.0.1,localhost.localstack.cloud,.localhost.localstack.cloud"
$env:HTTPS_PROXY = ""
$env:HTTP_PROXY = ""
kubectl get nodes
```

Verify backend chart install shape without requiring pushed images:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/deploy-prod.ps1 `
  -ValuesFile infra/helm/values/localstack.example.yaml `
  -ApiImageRepository 000000000000.dkr.ecr.eu-central-1.localhost.localstack.cloud:4566/pytorch-model/api `
  -ApiImageTag sha-localstack
```

`localstack.example.yaml` sets replicas to `0` and disables ingress, External Secrets, and Model Runtimes. This verifies Kubernetes manifest acceptance; image build/push and live pods can be tested later.

## 2. Prepare Terraform Vars

Create:

```text
infra/terraform/environments/prod/terraform.tfvars
```

Start from:

```text
infra/terraform/environments/prod/terraform.tfvars.example
```

Set at minimum:

- `project_name`
- `environment`
- `aws_region`
- `expected_aws_account_id`
- `expected_aws_principal_arn`
- `cluster_endpoint_public_access_cidrs`
- `frontend_bucket_name`
- `tags`

`db_password` may be left empty for short-lived test production. Terraform will generate a random password and expose
the resulting database URL as the sensitive `postgres_database_url` output. For long-lived production, store the chosen
password outside git and keep the value stable.

For a domain bought outside AWS, use Terraform-managed Route53:

```hcl
domain_name         = "example.com"
create_route53_zone = true
frontend_aliases    = []
api_domain_name     = ""
```

For this deployment, use:

```hcl
domain_name         = "oncoray.online"
create_route53_zone = true
frontend_aliases    = []
api_domain_name     = ""
```

Defaults become:

- frontend: `app.<domain_name>`
- API: `api.<domain_name>`

Leave `enable_managed_acm_certificates = false` for the first DNS bootstrap apply. This creates the Route53 hosted zone
and outputs `route53_name_servers`.

Do not reuse a LocalStack `terraform.tfstate` for real AWS. Production preflight rejects state containing
`localhost.localstack.cloud`, account `000000000000`, or `pytorch-model-local`.

Use clean remote state before long-lived production:

```powershell
terraform -chdir=infra/terraform/environments/prod init -backend-config=backend.hcl
```

Local planning without backend:

```powershell
bun run infra:terraform:init
```

## 3. Apply AWS Infra

Stop point before live resource creation:

- reviewed targeted plan shows only `aws_route53_zone.primary[0]`
- expected plan result is `1 to add, 0 to change, 0 to destroy`
- do not run apply until this one-resource DNS bootstrap is approved

### 3.1 Bootstrap DNS for External Registrar

If the domain is registered outside AWS, run the first apply with `create_route53_zone = true` and
`enable_managed_acm_certificates = false`.

```powershell
$env:AWS_PROFILE = "pytorch-model-prod"
$env:AWS_REGION = "eu-central-1"
$env:AWS_DEFAULT_REGION = "eu-central-1"
terraform -chdir=infra/terraform/environments/prod plan -var-file=terraform.tfvars -target="aws_route53_zone.primary[0]"
terraform -chdir=infra/terraform/environments/prod apply -var-file=terraform.tfvars -target="aws_route53_zone.primary[0]"
terraform -chdir=infra/terraform/environments/prod output route53_name_servers
```

Current status after teardown: previous hosted zone was destroyed. For second deployment, run this targeted plan and
apply again, then paste fresh `route53_name_servers` into Namecheap.

The first DNS bootstrap apply is intentionally targeted. It creates the public hosted zone only. CloudFront aliases and
ACM certificate validation are enabled in the second apply after the registrar delegates nameservers to Route53.

In Namecheap:

1. open the domain
2. set nameservers to Custom DNS
3. paste all `route53_name_servers`
4. wait for delegation to propagate

After full teardown, previous hosted-zone nameservers are invalid because the Route53 hosted zone was destroyed. Use the
new `route53_name_servers` from the fresh bootstrap apply every time.

After nameserver delegation works, set:

```hcl
enable_managed_acm_certificates = true
```

Then apply again. Terraform requests and validates:

- CloudFront certificate in `us-east-1`
- API certificate in `eu-central-1`

### 3.1.1 Remaining Work Before Actual Production Deployment

Do these after the one-resource DNS bootstrap and before exposing the application as production:

1. Paste `route53_name_servers` into Namecheap and wait for delegation.
2. Enable managed ACM certificates in gitignored `terraform.tfvars`, then plan/apply certificate DNS validation.
3. Decide remote state backend for the live environment before long-lived production. Use local state only for a
   short-lived test deploy if explicitly accepted.
4. Run full Terraform plan and apply for VPC, EKS, ECR, S3/CloudFront, RDS, WAF, CloudWatch, IAM, SSM paths, and
   account security services.
5. Populate required SSM Parameter Store values from `expected_parameter_store_paths`, including SMTP, JWT, API
   config, prediction artifact config, Model Artifact URLs, `HF_USERNAME`, and non-empty `HF_TOKEN`.
6. Create gitignored `infra/helm/values/addons.yaml` and install platform add-ons.
7. Build and push API and Model Runtime images to ECR.
8. Create gitignored `infra/helm/values/prod.yaml`, then run full production preflight.
9. Deploy backend Helm release and verify migrations, probes, IRSA annotations, logs, and internal Model Runtime calls.
10. Capture first ALB hostname, set `api_dns_name` in gitignored `terraform.tfvars`, and apply Route53 API DNS record.
11. Capture ALB and target-group ARN suffixes, set alarm variables, and apply API alarm wiring.
12. Deploy frontend build to S3, invalidate CloudFront, and verify `app.oncoray.online` and `api.oncoray.online`.
13. Run post-deploy smoke tests and confirm SNS alarm email subscriptions.

### 3.2 Apply Infrastructure

```powershell
terraform -chdir=infra/terraform/environments/prod fmt -check
terraform -chdir=infra/terraform/environments/prod plan -var-file=terraform.tfvars
terraform -chdir=infra/terraform/environments/prod apply -var-file=terraform.tfvars
```

Capture useful outputs:

```powershell
terraform -chdir=infra/terraform/environments/prod output
```

Need for later:

- `cluster_name`
- `aws_region`
- `vpc_id`
- `ecr_repository_urls`
- `cluster_addon_role_arns`
- `app_workload_role_arns`
- `frontend_bucket_name`
- `frontend_distribution_id`
- `frontend_acm_certificate_arn`
- `api_domain_name`
- `api_acm_certificate_arn`
- `route53_name_servers`
- `postgres`
- `cloudtrail_bucket_name`
- `expected_parameter_store_paths`

Security baseline created by Terraform when enabled:

- CloudTrail multi-region management-event trail with log-file validation
- EKS control-plane logs
- optional WAF log groups when WAF toggles are enabled

## 4. Configure kubeconfig

```powershell
aws eks update-kubeconfig --region <aws_region> --name <cluster_name>
kubectl get nodes
```

## 5. Install Cluster Add-ons

Create:

```text
infra/helm/values/addons.yaml
```

Start from:

```text
infra/helm/values/addons.example.yaml
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/install-cluster-addons.ps1 `
  -ClusterName <cluster_name> `
  -VpcId <vpc_id> `
  -LoadBalancerControllerRoleArn <alb_role_arn> `
  -ExternalSecretsRoleArn <external_secrets_role_arn> `
  -FluentBitRoleArn <fluent_bit_role_arn> `
  -PlatformValuesFile infra/helm/values/addons.yaml
```

Verify:

```powershell
kubectl get pods -A
```

## 6. Populate SSM Parameters

Use `expected_parameter_store_paths` from Terraform output.

Create gitignored production parameter file:

```text
infra/helm/values/ssm-parameters.prod.json
```

Start from:

```text
infra/helm/values/ssm-parameters.prod.example.json
```

Replace every placeholder before upload. The uploader rejects empty values, example placeholders, and account
placeholders. Mutable Hugging Face `/resolve/main/` artifact URLs are allowed only for the approved short-lived prototype
when `ALLOW_MUTABLE_MODEL_ARTIFACTS=true` is also set in Model Runtime Helm values. Current production config requires a
non-empty `HF_TOKEN` in SSM, even for public model URLs, because production Model Artifact access must be explicitly
reviewed.

Examples:

```powershell
aws ssm put-parameter --name /pytorch-model/prod/api/SECRET_KEY --type SecureString --value "<value>" --overwrite
aws ssm put-parameter --name /pytorch-model/prod/api/CORE_API_DATABASE_URL --type SecureString --value "<value>" --overwrite
```

Preferred upload path:

```powershell
$env:PYTORCH_MODEL_EXPECTED_AWS_ACCOUNT_ID = "123456789012"
$env:PYTORCH_MODEL_EXPECTED_AWS_PRINCIPAL_ARN = "arn:aws:iam::123456789012:user/pytorch-model-cli-user"
bun run prod:ssm:put -- -DryRun
bun run prod:ssm:put
```

Set the Model Runtime Host Hugging Face artifact values before enabling model serving. One `model-runtime-host`
process serves both visual models and routes requests by `model`. Long-lived production should use immutable Hugging Face
revisions, not `/resolve/main/`; the 24-hour prototype may use the verified `/resolve/main/` URLs with the explicit
mutable-artifact override and non-empty `HF_TOKEN`.

Set frontend Sentry env values before build when browser error reporting is enabled:

- `PUBLIC_SENTRY_DSN`
- `PUBLIC_APP_ENVIRONMENT`
- `PUBLIC_APP_RELEASE`
- optional `PUBLIC_SENTRY_TRACES_SAMPLE_RATE`

Set Sentry source-map upload credentials in the frontend build environment when source maps should be uploaded:

- `SENTRY_AUTH_TOKEN`
- `SENTRY_ORG`
- `SENTRY_PROJECT`

## 7. Build and Push Images

Login:

```powershell
aws ecr get-login-password --region <aws_region> | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<aws_region>.amazonaws.com
```

API image:

```powershell
docker build -t <api_repo>:<tag> apps/api
docker push <api_repo>:<tag>
```

Model Runtime image:

```powershell
docker build -t <model_service_repo>:<tag> apps/model-service
docker push <model_service_repo>:<tag>
```

Use immutable tags, usually git SHA. Do not deploy `latest`.

## 8. Deploy Backend with Helm

Create:

```text
infra/helm/values/prod.yaml
```

Start from:

```text
infra/helm/values/prod.example.yaml
```

Set:

- image repositories and tags
- API host and ALB certificate annotation from `api_acm_certificate_arn`
- CORS origin
- service account role annotations from `app_workload_role_arns` (`api` and `model_runtime_host`)
- ExternalSecret flags and Parameter Store keys
- Model Runtime Host enabled flag and artifact config
- Model Artifact URLs and Hugging Face credentials
- OpenTelemetry OTLP endpoint if exporting traces to a collector

Dry run:

```powershell
bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag <tag> `
  -DryRun
```

Deploy:

```powershell
bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag <tag>
```

With the single Model Runtime Host:

```powershell
bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag <tag> `
  -EnableModelService `
  -ModelServiceImageRepository <model_service_repo> `
  -ModelServiceImageTag <tag>
```

The backend Helm release runs the Alembic migration Job as a `post-install,post-upgrade` hook after the normal chart
resources are created. `deploy-prod.ps1` forces `migrations.enabled=true` and passes `--wait --wait-for-jobs`, so
migration failure fails the deployment and the operator should not continue to API DNS/frontend steps.

Verify:

```powershell
kubectl get all -n pytorch-model-prod
kubectl get ingress -n pytorch-model-prod
kubectl get externalsecrets -n pytorch-model-prod
```

## 9. Wire API DNS and ALB Alarms

After ALB ingress exists, get hostname:

```powershell
$apiAlbDnsName = (kubectl get ingress -n pytorch-model-prod `
  -o jsonpath="{.items[0].status.loadBalancer.ingress[0].hostname}")
$apiAlbDnsName
```

Set `api_dns_name` in `terraform.tfvars`, then apply again:

```powershell
terraform -chdir=infra/terraform/environments/prod plan -var-file=terraform.tfvars
terraform -chdir=infra/terraform/environments/prod apply -var-file=terraform.tfvars
```

This creates/updates Route53 API record when `api_domain_name` and `route53_zone_id` are set.

Enable API ALB CloudWatch alarms in the same feedback pass. Terraform cannot know the ALB and target group suffixes
until AWS Load Balancer Controller creates the ingress.

```powershell
$apiAlbArn = aws elbv2 describe-load-balancers `
  --query "LoadBalancers[?DNSName=='$apiAlbDnsName'].LoadBalancerArn | [0]" `
  --output text

$apiTargetGroupArn = aws elbv2 describe-target-groups `
  --load-balancer-arn $apiAlbArn `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text

$apiAlbArnSuffix = $apiAlbArn -replace '^.*/loadbalancer/', ''
$apiTargetGroupArnSuffix = $apiTargetGroupArn -replace '^.*/targetgroup/', 'targetgroup/'

$apiAlbArnSuffix
$apiTargetGroupArnSuffix
```

Set `api_alb_arn_suffix` and `api_target_group_arn_suffix` in `terraform.tfvars`, then run the Terraform plan/apply
again. This activates:

- API ALB target 5xx alarm
- API unhealthy target alarm

## 10. Deploy Frontend

Build:

```powershell
$env:PUBLIC_API_BASE_URL = "https://api.example.com"
Set-Location apps/astro-web
bun run build
Set-Location ../..
```

Upload and invalidate:

```powershell
aws s3 sync apps/astro-web/dist s3://<frontend_bucket_name> --delete
aws cloudfront create-invalidation --distribution-id <frontend_distribution_id> --paths "/*"
```

## 11. Smoke Test

```powershell
kubectl get pods -n pytorch-model-prod
Invoke-WebRequest https://api.example.com/livez
Invoke-WebRequest https://api.example.com/readyz
kubectl exec -n pytorch-model-prod deploy/pytorch-model-backend-stack-api -- python scripts/verify_s3_upload.py
```

Manual checks:

- frontend loads through CloudFront
- API ingress target group healthy
- S3 upload verification writes and reads one `predictions/verification/` object through the API pod IAM role
- ExternalSecrets synced
- prediction flow reaches enabled Model Runtimes
- Sentry browser errors arrive when `PUBLIC_SENTRY_DSN` is set

## Destroy

Rollback backend release without deleting infrastructure:

```powershell
bun run prod:rollback
```

Rollback to a specific Helm revision:

```powershell
bun run prod:rollback -- -Revision <revision>
```

Delete production test environment completely:

```powershell
bun run prod:destroy -- -PurgeS3Buckets -ConfirmDestructiveBucketPurge -PurgeSsmParameters -AutoApprove
```

Destroy sequence:

1. uninstall backend Helm release
2. uninstall add-on Helm releases
3. optionally purge Terraform-managed S3 bucket contents and object versions
4. optionally delete script-managed SSM parameters
5. run `terraform destroy`

If a previous destroy was interrupted after Terraform outputs disappeared but a known versioned bucket remains, pass it
explicitly:

```powershell
bun run prod:destroy -- -PurgeS3Buckets -AdditionalS3Buckets <bucket-name> -ConfirmDestructiveBucketPurge -PurgeSsmParameters -AutoApprove
```

AWS KMS keys cannot be deleted immediately. The EKS cluster encryption key is configured with the minimum
`kms_key_deletion_window_in_days = 7`; after destroy, Resource Explorer can still show that disabled key as
`PendingDeletion` until AWS deletes it.

For short-lived test production environments, set `db_deletion_protection = false` in `terraform.tfvars` before apply.
For disposable 24-hour prototypes where no database recovery artifact should remain, also set
`db_skip_final_snapshot = true` before apply. If `db_skip_final_snapshot = false`, Terraform can delete RDS but AWS keeps
the final snapshot, which is useful for recovery but is not a complete zero-artifact teardown.
For long-lived production, keep deletion protection enabled and expect Terraform destroy to fail until an operator
intentionally disables it.

Direct Terraform fallback:

```powershell
terraform -chdir=infra/terraform/environments/prod destroy -var-file=terraform.tfvars
```

## Common Failure Points

- wrong ACM cert region
- `cluster_endpoint_public_access_cidrs` excludes operator IP
- add-ons missing before API ingress deploy
- missing SSM parameters
- missing service account IRSA annotations
- image tag not pushed to ECR
- frontend built with wrong `PUBLIC_API_BASE_URL`
- API DNS not reapplied after first ALB hostname exists
