param(
    [string]$ProjectName = "pytorch-model",
    [string]$Environment = "prod",
    [string]$ReleaseName = "pytorch-model",
    [string]$Namespace = "pytorch-model-prod",
    [string]$TerraformDir = "infra/terraform/environments/prod",
    [string]$TerraformVarsFile = "terraform.tfvars",
    [string]$BackendConfigFile = "",
    [string]$PlatformValuesFile = "infra/helm/values/addons.yaml",
    [string]$BackendValuesFile = "infra/helm/values/prod.yaml",
    [string]$ParameterManifestFile = "",
    [string]$ApiImageRepository = "",
    [Parameter(Mandatory = $true)]
    [string]$ApiImageTag,
    [string]$WorkerImageRepository = "",
    [string]$WorkerImageTag = "",
    [string]$ModelServiceImageRepository = "",
    [string]$ModelServiceImageTag = "",
    [string]$PublicApiBaseUrl = "",
    [switch]$BuildApiImage,
    [switch]$PushApiImage,
    [switch]$BuildFrontend,
    [switch]$EnableModelService,
    [switch]$SyncApiEdge,
    [switch]$SkipTerraform,
    [switch]$SkipAddons,
    [switch]$SkipParameterSync,
    [switch]$SkipBackendDeploy,
    [switch]$SkipFrontendDeploy,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found in PATH."
    }
}

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$RepoRoot, [Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return Join-Path $RepoRoot $PathValue
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Get-TerraformOutputs {
    param([Parameter(Mandatory = $true)][string]$TerraformDirectory)

    $json = & terraform "-chdir=$TerraformDirectory" output -json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read Terraform outputs."
    }

    return $json | ConvertFrom-Json -AsHashtable
}

function Get-OutputValue {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Outputs,
        [Parameter(Mandatory = $true)][string]$Name
    )

    return $Outputs[$Name].value
}

function Get-ParameterManifest {
    param([string]$PathValue)

    if (-not $PathValue) {
        return @()
    }

    $manifestPath = Resolve-Path -LiteralPath $PathValue
    $raw = Get-Content -Raw $manifestPath
    $items = $raw | ConvertFrom-Json
    if ($items -isnot [System.Collections.IEnumerable]) {
        throw "Parameter manifest must be a JSON array."
    }

    return @($items)
}

function Merge-Parameters {
    param(
        [Parameter(Mandatory = $true)][object[]]$Derived,
        [Parameter(Mandatory = $true)][object[]]$Manifest
    )

    $byName = [ordered]@{}
    foreach ($item in $Derived + $Manifest) {
        $byName[$item.name] = $item
    }

    return @($byName.Values)
}

function Sync-SsmParameters {
    param(
        [Parameter(Mandatory = $true)][object[]]$Parameters
    )

    foreach ($parameter in $Parameters) {
        $args = @(
            "ssm",
            "put-parameter",
            "--name",
            $parameter.name,
            "--type",
            $parameter.type,
            "--value",
            [string]$parameter.value,
            "--overwrite"
        )

        Invoke-External -FilePath "aws" -Arguments $args
    }
}

function Wait-ForIngressHostname {
    param(
        [Parameter(Mandatory = $true)][string]$IngressName,
        [Parameter(Mandatory = $true)][string]$Namespace,
        [int]$TimeoutSeconds = 600
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $hostname = & kubectl get ingress $IngressName -n $Namespace -o "jsonpath={.status.loadBalancer.ingress[0].hostname}"
        if ($LASTEXITCODE -eq 0 -and $hostname) {
            return $hostname.Trim()
        }

        Start-Sleep -Seconds 10
    }

    throw "Timed out waiting for ingress hostname for $IngressName."
}

function Get-ApiAlbState {
    param(
        [Parameter(Mandatory = $true)][string]$DnsName
    )

    $loadBalancers = & aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='$DnsName']" --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $loadBalancers.Count -eq 0) {
        throw "Could not resolve ALB state for DNS name $DnsName."
    }

    $loadBalancerArn = $loadBalancers[0].LoadBalancerArn
    $targetGroups = & aws elbv2 describe-target-groups --load-balancer-arn $loadBalancerArn --query "TargetGroups" --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $targetGroups.Count -eq 0) {
        throw "Could not resolve target groups for ALB $loadBalancerArn."
    }

    return @{
        LoadBalancerArnSuffix = ($loadBalancerArn -split "loadbalancer/")[1]
        TargetGroupArnSuffix  = ($targetGroups[0].TargetGroupArn -split "targetgroup/")[1]
    }
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$resolvedTerraformDir = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $TerraformDir
$resolvedPlatformValuesFile = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $PlatformValuesFile
$resolvedBackendValuesFile = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $BackendValuesFile
$resolvedTerraformVarsFile = if ([System.IO.Path]::IsPathRooted($TerraformVarsFile)) {
    $TerraformVarsFile
}
else {
    Join-Path $resolvedTerraformDir $TerraformVarsFile
}

Assert-Command -Name "terraform"

if (-not $SkipTerraform -or -not $SkipParameterSync -or -not $SkipAddons -or -not $SkipFrontendDeploy -or $SyncApiEdge) {
    Assert-Command -Name "aws"
}

