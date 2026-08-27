# Deployment Command Reference

Command catalog for deployment, validation, smoke testing, rollback, and teardown. Prefer scripted paths when both
scripted and raw fallback commands exist.

## AWS Identity and Shell

```powershell
aws configure --profile pytorch-model-prod
$env:AWS_PROFILE = "pytorch-model-prod"
$env:AWS_REGION = "eu-central-1"
$env:AWS_DEFAULT_REGION = "eu-central-1"
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
aws sts get-caller-identity
aws sts get-caller-identity --region eu-central-1
aws sts get-caller-identity --profile pytorch-model-prod --region eu-central-1
```

## Local Validation

```powershell
bun run infra:bootstrap
bun run infra:bootstrap:install
bun run infra:validate
bun run infra:validate:helm
bun run infra:validate:env
bun run prod:preflight -- -Phase DnsBootstrap -RequireAwsIdentity
bun run prod:preflight -- -Phase FullDeploy -RequireAwsIdentity
bun run build
bun run lint
bun run check-types
bun run contract:generate
```

## Terraform Validation and Init

```powershell
bun run infra:terraform:init
terraform -chdir=infra/terraform/environments/prod init -backend=false
terraform -chdir=infra/terraform/environments/prod init -backend-config=backend.hcl
terraform -chdir=infra/terraform/environments/prod fmt -check
terraform -chdir=infra/terraform/environments/prod validate
terraform -chdir=infra/terraform/modules/workload-identities test
```

PowerShell-safe argument-array form for stubborn Terraform target quoting:

```powershell
terraform "-chdir=infra\terraform\environments\prod" plan "-var-file=terraform.tfvars" "-target=aws_route53_zone.primary[0]" "-no-color"
```

## LocalStack Verification

```powershell
terraform -chdir=infra/terraform/environments/prod init -backend=false
terraform -chdir=infra/terraform/environments/prod plan -var-file=localstack.tfvars.example
terraform -chdir=infra/terraform/environments/prod apply -var-file=localstack.tfvars.example -auto-approve
terraform plan "-var-file=localstack.tfvars.example" "-lock=false" "-no-color"
terraform apply "-var-file=localstack.tfvars.example" "-lock=false" "-auto-approve" "-no-color"

aws --endpoint-url=http://localhost:4566 --region eu-central-1 s3api list-buckets
aws --endpoint-url=http://localhost:4566 --region eu-central-1 ecr describe-repositories
aws --endpoint-url=http://localhost:4566 --region eu-central-1 eks describe-cluster --name pytorch-model-local-eks
aws --endpoint-url=http://localhost:4566 --region eu-central-1 rds describe-db-instances --db-instance-identifier pytorch-model-local-postgres
aws --endpoint-url=http://localhost:4566 --region eu-central-1 logs describe-log-groups --log-group-name-prefix /aws/eks/pytorch-model-local-eks
aws --endpoint-url=http://localhost:4566 --region eu-central-1 cloudwatch describe-alarms --alarm-name-prefix pytorch-model-local

$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_DEFAULT_REGION = "eu-central-1"
aws --endpoint-url=http://localhost:4566 eks update-kubeconfig --name pytorch-model-local-eks --region eu-central-1 --kubeconfig tmp/localstack-kubeconfig

$env:KUBECONFIG = "$PWD/tmp/localstack-kubeconfig"
$env:NO_PROXY = "localhost,127.0.0.1,localhost.localstack.cloud,.localhost.localstack.cloud"
$env:HTTPS_PROXY = ""
$env:HTTP_PROXY = ""
kubectl cluster-info
kubectl get namespaces
kubectl get nodes

helm upgrade --install pytorch-model infra\helm\charts\backend-stack -f infra\helm\values\localstack.example.yaml --namespace pytorch-model-prod --create-namespace
helm status pytorch-model --namespace pytorch-model-prod
kubectl get all,pdb,sa -n pytorch-model-prod

powershell -ExecutionPolicy Bypass -File infra/scripts/deploy-prod.ps1 `
  -ValuesFile infra/helm/values/localstack.example.yaml `
  -ApiImageRepository 000000000000.dkr.ecr.eu-central-1.localhost.localstack.cloud:4566/pytorch-model/api `
  -ApiImageTag sha-localstack

terraform plan "-var-file=localstack.tfvars.example" "-lock=false" "-refresh=false" "-no-color"
helm uninstall pytorch-model --namespace pytorch-model-prod
terraform destroy "-var-file=localstack.tfvars.example" "-lock=false" "-auto-approve" "-refresh=false" "-no-color"
terraform -chdir=infra\terraform\environments\prod state list
aws --endpoint-url=http://localhost:4566 --region eu-central-1 eks list-clusters
aws --endpoint-url=http://localhost:4566 --region eu-central-1 rds describe-db-instances
```

## DNS Bootstrap and Terraform Apply

```powershell
terraform -chdir=infra\terraform\environments\prod plan -var-file=terraform.tfvars -target='aws_route53_zone.primary[0]'
terraform -chdir=infra\terraform\environments\prod plan -var-file=terraform.tfvars -target="aws_route53_zone.primary[0]" -no-color
terraform -chdir=infra\terraform\environments\prod apply -var-file=terraform.tfvars -target='aws_route53_zone.primary[0]'
terraform -chdir=infra\terraform\environments\prod apply -var-file=terraform.tfvars -target="aws_route53_zone.primary[0]"
terraform -chdir=infra\terraform\environments\prod output route53_name_servers

