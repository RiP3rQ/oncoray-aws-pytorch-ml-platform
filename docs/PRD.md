# Product Requirements Document (PRD)

## Pytorch Model Monorepo - Production Deployment

| Field                    | Value                                                 |
| ------------------------ | ----------------------------------------------------- |
| Version                  | 3.3.0                                                 |
| Last updated             | 2026-05-03                                            |
| Status                   | Draft - 24-hour AWS prototype with mandatory teardown |
| Primary region           | eu-central-1                                          |
| Domain registrar         | Namecheap                                             |
| Root domain              | oncoray.online                                        |
| AWS account ID           | 123456789012                                          |
| AWS deployment principal | arn:aws:iam::123456789012:user/pytorch-model-cli-user |
| Primary goal             | Production deployment architecture for showcase repo  |

---

## 1. Executive summary

This repository is an education and showcase monorepo. The current canonical production deployment target is an AWS
showcase architecture for a private demo with about two peak concurrent users. It demonstrates coherent AWS,
Kubernetes, Docker, Terraform, and deployment practices without deploying security or redundancy services that are not
justified by the current traffic profile.

Budget finding from the 2026-05-03 infra review: the implemented EKS architecture is not a hard $20/7-day architecture,
but the seven-day number is informational only. The intended live AWS exercise is a roughly 24-hour prototype run, then
teardown. On that basis, the current infra can stay acceptable if operators keep WAF disabled, avoid unnecessary traffic,
and run the teardown path immediately after testing.

Canonical production path:

- Frontend deployed as static Astro site to private S3 behind CloudFront
- API deployed to EKS as containerized FastAPI service
- Model inference deployed to EKS as one Model Runtime Host backed by `apps/model-service`
- PostgreSQL on Amazon RDS for PostgreSQL, single-AZ with backups
- Infrastructure provisioned with Terraform
- Kubernetes application releases managed with Helm
- CI/CD handled by GitHub Actions
- Logs shipped from EKS to CloudWatch using Fluent Bit

Cheap alternatives remain fallback material only. The main P0 requirement is now teardown reliability: every live AWS
prototype must be created from Terraform/Helm-managed resources and removed with the documented destroy workflow.

---

## 2. Product context

### 2.1 Repository intent

This repo exists to showcase:

- Monorepo organization
- AWS infrastructure design
- Kubernetes deployment patterns
- Infrastructure as Code with Terraform
- CI/CD with Docker, ECR, Helm, and GitHub Actions
- ML application deployment separation between training and serving

### 2.2 Current application state

- `apps/astro-web` is mostly complete from a product UI perspective
- `apps/api` is mostly complete for auth, model metadata, health probes, and base backend flows
- actual model inference integration is still pending
- `apps/pytorch-engine` is focused on training and experimentation and remains work in progress

### 2.3 Implementation status snapshot

Already done in repo:

- `apps/astro-web` exists as deployable frontend app
- `apps/api` exists with FastAPI routes, auth flows, database access, Alembic migrations, and
  Kubernetes-style probes
- training code is already isolated in `apps/pytorch-engine`
- frontend API base URL is now environment-driven instead of hardcoded localhost
- API Docker packaging has now been aligned to the real repository layout
- production Terraform scaffold now exists under:
  - `infra/terraform/environments/prod`
  - now covering VPC, EKS, ECR, S3/CloudFront, RDS PostgreSQL, optional WAF, frontend Route53,
    prediction artifacts S3 bucket, CloudWatch log group, CloudWatch alarms, and IRSA roles for add-ons plus app
    workloads
- production Helm scaffolding now exists under:
  - `infra/helm/charts/backend-stack`
  - `infra/helm/charts/platform-addons`
- local deployment helper material now exists under:
  - `infra/helm/values/prod.example.yaml`
  - `infra/helm/values/addons.example.yaml`
  - `infra/scripts/deploy-prod.ps1`
  - `infra/scripts/destroy-prod.ps1`
  - `infra/scripts/install-cluster-addons.ps1`
- one-command full release orchestration is intentionally not supported before the first live AWS deployment
- commented GitHub Actions workflow drafts now exist under:
  - `.github/workflows/infra-validate.yml`
  - `.github/workflows/backend-release.yml`
  - `.github/workflows/frontend-release.yml`
- Terraform remote backend example now exists at:
  - `infra/terraform/environments/prod/backend.hcl.example`
- local production value files are intentionally gitignored and must be created from examples before live deploy:
  - `infra/helm/values/prod.yaml`
  - `infra/helm/values/addons.yaml`
  - `infra/terraform/environments/prod/terraform.tfvars`
- detailed operator runbook now exists at:
  - `docs/DEPLOYMENT_RUNBOOK.md`

Still not done:

- Terraform has now been applied to the live AWS account for the first 24-hour prototype. Route53, ACM, VPC, EKS,
  ECR, S3/CloudFront, RDS PostgreSQL, CloudTrail, CloudWatch, IAM, and SSM paths exist in account `123456789012`.
- Helm chart has not yet been released to a live EKS cluster
- `apps/model-service` now exists as the internal Model Runtime app, but has not been released to EKS
- API now expects reachable internal Model Runtime URLs for prediction when real prediction mode is enabled
- production secret values are operator-supplied through SSM Parameter Store; the first live prototype set has been
  uploaded and verified against Terraform `expected_parameter_store_paths`.
- GitHub repository secrets/variables for live CI/CD are intentionally not wired yet

### 2.4 Production scope

In scope:

- one production environment only
- infrastructure required to serve frontend, API, and model inference
- observability, security, deployment automation, and AWS integration

Out of scope:

- non-production AWS environments
- deployment of training workloads
- full MLOps pipeline automation
- multi-region disaster recovery

---

## 3. Current monorepo alignment

### 3.1 Current repository structure

```text
apps/
  api/               FastAPI app, auth, DB access, direct email sending
  astro-web/         Astro frontend
  pytorch-engine/    model training only
infra/
  terraform/         production Terraform scaffold
  helm/              backend Helm chart scaffold
packages/
  ui/                shared frontend UI package
  eslint-config/
  tailwind-config/
  typescript-config/
docs/
  PRD.md
  DEPLOYMENT_RUNBOOK.md
```