if (-not $SkipAddons -or -not $SkipBackendDeploy -or $SyncApiEdge) {
    Assert-Command -Name "kubectl"
    Assert-Command -Name "helm"
}

if (-not $SkipTerraform) {
    $terraformInitArgs = @("-chdir=$resolvedTerraformDir", "init")
    if ($BackendConfigFile) {
        $resolvedBackendConfigFile = Resolve-RepoPath -RepoRoot $repoRoot -PathValue $BackendConfigFile
        $terraformInitArgs += "-backend-config=$resolvedBackendConfigFile"
    }

    Invoke-External -FilePath "terraform" -Arguments $terraformInitArgs

    if ($DryRun) {
        Invoke-External -FilePath "terraform" -Arguments @(
            "-chdir=$resolvedTerraformDir",
            "plan",
            "-var-file=$resolvedTerraformVarsFile"
        )
        return
    }

    Invoke-External -FilePath "terraform" -Arguments @(
        "-chdir=$resolvedTerraformDir",
        "apply",
        "-var-file=$resolvedTerraformVarsFile"
    )
}

$terraformOutputs = Get-TerraformOutputs -TerraformDirectory $resolvedTerraformDir
$clusterName = Get-OutputValue -Outputs $terraformOutputs -Name "cluster_name"
$awsRegion = Get-OutputValue -Outputs $terraformOutputs -Name "aws_region"
$vpcId = Get-OutputValue -Outputs $terraformOutputs -Name "vpc_id"
$frontendBucketName = Get-OutputValue -Outputs $terraformOutputs -Name "frontend_bucket_name"
$frontendDistributionId = Get-OutputValue -Outputs $terraformOutputs -Name "frontend_distribution_id"
$predictionArtifactsBucketName = Get-OutputValue -Outputs $terraformOutputs -Name "prediction_artifacts_bucket_name"
$apiWafAclArn = Get-OutputValue -Outputs $terraformOutputs -Name "api_waf_acl_arn"
$ecrRepositoryUrls = Get-OutputValue -Outputs $terraformOutputs -Name "ecr_repository_urls"
$addonRoleArns = Get-OutputValue -Outputs $terraformOutputs -Name "cluster_addon_role_arns"
$appRoleArns = Get-OutputValue -Outputs $terraformOutputs -Name "app_workload_role_arns"
$expectedParameterStorePaths = Get-OutputValue -Outputs $terraformOutputs -Name "expected_parameter_store_paths"

if (-not $ApiImageRepository) {
    $ApiImageRepository = $ecrRepositoryUrls.api
}

if (-not $WorkerImageRepository) {
    $WorkerImageRepository = $ApiImageRepository
}

if (-not $WorkerImageTag) {
    $WorkerImageTag = $ApiImageTag
}

if (-not $SkipParameterSync) {
    $resolvedParameterManifestFile = if ($ParameterManifestFile) {
        Resolve-RepoPath -RepoRoot $repoRoot -PathValue $ParameterManifestFile
    }
    else {
        ""
    }
    $manifestParameters = Get-ParameterManifest -PathValue $resolvedParameterManifestFile
    $prefix = "/$ProjectName/$Environment"
    $derivedParameters = @(
        [pscustomobject]@{ name = "$prefix/api/REDIS_HOST"; type = "String"; value = (Get-OutputValue -Outputs $terraformOutputs -Name "redis").primary_endpoint },
        [pscustomobject]@{ name = "$prefix/api/REDIS_PORT"; type = "String"; value = [string](Get-OutputValue -Outputs $terraformOutputs -Name "redis").port },
        [pscustomobject]@{ name = "$prefix/api/REDIS_SSL"; type = "String"; value = "true" },
        [pscustomobject]@{ name = "$prefix/api/AWS_REGION"; type = "String"; value = $awsRegion },
        [pscustomobject]@{ name = "$prefix/api/SQS_QUEUE_URL"; type = "String"; value = (Get-OutputValue -Outputs $terraformOutputs -Name "worker_queue_url") },
        [pscustomobject]@{ name = "$prefix/api/S3_BUCKET_NAME"; type = "String"; value = $predictionArtifactsBucketName },
        [pscustomobject]@{ name = "$prefix/worker/AWS_REGION"; type = "String"; value = $awsRegion },
        [pscustomobject]@{ name = "$prefix/worker/SQS_QUEUE_URL"; type = "String"; value = (Get-OutputValue -Outputs $terraformOutputs -Name "worker_queue_url") }
    )
    $mergedParameters = Merge-Parameters -Derived $derivedParameters -Manifest $manifestParameters

    $requiredParameterNames = @()
    $requiredParameterNames += @($expectedParameterStorePaths.api)
    $requiredParameterNames += @($expectedParameterStorePaths.worker)
    if ($EnableModelService) {
        $requiredParameterNames += @($expectedParameterStorePaths.model_service)
    }

    $missingParameters = $requiredParameterNames | Where-Object {
        $_ -notin $mergedParameters.name
    }
    if ($missingParameters.Count -gt 0) {
        throw "Missing Parameter Store values: $($missingParameters -join ', '). Supply them in -ParameterManifestFile."
    }

    Sync-SsmParameters -Parameters $mergedParameters
}