terraform -chdir=infra\terraform\environments\prod plan -var-file=terraform.tfvars
terraform -chdir=infra\terraform\environments\prod apply -var-file=terraform.tfvars
terraform -chdir=infra\terraform\environments\prod apply -var-file=terraform.tfvars -auto-approve
terraform -chdir=infra\terraform\environments\prod output
terraform -chdir=infra\terraform\environments\prod output -raw postgres_database_url
```

## Kubernetes Access and Add-ons

```powershell
aws eks update-kubeconfig --region eu-central-1 --name pytorch-model-prod-eks
aws eks update-kubeconfig --region <aws_region> --name <cluster_name>
kubectl get nodes
kubectl get nodes -o wide
kubectl get pods -A
helm list -A

powershell -ExecutionPolicy Bypass -File infra/scripts/install-cluster-addons.ps1 `
  -ClusterName pytorch-model-prod-eks `
  -VpcId <vpc_id> `
  -LoadBalancerControllerRoleArn <alb_role_arn> `
  -ExternalSecretsRoleArn <external_secrets_role_arn> `
  -FluentBitRoleArn <fluent_bit_role_arn> `
  -PlatformValuesFile infra/helm/values/addons.yaml

kubectl get clustersecretstore
```

## SSM Parameters

```powershell
aws ssm put-parameter --name /pytorch-model/prod/api/SECRET_KEY --type SecureString --value "<value>" --overwrite
aws ssm put-parameter --name /pytorch-model/prod/api/CORE_API_DATABASE_URL --type SecureString --value "<value>" --overwrite
$env:PYTORCH_MODEL_EXPECTED_AWS_ACCOUNT_ID = "123456789012"
$env:PYTORCH_MODEL_EXPECTED_AWS_PRINCIPAL_ARN = "arn:aws:iam::123456789012:user/pytorch-model-cli-user"
bun run prod:ssm:put -- -DryRun
bun run prod:ssm:put
aws ssm get-parameters-by-path --path /pytorch-model/prod --recursive
aws ssm get-parameters-by-path --path /pytorch-model/prod --recursive --with-decryption --region eu-central-1
```

## Build and Push Images

```powershell
$tag = "sha-<git_short_sha>"
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.eu-central-1.amazonaws.com
aws ecr get-login-password --region <aws_region> | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<aws_region>.amazonaws.com
docker logout 123456789012.dkr.ecr.eu-central-1.amazonaws.com
docker build -t <api_repo>:$tag apps/api
docker push <api_repo>:$tag
docker build -t <model_service_repo>:$tag apps/model-service
docker push <model_service_repo>:$tag
docker build -t <api_repo>:<sha_tag> apps/api
docker push <api_repo>:<sha_tag>
docker build -t <model_service_repo>:<sha_tag> apps/model-service
docker push <model_service_repo>:<sha_tag>
```

## Backend Helm Deploy

```powershell
bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag <tag> `
  -DryRun

bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag <tag>

bun run prod:deploy:backend -- `
  -ValuesFile infra/helm/values/prod.yaml `
  -ApiImageRepository <api_repo> `
  -ApiImageTag $tag `
  -EnableModelService `
  -ModelServiceImageRepository <model_service_repo> `
  -ModelServiceImageTag $tag `
  -Timeout 15m