### 3.2 Production-oriented additions

```text
apps/
  model-service/     dedicated internal Model Runtime app for PyTorch models
infra/
  terraform/         initial AWS production scaffold now added
  helm/              initial backend Helm chart scaffold now added
```

### 3.3 Important repo truths this PRD must reflect

- `apps/pytorch-engine` is not deployed to production
- `apps/api` sends email directly in request-path service code; no queue-backed email runtime is deployed
- `apps/model-service` exists as the deployable app for the internal Model Runtime Host
- frontend and API are served on separate domains
- production architecture is target-state, not a claim that every piece already exists in code today
- repo now contains initial infra scaffold, but not a completed production deployment

---

## 4. Problem statement

The repo currently has application code but not a clear, production-grade deployment architecture aligned to its
monorepo structure. The copied PRD described a different platform with extra services, mismatched folder names, and
deployment assumptions that do not fit this repository.

The project needs a production PRD that:

- matches the real monorepo structure
- clearly separates training from serving
- uses AWS-native infrastructure where it strengthens the showcase
- remains technically coherent and defensible
- avoids fake complexity unrelated to the current codebase or two-user demo traffic

---

## 5. Production goals and non-goals

### 5.1 Goals

- Deploy frontend, API, and model-serving workloads to production on AWS
- Use Terraform as the canonical IaC layer for AWS resources
- Use EKS as the canonical orchestration layer for deployable backend services
- Use Docker and ECR for backend image delivery
- Use CloudFront and S3 for static frontend delivery
- Use separate model-serving service for custom PyTorch inference
- Use AWS-managed data services where reasonable
- Route logs to CloudWatch at debug visibility for troubleshooting
- Present architecture that is strong for portfolio and interview review
- Keep live AWS cost low enough for a short-lived private demo

### 5.2 Non-goals

- making training part of the production runtime
- designing for hyperscale traffic on day one
- building a full GitOps platform on day one
- introducing services that are not justified by current app scope

---

## 6. Target production architecture

### 6.1 High-level design

```text
Users
  |
  +--> app.<domain>
  |      Route53 -> CloudFront -> private S3 bucket (Astro static site)
  |
  +--> api.<domain>
         Route53 -> ALB -> EKS
                                |
                                +--> api deployment
                                +--> one Model Runtime Host deployment
                                |
                                +--> ClusterIP services for internal API -> Model Runtime traffic

AWS managed services:
  - Amazon RDS for PostgreSQL (single-AZ)
  - AWS Systems Manager Parameter Store
  - Amazon ECR
  - Amazon CloudWatch Logs and Alarms
  - Amazon SNS email subscriptions for alarm notifications
  - ACM
  - Route53
  - AWS WAF optional only; disabled by default
  - S3 buckets for frontend assets and optional prediction artifacts
```

### 6.2 Runtime services

#### Frontend

- app: `apps/astro-web`
- hosting: private S3 bucket + CloudFront with OAC
- domain: `app.<domain>`
- deployment artifact: static build output
- does not run on Kubernetes

#### API

- app: `apps/api`
- framework: FastAPI
- deployment target: EKS
- domain: `api.<domain>`
- ingress: ALB via AWS Load Balancer Controller
- responsibilities:
  - auth
  - user endpoints
  - model metadata endpoints
  - request validation
  - orchestration of prediction requests
  - persistence to PostgreSQL
  - optional S3 persistence for uploaded images or prediction artifacts

#### Model Runtime

- app: `apps/model-service`
- deployment target: EKS
- exposure: internal only through private Kubernetes service
- protocol from API: synchronous internal HTTP/REST
- responsibilities:
  - load custom PyTorch model weights
  - fetch model artifacts from Hugging Face at startup
  - expose prediction endpoint to API
  - keep Model Runtime concerns isolated from public API responsibilities

### 6.3 Node group strategy

Day-one node group:

- one small CPU-focused managed node group for API and Model Runtime workloads

Future option:

- dedicated GPU node group if model size, latency, or throughput requires it

CPU-first inference is the baseline because current custom PyTorch models are relatively small and do not justify
day-one GPU cost. The Model Runtime container installs CPU-only PyTorch dependencies and should run on modest
compute-optimized CPU nodes, not GPU or memory-heavy instance families.

### 6.4 Cost and teardown validation

The current EKS production path is intentionally trimmed, but it should be treated as a short-lived AWS prototype rather
than a low-idle-cost production environment.

Cost floor for 168 deployed hours:

| Cost item         | Current source in infra                                  | 7-day estimate                                         | Budget impact           |
| ----------------- | -------------------------------------------------------- | ------------------------------------------------------ | ----------------------- |
| EKS control plane | `module.eks`                                             | $16.80                                                 | leaves only $3.20       |
| One worker node   | managed node group default `c6a.large`                   | about $14.67 before EBS                                | breaks budget by itself |
| NAT Gateway       | `enable_nat_gateway = true`, `single_nat_gateway = true` | about $7.56 plus data processing in common AWS regions | breaks budget further   |
| RDS PostgreSQL    | default `db.t4g.micro` plus 20 GiB gp3                   | several dollars for 7 days                             | required for backend    |
| ALB               | created by AWS Load Balancer Controller ingress          | several dollars for 7 days                             | required for public API |

Result: full EKS backend deployment is expected to exceed $40 for 7 days even before variable data transfer, logs, image
storage, DNS, snapshots, and CloudFront request costs. For the intended 24-hour live test, the same fixed hourly resources
are acceptable if the stack is destroyed promptly after verification.

Prototype teardown requirements:

- Before prototype apply, set `db_deletion_protection = false` in gitignored `terraform.tfvars`; otherwise Terraform
  destroy is expected to fail on RDS deletion protection.