Invoke-External -FilePath "aws" -Arguments @("eks", "update-kubeconfig", "--region", $awsRegion, "--name", $clusterName)

if (-not $SkipAddons) {
    $addonArgs = @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "infra/scripts/install-cluster-addons.ps1"),
        "-ClusterName",
        $clusterName,
        "-VpcId",
        $vpcId,
        "-LoadBalancerControllerRoleArn",
        $addonRoleArns.aws_load_balancer_controller,
        "-ExternalSecretsRoleArn",
        $addonRoleArns.external_secrets,
        "-FluentBitRoleArn",
        $addonRoleArns.fluent_bit,
        "-PlatformValuesFile",
        $resolvedPlatformValuesFile
    )
    if ($DryRun) {
        $addonArgs += "-DryRun"
    }

    Invoke-External -FilePath "powershell" -Arguments $addonArgs
}

if ($BuildApiImage -or $PushApiImage) {
    Assert-Command -Name "docker"
    if ($PushApiImage) {
        Invoke-External -FilePath "powershell" -Arguments @(
            "-Command",
            "aws ecr get-login-password --region '$awsRegion' | docker login --username AWS --password-stdin '$($ApiImageRepository.Split('/')[0])'"
        )
    }

    if ($BuildApiImage -or $PushApiImage) {
        Invoke-External -FilePath "docker" -Arguments @("build", "-t", "$ApiImageRepository`:$ApiImageTag", (Join-Path $repoRoot "apps/api"))
    }

    if ($PushApiImage) {
        Invoke-External -FilePath "docker" -Arguments @("push", "$ApiImageRepository`:$ApiImageTag")
    }
}

if (-not $SkipBackendDeploy) {
    $deployArgs = @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "infra/scripts/deploy-prod.ps1"),
        "-ReleaseName",
        $ReleaseName,
        "-Namespace",
        $Namespace,
        "-ValuesFile",
        $resolvedBackendValuesFile,
        "-ApiImageRepository",
        $ApiImageRepository,
        "-ApiImageTag",
        $ApiImageTag,
        "-WorkerImageRepository",
        $WorkerImageRepository,
        "-WorkerImageTag",
        $WorkerImageTag,
        "-ApiServiceAccountRoleArn",
        $appRoleArns.api,
        "-WorkerServiceAccountRoleArn",
        $appRoleArns.worker
    )

    if ($apiWafAclArn) {
        $deployArgs += @(
            "-ApiWafAclArn",
            $apiWafAclArn
        )
    }

    if ($EnableModelService) {
        $deployArgs += @(
            "-EnableModelService",
            "-ModelServiceImageRepository",
            $ModelServiceImageRepository,
            "-ModelServiceImageTag",
            $ModelServiceImageTag
        )
    }

    if ($DryRun) {
        $deployArgs += "-DryRun"
    }

    Invoke-External -FilePath "powershell" -Arguments $deployArgs
}

if ($SyncApiEdge -and -not $DryRun) {
    $apiIngressName = "$ReleaseName-backend-stack-api"
    $apiHostname = Wait-ForIngressHostname -IngressName $apiIngressName -Namespace $Namespace
    $apiAlbState = Get-ApiAlbState -DnsName $apiHostname

    Invoke-External -FilePath "terraform" -Arguments @(
        "-chdir=$resolvedTerraformDir",
        "apply",
        "-var-file=$resolvedTerraformVarsFile",
        "-var=api_dns_name=$apiHostname",
        "-var=api_alb_arn_suffix=$($apiAlbState.LoadBalancerArnSuffix)",
        "-var=api_target_group_arn_suffix=$($apiAlbState.TargetGroupArnSuffix)"
    )
}

if (-not $SkipFrontendDeploy) {
    Assert-Command -Name "bun"
    $resolvedPublicApiBaseUrl = if ($PublicApiBaseUrl) {
        $PublicApiBaseUrl
    }
    else {
        throw "PublicApiBaseUrl is required when frontend deploy is enabled."
    }

    if ($BuildFrontend) {
        $originalLocation = Get-Location
        try {
            Set-Location $repoRoot
            Invoke-External -FilePath "bun" -Arguments @("install", "--frozen-lockfile")
        }
        finally {
            Set-Location $originalLocation
        }
    }

    $originalLocation = Get-Location
    try {
        Set-Location (Join-Path $repoRoot "apps/astro-web")
        $env:PUBLIC_API_BASE_URL = $resolvedPublicApiBaseUrl
        Invoke-External -FilePath "bun" -Arguments @("run", "build")
    }
    finally {
        Set-Location $originalLocation
    }

    if (-not $DryRun) {
        Invoke-External -FilePath "aws" -Arguments @("s3", "sync", (Join-Path $repoRoot "apps/astro-web/dist"), "s3://$frontendBucketName", "--delete")
        Invoke-External -FilePath "aws" -Arguments @("cloudfront", "create-invalidation", "--distribution-id", $frontendDistributionId, "--paths", "/*")
    }
}