kubectl get all -n pytorch-model-prod
kubectl get deploy,ingress,externalsecret -n pytorch-model-prod
kubectl get ingress -n pytorch-model-prod
kubectl get externalsecrets -n pytorch-model-prod
helm status pytorch-model -n pytorch-model-prod
kubectl logs -n pytorch-model-prod deploy/pytorch-model-backend-stack-api
```

Helm render command used in verification:

```powershell
helm template pytorch-model infra\helm\charts\backend-stack -f infra\helm\values\prod.example.yaml --set workloads.model-runtime-host.enabled=true --set workloads.api.image.repository=repo/api --set workloads.api.image.tag=sha-test --set migrations.image.repository=repo/api --set migrations.image.tag=sha-test --set workloads.model-runtime-host.image.repository=repo/model-service --set workloads.model-runtime-host.image.tag=sha-test --namespace pytorch-model-prod
```

## API DNS and ALB Alarms

```powershell
$apiAlbDnsName = (kubectl get ingress -n pytorch-model-prod -o jsonpath="{.items[0].status.loadBalancer.ingress[0].hostname}")
$apiAlbDnsName = (kubectl get ingress -n pytorch-model-prod `
  -o jsonpath="{.items[0].status.loadBalancer.ingress[0].hostname}")
$apiAlbDnsName

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

terraform -chdir=infra/terraform/environments/prod plan -var-file=terraform.tfvars
terraform -chdir=infra/terraform/environments/prod apply -var-file=terraform.tfvars
```

## Frontend Build and Publish

```powershell
$env:PUBLIC_API_BASE_URL = "https://api.oncoray.online"
$env:PUBLIC_APP_ENVIRONMENT = "production"
$env:PUBLIC_APP_RELEASE = "<sha_tag>"
$env:PUBLIC_SENTRY_DSN = "<sentry_dsn_or_empty>"
$env:PUBLIC_SENTRY_TRACES_SAMPLE_RATE = "0.1"
$env:SENTRY_AUTH_TOKEN = "<source_map_upload_token_or_empty>"
$env:SENTRY_ORG = "<sentry_org_or_empty>"
$env:SENTRY_PROJECT = "<sentry_project_or_empty>"

bun run --cwd apps/astro-web build
bun --cwd apps\astro-web run astro build

Set-Location apps/astro-web
bun run build
Set-Location ../..

cd apps\astro-web
node .\node_modules\astro\bin\astro.mjs build
cd ..\..

aws s3 sync apps/astro-web/dist s3://<frontend_bucket_name> --delete
aws s3 sync apps\astro-web\dist s3://<frontend_bucket_name> --delete
aws cloudfront create-invalidation --distribution-id <frontend_distribution_id> --paths "/*"
```

## Smoke Tests

```powershell
kubectl get pods -n pytorch-model-prod
kubectl get pods -A
Invoke-WebRequest https://api.oncoray.online/livez
Invoke-WebRequest https://api.oncoray.online/readyz
Invoke-WebRequest https://app.oncoray.online/login/
Invoke-WebRequest https://oncoray.online/login/
Invoke-WebRequest https://api.example.com/livez
Invoke-WebRequest https://api.example.com/readyz
kubectl logs -n pytorch-model-prod deploy/pytorch-model-backend-stack-api
kubectl exec -n pytorch-model-prod deploy/pytorch-model-backend-stack-api -- python scripts/verify_s3_upload.py
```

## Rollback and Destroy

```powershell
bun run prod:rollback
bun run prod:rollback -- -Revision <revision>

bun run prod:destroy -- -PurgeS3Buckets -ConfirmDestructiveBucketPurge -PurgeSsmParameters -AutoApprove
bun run prod:destroy -- `
  -PurgeS3Buckets `
  -ConfirmDestructiveBucketPurge `
  -PurgeSsmParameters `
  -AutoApprove
bun run prod:destroy -- `
  -PurgeS3Buckets `
  -AdditionalS3Buckets <bucket-name> `
  -ConfirmDestructiveBucketPurge `
  -PurgeSsmParameters `
  -AutoApprove

powershell -ExecutionPolicy Bypass -File infra/scripts/destroy-prod.ps1 `
  -PurgeS3Buckets `
  -ConfirmDestructiveBucketPurge `
  -PurgeSsmParameters `
  -AutoApprove
powershell -ExecutionPolicy Bypass -File infra/scripts/destroy-prod.ps1 `
  -PurgeS3Buckets `
  -AdditionalS3Buckets pytorch-model-prod-cloudtrail-123456789012 `
  -ConfirmDestructiveBucketPurge `
  -PurgeSsmParameters `
  -AutoApprove

terraform -chdir=infra/terraform/environments/prod destroy -var-file=terraform.tfvars
```

## Post-Teardown Verification

```powershell
terraform -chdir=infra\terraform\environments\prod state list
terraform -chdir=infra\terraform\environments\prod plan -destroy -var-file=terraform.tfvars -detailed-exitcode
terraform -chdir=infra/terraform/environments/prod state list
terraform -chdir=infra/terraform/environments/prod plan -destroy -detailed-exitcode
aws eks list-clusters --region eu-central-1
aws eks describe-cluster --name pytorch-model-prod-eks
aws rds describe-db-instances --region eu-central-1
aws rds describe-db-instances
aws ecr describe-repositories --region eu-central-1
aws ecr describe-repositories
aws s3api list-buckets
aws ssm describe-parameters --parameter-filters Key=Name,Option=BeginsWith,Values=/pytorch-model/prod --region eu-central-1
aws ssm get-parameters-by-path --path /pytorch-model/prod --recursive
aws elbv2 describe-load-balancers
aws ec2 describe-vpcs --filters Name=tag:Project,Values=pytorch-model
aws cloudfront list-distributions
aws route53 list-hosted-zones-by-name --dns-name oncoray.online
aws cloudwatch describe-alarms --alarm-name-prefix pytorch-model-prod
aws logs describe-log-groups --log-group-name-prefix /aws/eks/pytorch-model-prod
aws cloudtrail describe-trails
aws iam list-roles
helm list -A
```