- For a pure disposable prototype, set `db_skip_final_snapshot = true`; otherwise RDS leaves a final snapshot outside the
  running stack, which is safer but not a complete zero-artifact teardown.
- Destroy through `bun run prod:destroy -- -PurgeS3Buckets -ConfirmDestructiveBucketPurge -AutoApprove` so versioned S3
  buckets are emptied before Terraform destroy.
- Confirm post-destroy that Terraform state is empty and AWS no longer contains project EKS, RDS, ALB, NAT Gateway, ECR,
  S3, CloudWatch, CloudTrail, Route53, IAM, and SSM resources except any intentionally retained DNS hosted zone or final
  RDS snapshot.

---

## 7. AWS service decisions

| Area               | Decision                                        | Notes                                    |
| ------------------ | ----------------------------------------------- | ---------------------------------------- |
| Region             | `eu-central-1`                                  | single primary production region         |
| Compute            | Amazon EKS                                      | canonical orchestration platform         |
| Frontend hosting   | S3 + CloudFront + OAC                           | private bucket, CDN at edge              |
| API ingress        | ALB via AWS Load Balancer Controller            | ACM-managed TLS                          |
| DNS                | Route53                                         | split frontend/API domains               |
| Edge protection    | AWS WAF disabled by default                     | optional future toggle only              |
| Container registry | Amazon ECR                                      | backend images                           |
| Database           | Amazon RDS for PostgreSQL, single-AZ            | standard Postgres, no Aurora requirement |
| Secrets/config     | SSM Parameter Store + External Secrets Operator | no CI-managed secrets                    |
| Logs               | CloudWatch Logs                                 | debug-level visibility                   |
| Log shipping       | Fluent Bit DaemonSet                            | EKS node and container log forwarding    |
| Alarm notification | SNS email subscriptions                         | email-only operator notifications        |
| Certificates       | ACM                                             | frontend/API certificates                |

---

## 8. Inference and model artifact strategy

### 8.1 Serving strategy

Inference is not served from the public API container. The production architecture uses dedicated Model Runtime
workloads on EKS, implemented by `apps/model-service`.

Reasons:

- cleaner separation of responsibilities
- easier independent scaling
- cleaner dependency isolation for PyTorch runtime
- easier future move to GPU if needed

### 8.2 Artifact source

Model weights are stored on Hugging Face, not S3.

Production behavior:

- each Model Runtime deployment pins its own Hugging Face repository, revision, and artifact filename
- pinned values are set through Helm values and environment variables
- container downloads the required model artifact on startup
- deployment remains reproducible because repo, revision, and artifact filename are explicit

This intentionally mirrors the operational benefit of an artifact bucket without requiring S3 as the system of record
for model weights.

### 8.3 Versioning rule

Production deployments must never pull "latest" implicitly.

Required:

- explicit model repository identifier
- explicit revision, tag, or commit SHA
- ability to roll back by redeploying previous Helm values

---

## 9. Data flow

### 9.1 Prediction request flow

1. User accesses `app.<domain>` through CloudFront.
2. Frontend sends prediction request to `api.<domain>`.
3. API validates auth, payload, and model selection.
4. API forwards synchronous internal request to one or more Model Runtimes over private Kubernetes networking.
5. Each Model Runtime runs inference using its loaded PyTorch model.
6. API returns normalized response to frontend.
7. API may store uploaded image or prediction artifact in S3 if retention is required.

### 9.2 Email flow

1. API creates verification token with bounded expiry.
2. API sends verification email directly through configured SMTP settings.
3. Failures are logged and recorded on active OpenTelemetry spans.

### 9.3 Frontend delivery flow

1. Astro build output is uploaded to private S3.
2. CloudFront serves cached static assets.
3. Route53 maps `app.<domain>` to CloudFront.

---

## 10. Kubernetes deployment design

### 10.1 Namespaces

Production namespace:

- `pytorch-model-prod`

### 10.2 Deployments

Required backend deployments:

- `api`
- `model-runtime-host`

### 10.3 Services

- public ingress route for API through ALB
- internal `ClusterIP` service for each Model Runtime

### 10.4 Health checks

`apps/api` already exposes Kubernetes-style probes and production deployment must use them:

- `/livez`
- `/readyz`
- `/startupz`

Equivalent probes are required on the Model Runtime Host; readiness and startup must only succeed after both Model
Artifacts have loaded.

### 10.5 Scaling

- API scales horizontally based on CPU and memory
- Model Runtime Host stays at one replica for the two small CPU-served visual models

---

## 11. Infrastructure as Code ownership

### 11.1 Terraform owns

- VPC and networking
- subnets, route tables, one NAT gateway, security groups
- EKS cluster and managed node groups
- RDS PostgreSQL
- S3 buckets
- ECR repositories
- Route53 records
- ACM certificates where applicable
- optional WAF policies, disabled by default
- IAM roles and IRSA bindings
- SSM Parameter Store paths

### 11.2 Helm owns

- API deployment and service
- one Model Runtime Host deployment and ClusterIP service
- add-on releases such as:
  - AWS Load Balancer Controller
  - External Secrets Operator
  - Fluent Bit

Terraform should not own all application-level Kubernetes objects. Separation remains:

- Terraform for cloud infrastructure
- Helm for cluster application releases

---

## 12. CI/CD strategy

### 12.1 Canonical release flow

GitHub Actions pipeline:

1. run lint, type checks, and tests
2. build backend Docker image for `apps/api`
3. build Docker image for `apps/model-service`
4. push images to Amazon ECR
5. package or update Helm release values with image tags
6. run `helm upgrade` against production EKS cluster
7. invalidate CloudFront cache when frontend deployment requires it

### 12.2 Frontend release flow

1. build Astro static output
2. upload static assets to private S3 bucket
3. invalidate CloudFront distribution as needed

### 12.3 Deliberate exclusions

Not required for day one:

- ArgoCD
- full GitOps manifest sync workflow
- multi-examplenvironment promotion pipeline

They may be documented later as future enhancements.

---

## 13. Security design

### 13.1 Networking

- private subnets for EKS nodes and managed data services
- public entry only through CloudFront and ALB
- Model Runtime Host exposed internally only

### 13.2 Secrets and configuration

- secrets stored in AWS Systems Manager Parameter Store
- External Secrets Operator syncs required values into Kubernetes
- API uses IRSA for AWS access instead of static application credentials
- no production secrets committed to repo
- no production secrets injected directly from CI as the primary pattern

### 13.3 TLS and domains

- ACM certificates for frontend and API domains
- Route53 manages DNS records
- root domain is `oncoray.online`, registered in Namecheap
- Terraform creates the Route53 hosted zone, then Namecheap nameservers are replaced with Terraform output
  `route53_name_servers`
- separate domains:
  - `app.oncoray.online`
  - `api.oncoray.online`

### 13.4 AWS operator identity

- live AWS operations use account `123456789012`
- CLI/Terraform principal is `arn:aws:iam::123456789012:user/pytorch-model-cli-user`
- production `terraform.tfvars` must set `expected_aws_account_id = "123456789012"`
- production `terraform.tfvars` must set
  `expected_aws_principal_arn = "arn:aws:iam::123456789012:user/pytorch-model-cli-user"`
- production preflight with `-RequireAwsIdentity` must pass `aws sts get-caller-identity` and reject any other account or
  principal
- recommended local AWS CLI profile name is `pytorch-model-prod`

### 13.5 Edge protection

- WAF is disabled by default for the budget-first deployment
- CloudFront, ALB, TLS, private S3, private RDS, IRSA, and narrowly-scoped security groups remain the baseline
- WAF may be enabled later if the app becomes public or abuse traffic appears

---

## 14. Logging, monitoring, and alerting

### 14.1 Logging

Requirement:

- application logs must be available in CloudWatch at debug detail when needed for troubleshooting

Implementation:

- backend apps emit structured logs to stdout/stderr
- Fluent Bit runs as DaemonSet in EKS
- Fluent Bit forwards container logs to CloudWatch Logs

### 14.2 Metrics and alarms

CloudWatch alarms should cover at minimum:

- ALB 5xx error rate
- API pod crash loops or unhealthy target count
- RDS CPU/storage/connection pressure
- EKS node pressure where relevant
- alarm state changes delivered through SNS email subscriptions only

### 14.3 Observability scope

Day-one observability stack:

- CloudWatch Logs
- CloudWatch metrics
- CloudWatch alarms
- Fluent Bit
- OpenTelemetry tracing in API and Model Runtime
- Sentry browser error capture for frontend

Not required for day one:

- Prometheus
- Grafana
- OpenSearch
- Datadog

---

## 15. Monorepo implementation plan

### 15.1 Required deployable units

- `apps/astro-web`
- `apps/api`
- `apps/model-service`

### 15.2 Backend image strategy

`apps/api` builds one API image. Queue-backed background processing is not part of the day-one production design.

### 15.3 Training app policy

`apps/pytorch-engine`:

- remains in monorepo
- is used for experimentation and training
- is not part of production deployment
- may publish resulting model weights to Hugging Face outside production runtime

---

## 16. Known gaps between current repo and target production state

These are not failures of the PRD. They are the implementation delta this PRD defines.

- `apps/model-service` exists, but the Model Runtime Host has not been released to live EKS
- API now proxies prediction requests to internal Model Runtime URLs when configured
- S3 upload service in API supports AWS mode, but production S3 wiring has not been exercised live
- API sends verification email directly through SMTP; no queue-backed email runtime remains
- frontend now supports environment-driven API base URL, but production env wiring is still pending
- API and Model Runtime Docker packaging are aligned to the real repository layout, and CI/CD workflow drafts exist, but
  live CI activation is intentionally deferred
- Terraform scaffold now covers VPC, EKS, ECR, S3/CloudFront, RDS, optional WAF, frontend Route53, IRSA,
  and CloudWatch log-group wiring, and has been applied and destroyed successfully against LocalStack. On 2026-05-03 it
  was also applied to live AWS for the first 24-hour prototype after DNS delegation reached Route53.
- Helm scaffold now covers API, Model Runtime manifests, ClusterSecretStore config, and Fluent Bit
  DaemonSet wiring, but live release execution still remains pending. The production example keeps
  `workloads.model-runtime-host.enabled=false` as a safe placeholder; the deploy helper must be run with
  `-EnableModelService` or the operator must set that value to `true` before a real Prediction Workflow can work.
- add-on install automation now exists and the gitignored live `addons.yaml` has been populated from Terraform outputs;
  AWS Load Balancer Controller, External Secrets, and platform add-ons have been installed in live EKS. ClusterSecretStore
  is Ready and Fluent Bit has rolled out.
- Parameter Store naming and External Secret manifests are scaffolded. On 2026-05-03 the prototype SSM parameter file
  was validated against Terraform `expected_parameter_store_paths`; all 14 expected values were uploaded and verified in
  AWS.
- API Route53 record still requires live ALB hostname input after first ingress creation

### 16.1 Pre-final AWS deployment blockers

The following items must be resolved before this repository is treated as ready for final AWS production deployment.
This section records repository-level verification only. Live AWS, operator confirmation, and real deployment proof
remain outside what can be proven from local source files and tests.

#### Done in repo

- Done: Model Runtime Host topology. Helm uses one `model-runtime-host`, the API uses one `MODEL_SERVICE_URL`, and
  `apps/model-service` routes both `effnetb0` and `vitb16` prediction requests by `model`.
- Done: production fail-fast configuration validation. API and Model Runtime startup validation reject unsafe production
  defaults such as development JWT secrets, mock S3 mode, localhost URLs, empty required mail settings, and mutable Model
  Artifact URLs using `/resolve/main/` unless the short-lived prototype override `ALLOW_MUTABLE_MODEL_ARTIFACTS=true` is
  explicitly set.
- Done: explicit database migration step. The backend Helm chart includes a post-install/post-upgrade Alembic migration
  Job, and `deploy-prod.ps1` forces `migrations.enabled=true` while waiting for hook Jobs and workload readiness.
- Done: Kubernetes-style probes exist for API and Model Runtime Host. Helm wires liveness, readiness, and startup probes.
- Done: private frontend bucket, CloudFront OAC, public-access blocks, S3 versioning, and CloudFront security headers are
  represented in Terraform.
- Done: ECR repositories use immutable image tags and scan-on-push.
- Done: RDS is private, encrypted, single-AZ, has backup retention, deletion protection, and final snapshot enabled by
  default.
- Done: Terraform validates that EKS public endpoint CIDRs are explicit and do not include `0.0.0.0/0`.
- Done: Terraform creates SNS email subscriptions from `alarm_email_addresses` and CloudWatch alarms for RDS, API
  ALB target 5xx, API unhealthy targets, and optional EKS node condition metrics.
- Done: Fluent Bit chart forwards EKS workload logs to a Terraform-managed CloudWatch log group.
- Done: frontend Sentry integration and optional source-map upload configuration exist in code.
- Done: Account Verification token expiry exists through `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` and token decode `max_age`.
- Done: local infra validation and Helm rendering are available through `bun run infra:validate` and
  `bun run infra:validate:helm`.
- Done: local infra validation ignores generated Terraform state, plan files, and `.terraform` provider artifacts when
  scanning for patch markers, so locked local state no longer breaks offline validation.
- Done: API test drift from the 2026-05-02 review is fixed. Full API suite now passes locally.
- Done: production `/scalar` access is disabled by default. API startup rejects `SCALAR_DOCS_ENABLED=true` in production,
  and production Helm values set `SCALAR_DOCS_ENABLED` to `"false"`.
- Done: `infra/helm/values/ssm-parameters.prod.example.json` includes the required API AWS region and prediction
  artifacts bucket parameters.
- Done: Terraform `expected_parameter_store_paths` includes the required Model Artifact URL and Hugging Face credential
  paths for the Model Runtime Host.
- Done: `infra/scripts/deploy-prod.ps1` rejects unresolved placeholder values in gitignored `prod.yaml` before Helm can
  deploy it.
- Done: `docs/DEPLOYMENT_RUNBOOK.md` documents the API ALB and target group ARN suffix feedback step required to activate
  API 5xx and unhealthy-target CloudWatch alarms.
- Done: Model Runtime Host validates production Model Artifact URLs and rejects mutable `/resolve/main/` URLs unless the
  explicit short-lived prototype override is enabled.
- Done: Terraform enables EKS control-plane logging for API, audit, authenticator, controller-manager, and scheduler logs
  by default.
- Done: Terraform includes multi-region CloudTrail with log-file validation for basic account audit logging.
- Done: Terraform keeps WAF optional and disabled by default for the budget-first deployment.
- Done: production frontend S3 bucket no longer uses `force_destroy = true`.
- Done: backend Helm chart renders PodDisruptionBudgets for API and Model Runtime Host workloads.
- Done: `docs/DEPLOYMENT_RUNBOOK.md` documents Sentry source-map upload credentials and Model Artifact Parameter Store
  values.
- Done: `infra/scripts/preflight-prod.ps1` validates operator-owned production inputs before AWS deploy attempts.
- Done: `infra/scripts/rollback-prod.ps1` supports Helm release rollback for backend workloads.
- Done: `infra/scripts/destroy-prod.ps1` supports full short-lived production teardown, including explicit S3 bucket
  purge before Terraform destroy.
- Done: Terraform supports a domain registered outside AWS by creating a Route53 hosted zone, outputting nameservers for
  the registrar, and optionally managing ACM certificates for frontend and API domains.
- Done: Terraform can generate the production PostgreSQL password when `db_password = ""`, reducing first-test deploy
  secret handling while keeping the generated database URL sensitive.
- Done: production preflight refuses to run real-AWS checks when the default local Terraform state contains LocalStack
  markers, preventing accidental reuse of fake `000000000000` resources against AWS.
- Done: LocalStack Terraform variables are self-contained for local verification and override operator-owned production
  DNS, ACM, alarm, and CloudTrail toggles so `localstack.tfvars.example` does not accidentally inherit gitignored
  `terraform.tfvars` values.
- Done: LocalStack apply-level verification has been exercised from a clean emulator and clean local Terraform state for
  Terraform-managed AWS resources and the local EKS API path. LocalStack accepted the backend Helm chart with
  `localstack.example.yaml` using zero replicas, and clean Terraform destroy removed the managed resource set.
- Done: live-AWS operator identity has been selected and validated for account `123456789012` with principal
  `arn:aws:iam::123456789012:user/pytorch-model-cli-user` using the `pytorch-model-prod` AWS CLI profile.
- Done: gitignored production Terraform inputs exist locally for DNS bootstrap, including the Namecheap root domain
  `oncoray.online`, expected AWS account and principal guards, and a private operator `/32` EKS API allowlist entry. The
  private operator IP is intentionally not recorded in tracked documentation.
- Done: production DNS-bootstrap preflight passed with `-RequireAwsIdentity`. This validated Terraform formatting,
  Terraform configuration, unresolved-placeholder guards, LocalStack-state reuse guards, and the selected AWS STS
  identity without creating AWS resources.
- Done: targeted Terraform plan and apply for `aws_route53_zone.primary[0]` against live AWS created the Route53 hosted
  zone for `oncoray.online`; Namecheap custom nameservers were updated to the Terraform output.
- Done: DNS delegation propagated enough for ACM DNS validation. Cloudflare `1.1.1.1` and Google `8.8.8.8` returned the
  AWS Route53 nameservers during deployment checks.
- Done: full live AWS Terraform apply completed for the 24-hour prototype. The first apply stopped on unavailable RDS
  PostgreSQL engine `16.4` in `eu-central-1`; the Terraform default was corrected to supported `16.13`, then re-apply
  completed with RDS and RDS alarms created.
- Done: Terraform outputs confirmed EKS cluster `pytorch-model-prod-eks`, frontend CloudFront distribution
  `EEXAMPLEFRONTEND1`, RDS endpoint `pytorch-model-prod-postgres.example.internal:5432`,
  ECR repositories for API and Model Service, and the expected SSM parameter paths.
- Done: production SSM values were validated for placeholder-free content and exact key parity with Terraform
  `expected_parameter_store_paths`; all 14 parameters were uploaded to AWS SSM Parameter Store and verified by path.
- Done: EKS kubeconfig was updated and one managed node reported `Ready`.
- Done: live EKS add-ons were installed after fixing Helm/PowerShell annotation escaping, adding rollout/CRD waits, and
  updating External Secrets resources to `external-secrets.io/v1`. AWS Load Balancer Controller, External Secrets, and
  platform add-ons Helm releases are deployed; ClusterSecretStore is Ready and Fluent Bit rolled out.
- Done: gitignored `infra/helm/values/prod.yaml` was created for the live prototype with real domains, IRSA role ARNs,
  ACM certificate ARN, ECR repositories, immutable image tag `sha-97f9f0cfa5f7`, and Model Runtime Host enabled.
- Done: API and Model Service images were built locally and pushed to ECR with tag `sha-97f9f0cfa5f7`.
- Done: full production preflight passed for Terraform, backend Helm, platform Helm, and AWS identity.
- Done: first backend Helm install exposed a migration hook ordering bug. The hook Job ran before normal ServiceAccount
  and ExternalSecret resources, so Kubernetes rejected the pod because `pytorch-model-api` did not yet exist. The chart
  now runs migrations as a `post-install,post-upgrade` hook, and `deploy-prod.ps1` forces `migrations.enabled=true`
  while waiting for hook Jobs and workload readiness.
- Done: first migration attempt failed because Alembic wrote the URL-encoded RDS password containing `%` into
  ConfigParser without escaping. `apps/api/src/migrations/env.py` now escapes `%` before `set_main_option`.
- Done: Model Runtime Host failed fast because production validation rejects `/resolve/main/`. For this approved
  24-hour prototype, `ALLOW_MUTABLE_MODEL_ARTIFACTS=true` is set in `prod.yaml`; default remains false so long-lived
  production still requires pinned Hugging Face revisions. Model Service image tag `sha-97f9f0cfa5f7-hfmain` carries this
  config support.
- Done: one-node prototype hit API rollout CPU pressure because HPA min replicas rendered two API pods. `prod.yaml`
  disables API autoscaling for this 24-hour run so API stays at one replica and leaves room for Model Runtime Host.
- Done: model-runtime rollout was stuck because the old crashing pod still reserved node CPU/memory while the fixed
  pod was Pending. Helm force-replace is blocked by this Helm/server-side-apply combination, so live `prod.yaml` lowers
  Model Runtime Host requests to `100m` CPU and `512Mi` memory for the one-node prototype while keeping higher limits.
- Done: backend became healthy after the first-deploy fixes. API pod was `1/1 Running`, Model Runtime Host pod was
  `1/1 Running`, and logs confirmed both approved Hugging Face `/resolve/main/` artifact URLs fetched and loaded
  in-cluster.
- Done: Terraform created `api.oncoray.online` CNAME to the ingress ALB. Public API smoke passed with local proxy env
  cleared: `/livez` returned `200` and `/readyz` returned `200` with database check true.
- Done: API ALB CloudWatch alarms were created after capturing ALB and target group suffixes.
- Done: frontend built with `PUBLIC_API_BASE_URL=https://api.oncoray.online`, synced to
  `s3://pytorch-model-prod-frontend-123456789012`, and CloudFront invalidation `IEXAMPLEINVALIDATION1` started.
  Public frontend smoke passed: `https://app.oncoray.online/` returned `200`.
- Done: frontend route smoke found CloudFront served dashboard HTML for `/login` and `/register`, causing the browser
  auth guard to reload continuously. Terraform now adds a CloudFront Function that rewrites Astro static routes to S3
  `*/index.html` objects. Live frontend aliases now include both `app.oncoray.online` and `oncoray.online`, with
  Route53 A/AAAA aliases to CloudFront.
- Done: browser smoke verified `https://app.oncoray.online/` navigates once to `/login`, renders `Log In | OncoRay`,
  shows the login button, and emits no console errors. Direct HTTPS smoke verified `https://app.oncoray.online/login`,
  `/register`, and apex `https://oncoray.online/login` through CloudFront.
- Done: CORS preflight works from both `https://app.oncoray.online` and `https://oncoray.online`. Backend Helm prod
  values include both origins in `CORS_ALLOWED_ORIGINS`, API rollout completed, and `/readyz` still returns database
  healthy.
- Done: first AWS prototype deployment served API and frontend, then teardown was executed and verified.
- Done: 2026-05-03 AWS teardown completed. Terraform state was empty and
  verification found no EKS, RDS, ALB, CloudFront, S3, ECR, Route53, SSM, IAM role, CloudTrail, CloudWatch alarm, or EKS
  log-group leftovers for the prototype. The destroy script now also supports SSM purging and partial reruns with
  explicit extra S3 buckets.
- Done: Resource Explorer follow-up found the reported EC2 volume and ENIs already deleted by direct EC2 APIs, and the
  reported EC2 instance is terminated history only. The remaining KMS key is disabled and `PendingDeletion`; deletion was
  rescheduled to the minimum 7-day window ending 2026-05-10. Future EKS KMS keys use
  `kms_key_deletion_window_in_days = 7`.
- Done: first deployment failure analysis informed repo fixes that now cover the
  failures that were patched live during the first deployment: migration hook ordering, Alembic `%` escaping,
  one-node scheduling values, mutable model artifact prototype override, CloudFront static route rewrite, apex CORS,
  add-on readiness races, RDS engine version, and teardown cleanup gaps.
- Done: 2026-05-03 infra budget review found the Terraform and Helm setup validates locally. The full EKS production
  path is not compatible with a hard $20/7-day budget, but it is acceptable for the intended roughly 24-hour AWS
  prototype if teardown is run promptly.

#### P0 - deployment blockers

- Done for current prototype: teardown settings were resolved before full live AWS apply. Gitignored
  `terraform.tfvars` must set `db_deletion_protection = false`; set `db_skip_final_snapshot = true` when no final RDS
  snapshot should remain after destroy.
- Done for current prototype: targeted DNS bootstrap plan/apply for
  `aws_route53_zone.primary[0]`. The reviewed plan currently contains only the Route53 hosted zone for
  `oncoray.online`.
- Done for current prototype: Terraform output `route53_name_servers` was pasted into Namecheap custom nameservers and
  delegation to propagate.
- Done for current prototype: after delegation, `enable_managed_acm_certificates = true` was set and Terraform applied the
  managed ACM certificate path so frontend and API certificates can be requested and DNS-validated.
- Current blocker before second public API smoke: repeat the deploy runbook from DNS bootstrap with fresh Route53
  nameservers, fresh SSM upload, fresh image tags, backend Helm release through `deploy-prod.ps1`, migration hook/workload
  wait, ingress ALB capture, and API DNS Terraform apply.
- Prove one live manual deployment path before enabling or depending on release automation. GitHub Actions release
  workflows exist only as commented drafts, which matches the manual-first ADR, but final deployment still requires
  Terraform apply, image push, Helm release, DNS wiring, and workload health proof in a real AWS account.

#### P1 - production readiness blockers

- Validate application-level observability in live AWS. API and Model Runtime now have OpenTelemetry hooks, but final
  deployment still must confirm OTLP export, trace attributes, and exception recording in the target collector.
- Validate runtime error detection. Frontend Sentry integration and source-map upload configuration exist, but production
  still needs operator-owned DSN, environment, release, auth token, org, and project values before browser errors are
  actionable.
- Confirm alarm email subscribers. Terraform creates SNS email subscriptions from `alarm_email_addresses`, but each
  recipient must confirm the AWS SNS subscription before final deployment is considered monitored.
- Tighten frontend authentication storage before real users. The frontend stores JWTs in browser storage through
  `localStorage` and `sessionStorage`, which is acceptable for a private showcase but weaker than HttpOnly Secure
  SameSite cookies. Final deployment must either move auth to cookie-backed sessions or explicitly accept the
  browser-storage risk in an ADR.
- Pin Model Artifact source by immutable Hugging Face revision for long-lived production. Model Runtime production
  validation rejects `/resolve/main/` unless the explicit short-lived prototype override is enabled. Operator must supply
  reviewed Hugging Face URLs plus non-empty `HF_TOKEN` before deploy.

#### P2 - hardening before public launch

- Add a post-deploy synthetic smoke test covering frontend load, API health, login/register, Model Catalog read,
  Prediction Workflow execution with a fixture Chest X-ray Upload, S3 persistence status, and CloudWatch log visibility.
- Add restore and rollback drills for RDS, S3 prediction artifacts, Helm release rollback, and previous frontend
  CloudFront/S3 artifact versions.
- Add an image vulnerability gate based on ECR scan results or equivalent CI security scanning before deploying backend
  images. ECR scan-on-push exists, but no release gate consumes scan findings yet.
- Review access logging and retention for CloudFront, ALB, API, and Model Runtime logs. Explicit CloudFront and ALB
  access log delivery still need implementation or a documented deferral.
- Decide whether NetworkPolicies are required for namespace-level isolation inside EKS.

#### Verification snapshot - 2026-05-02

Verification commands run:

Kubernetes commands used `KUBECONFIG=tmp/localstack-kubeconfig` and the LocalStack `NO_PROXY` settings from the runbook.

```text
bun run infra:validate
bun run infra:validate:helm
uv run --project apps\api pytest apps\api\src\tests -q
uv run --project apps\model-service pytest apps\model-service\src\tests -q
uv run --project apps\model-service ruff check apps\model-service\src\config.py apps\model-service\src\runtime_definition.py apps\model-service\src\tests\test_config.py apps\model-service\src\tests\test_runtime_definition.py
terraform -chdir=infra\terraform\environments\prod validate
localstack state reset
terraform plan "-var-file=localstack.tfvars.example" "-lock=false" "-no-color"
terraform apply "-var-file=localstack.tfvars.example" "-lock=false" "-auto-approve" "-no-color"
aws --endpoint-url=http://localhost:4566 --region eu-central-1 s3api list-buckets
aws --endpoint-url=http://localhost:4566 --region eu-central-1 ecr describe-repositories
aws --endpoint-url=http://localhost:4566 --region eu-central-1 eks describe-cluster --name pytorch-model-local-eks
aws --endpoint-url=http://localhost:4566 --region eu-central-1 rds describe-db-instances --db-instance-identifier pytorch-model-local-postgres
aws --endpoint-url=http://localhost:4566 --region eu-central-1 logs describe-log-groups --log-group-name-prefix /aws/eks/pytorch-model-local-eks
aws --endpoint-url=http://localhost:4566 --region eu-central-1 cloudwatch describe-alarms --alarm-name-prefix pytorch-model-local
aws --endpoint-url=http://localhost:4566 eks update-kubeconfig --name pytorch-model-local-eks --region eu-central-1 --kubeconfig tmp/localstack-kubeconfig
kubectl cluster-info
kubectl get namespaces
helm upgrade --install pytorch-model infra\helm\charts\backend-stack -f infra\helm\values\localstack.example.yaml --namespace pytorch-model-prod --create-namespace
helm status pytorch-model --namespace pytorch-model-prod
kubectl get all,pdb,sa -n pytorch-model-prod
terraform plan "-var-file=localstack.tfvars.example" "-lock=false" "-refresh=false" "-no-color"
helm uninstall pytorch-model --namespace pytorch-model-prod
terraform destroy "-var-file=localstack.tfvars.example" "-lock=false" "-auto-approve" "-refresh=false" "-no-color"
terraform -chdir=infra\terraform\environments\prod state list
aws --endpoint-url=http://localhost:4566 --region eu-central-1 eks list-clusters
aws --endpoint-url=http://localhost:4566 --region eu-central-1 rds describe-db-instances
aws sts get-caller-identity --profile pytorch-model-prod --region eu-central-1
bun run prod:preflight -- -Phase DnsBootstrap -RequireAwsIdentity
terraform "-chdir=infra\terraform\environments\prod" plan "-var-file=terraform.tfvars" "-target=aws_route53_zone.primary[0]" "-no-color"
bun test src/lib
bun test ./src/lib/auth-session.test.ts ./src/lib/model-catalog-selection.test.ts ./src/lib/prediction-result-view-model.test.ts
```

Verification result:

- `bun run infra:validate`: passed with zero failures and zero warnings.
- `bun run infra:validate:helm`: passed with zero failures and zero warnings.
- `apps/model-service` tests: 43 passed.
- `apps/api` tests: 240 passed.
- `apps/model-service` targeted ruff check: passed.
- `terraform validate` for `infra/terraform/environments/prod`: passed.
- LocalStack emulator state was reset, ignored local Terraform state and plan files were removed, and Terraform was run
  from clean local state against account `000000000000`.
- LocalStack Terraform plan passed with `94 to add, 0 to change, 0 to destroy`.
- LocalStack Terraform apply passed with `94 added, 0 changed, 0 destroyed`.
- LocalStack AWS endpoint checks confirmed frontend and prediction artifact S3 buckets, immutable scan-on-push ECR
  repositories, active EKS cluster, available private RDS PostgreSQL, EKS CloudWatch log groups, and RDS CloudWatch
  alarms.
- LocalStack EKS kubeconfig worked. `kubectl cluster-info` reached `https://localhost.localstack.cloud:4511`, and
  default Kubernetes namespaces were readable.
- LocalStack backend Helm install passed in namespace `pytorch-model-prod` using `localstack.example.yaml`. It created
  ServiceAccount, ClusterIP Service, Deployment with `0/0` replicas, ReplicaSet with `0` desired replicas, and
  PodDisruptionBudget. No pods were expected because LocalStack values set API replicas to `0`.
- Post-apply Terraform plan had no adds or destroys, but LocalStack returned provider read-back drift for CloudFront
  forwarded values, subnet group tag readback, and S3 bucket policy formatting. Treat this as an
  emulator compatibility caveat, not live-AWS proof.
- LocalStack backend Helm uninstall passed before infrastructure teardown.
- Clean LocalStack Terraform destroy passed with `94 destroyed`.
- Post-destroy checks showed empty Terraform state; no project S3 buckets, ECR repositories, EKS clusters, RDS instances,
  SSM parameters, EKS log groups, or project CloudWatch alarms remained. LocalStack retained only its default VPC.
- Live AWS STS identity check passed for profile `pytorch-model-prod`, account `123456789012`, and principal
  `arn:aws:iam::123456789012:user/pytorch-model-cli-user`.
- Production DNS-bootstrap preflight passed without creating AWS resources.
- Targeted live-AWS Terraform plan for `aws_route53_zone.primary[0]` passed with `1 to add, 0 to change, 0 to destroy`.
  The planned create is only the Route53 hosted zone for `oncoray.online`; no apply was run.
- frontend focused unit tests not importing `api.ts`: 15 passed.
- full frontend `src/lib` test run failed because tests importing `api.ts` could not resolve `@sentry/astro` from Bun.

#### Verification snapshot - 2026-05-03

Additional infra review commands run:

```text
bun run infra:validate
bun run infra:validate:helm
terraform -chdir=infra\terraform\environments\prod validate
terraform -chdir=infra\terraform\modules\workload-identities test
helm template pytorch-model infra\helm\charts\backend-stack -f infra\helm\values\prod.example.yaml --set workloads.model-runtime-host.enabled=true --set workloads.api.image.repository=repo/api --set workloads.api.image.tag=sha-test --set migrations.image.repository=repo/api --set migrations.image.tag=sha-test --set workloads.model-runtime-host.image.repository=repo/model-service --set workloads.model-runtime-host.image.tag=sha-test --namespace pytorch-model-prod
```

Verification result:

- `bun run infra:validate`: passed with zero failures and zero warnings.
- `bun run infra:validate:helm`: passed with zero failures and zero warnings.
- `terraform validate` for `infra/terraform/environments/prod`: passed.
- `terraform test` for `infra/terraform/modules/workload-identities`: 2 passed, 0 failed.
- Helm rendering with Model Runtime Host explicitly enabled produced API Deployment, Model Runtime Host Deployment,
  ClusterIP Services, API HPA, PDBs, ExternalSecret, Ingress, and migration Job.
- Cost validation confirmed the full EKS deployment cannot stay within $20 for 7 deployed days. This is no longer treated
  as a blocker because the intended AWS test window is roughly 24 hours followed by teardown.

---

## 17. Definition of done

This production deployment initiative is complete when all statements below are true:

- frontend is deployed to private S3 and served through CloudFront on `app.<domain>`
- API is deployed to EKS behind ALB on `api.<domain>`
- one Model Runtime Host is deployed separately on EKS and serves both custom PyTorch models
- PostgreSQL runs on RDS single-AZ with backups
- backend images are stored in ECR
- Terraform provisions AWS infrastructure
- Helm deploys Kubernetes workloads
- model artifact source is pinned Hugging Face repo + revision
- logs from EKS workloads arrive in CloudWatch
- ACM and Route53 are configured for production entry points

---

## 18. Budget-constrained alternative

Fallback only if the project later needs a hard multi-exampley low-cost backend.

Possible cheaper alternative:

- keep CloudFront + S3 for frontend
- replace EKS with ECS or EC2-based Docker deployment
- collapse Model Runtime and API responsibilities for very small-scale demo traffic
- add queue-backed background processing only if async load grows enough to justify it

This option is cheaper, but weaker as a Kubernetes showcase. Primary PRD remains AWS + Terraform + EKS for the 24-hour
prototype path.
