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
    [switch]$BuildModelServiceImage,
    [switch]$PushModelServiceImage,
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

. (Join-Path $PSScriptRoot "production-deployment-contract.ps1")

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

function New-DerivedSsmParameters {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$ProductionDeploymentContract,
        [Parameter(Mandatory = $true)][string]$ParameterPrefix
    )

    return @(
        [pscustomobject]@{ name = "$ParameterPrefix/api/REDIS_HOST"; type = "String"; value = $ProductionDeploymentContract.redis.primaryEndpoint },
        [pscustomobject]@{ name = "$ParameterPrefix/api/REDIS_PORT"; type = "String"; value = [string]$ProductionDeploymentContract.redis.port },
        [pscustomobject]@{ name = "$ParameterPrefix/api/REDIS_SSL"; type = "String"; value = "true" },
        [pscustomobject]@{ name = "$ParameterPrefix/api/AWS_REGION"; type = "String"; value = $ProductionDeploymentContract.awsRegion },
        [pscustomobject]@{ name = "$ParameterPrefix/api/SQS_QUEUE_URL"; type = "String"; value = $ProductionDeploymentContract.workerQueueUrl },
        [pscustomobject]@{ name = "$ParameterPrefix/api/S3_BUCKET_NAME"; type = "String"; value = $ProductionDeploymentContract.predictionArtifactsBucketName },
        [pscustomobject]@{ name = "$ParameterPrefix/worker/AWS_REGION"; type = "String"; value = $ProductionDeploymentContract.awsRegion },
        [pscustomobject]@{ name = "$ParameterPrefix/worker/SQS_QUEUE_URL"; type = "String"; value = $ProductionDeploymentContract.workerQueueUrl }
    )
}

function Assert-RequiredSsmParameters {
    param(
        [Parameter(Mandatory = $true)][object[]]$Parameters,
        [Parameter(Mandatory = $true)][object]$ExpectedParameterStorePaths
    )

    $requiredParameterNames = @()
    $requiredParameterNames += @($ExpectedParameterStorePaths.api)
    $requiredParameterNames += @($ExpectedParameterStorePaths.worker)

    $missingParameters = $requiredParameterNames | Where-Object {
        $_ -notin $Parameters.name
    }
    if ($missingParameters.Count -gt 0) {
        throw "Missing Parameter Store values: $($missingParameters -join ', '). Supply them in -ParameterManifestFile."
    }
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

function Sync-ApiEdgeState {
    param(
        [Parameter(Mandatory = $true)][string]$ReleaseName,
        [Parameter(Mandatory = $true)][string]$Namespace,
        [Parameter(Mandatory = $true)][string]$TerraformDirectory,
        [Parameter(Mandatory = $true)][string]$TerraformVarsFile
    )

    $apiIngressName = "$ReleaseName-backend-stack-api"
    $apiHostname = Wait-ForIngressHostname -IngressName $apiIngressName -Namespace $Namespace
    $apiAlbState = Get-ApiAlbState -DnsName $apiHostname

    Invoke-External -FilePath "terraform" -Arguments @(
        "-chdir=$TerraformDirectory",
        "apply",
        "-var-file=$TerraformVarsFile",
        "-var=api_dns_name=$apiHostname",
        "-var=api_alb_arn_suffix=$($apiAlbState.LoadBalancerArnSuffix)",
        "-var=api_target_group_arn_suffix=$($apiAlbState.TargetGroupArnSuffix)"
    )
}

function New-AddonInstallArguments {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$ClusterName,
        [Parameter(Mandatory = $true)][string]$VpcId,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$ClusterAddonRoleArns,
        [Parameter(Mandatory = $true)][string]$PlatformValuesFile,
        [Parameter(Mandatory = $true)][bool]$DryRun
    )

    $arguments = @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $RepoRoot "infra/scripts/install-cluster-addons.ps1"),
        "-ClusterName",
        $ClusterName,
        "-VpcId",
        $VpcId,
        "-LoadBalancerControllerRoleArn",
        $ClusterAddonRoleArns.awsLoadBalancerController,
        "-ExternalSecretsRoleArn",
        $ClusterAddonRoleArns.externalSecrets,
        "-FluentBitRoleArn",
        $ClusterAddonRoleArns.fluentBit,
        "-PlatformValuesFile",
        $PlatformValuesFile
    )

    if ($DryRun) {
        $arguments += "-DryRun"
    }

    return $arguments
}

function New-BackendDeployArguments {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$ReleaseName,
        [Parameter(Mandatory = $true)][string]$Namespace,
        [Parameter(Mandatory = $true)][string]$BackendValuesFile,
        [Parameter(Mandatory = $true)][string]$ApiImageRepository,
        [Parameter(Mandatory = $true)][string]$ApiImageTag,
        [Parameter(Mandatory = $true)][string]$WorkerImageRepository,
        [Parameter(Mandatory = $true)][string]$WorkerImageTag,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$AppWorkloadRoleArns,
        [string]$ApiWafAclArn = "",
        [switch]$EnableModelService,
        [string]$ModelServiceImageRepository = "",
        [string]$ModelServiceImageTag = "",
        [switch]$DryRun
    )

    $arguments = @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $RepoRoot "infra/scripts/deploy-prod.ps1"),
        "-ReleaseName",
        $ReleaseName,
        "-Namespace",
        $Namespace,
        "-ValuesFile",
        $BackendValuesFile,
        "-ApiImageRepository",
        $ApiImageRepository,
        "-ApiImageTag",
        $ApiImageTag,
        "-WorkerImageRepository",
        $WorkerImageRepository,
        "-WorkerImageTag",
        $WorkerImageTag,
        "-ApiServiceAccountRoleArn",
        $AppWorkloadRoleArns.api,
        "-WorkerServiceAccountRoleArn",
        $AppWorkloadRoleArns.worker
    )

    if ($ApiWafAclArn) {
        $arguments += @("-ApiWafAclArn", $ApiWafAclArn)
    }

    if ($EnableModelService) {
        $arguments += @(
            "-EnableModelService",
            "-ModelServiceImageRepository",
            $ModelServiceImageRepository,
            "-ModelServiceImageTag",
            $ModelServiceImageTag
        )
    }

    if ($DryRun) {
        $arguments += "-DryRun"
    }

    return $arguments
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
$productionDeploymentContract = New-ProductionDeploymentContract `
    -TerraformOutputs $terraformOutputs `
    -ProjectName $ProjectName `
    -Environment $Environment `
    -Namespace $Namespace
$productionDeploymentContractPath = Save-ProductionDeploymentContract `
    -Contract $productionDeploymentContract `
    -RepoRoot $repoRoot
Write-Host "Production Deployment Contract: $productionDeploymentContractPath"

$clusterName = $productionDeploymentContract.clusterName
$awsRegion = $productionDeploymentContract.awsRegion
$vpcId = $productionDeploymentContract.vpcId
$frontendBucketName = $productionDeploymentContract.frontendBucketName
$frontendDistributionId = $productionDeploymentContract.frontendDistributionId
$predictionArtifactsBucketName = $productionDeploymentContract.predictionArtifactsBucketName
$apiWafAclArn = $productionDeploymentContract.apiWafAclArn
$ecrRepositoryUrls = $productionDeploymentContract.ecrRepositories
$addonRoleArns = $productionDeploymentContract.clusterAddonRoleArns
$appRoleArns = $productionDeploymentContract.appWorkloadRoleArns
$expectedParameterStorePaths = $productionDeploymentContract.expectedParameterStorePaths

if (-not $ApiImageRepository) {
    $ApiImageRepository = $ecrRepositoryUrls.api
}

if (-not $WorkerImageRepository) {
    $WorkerImageRepository = $ApiImageRepository
}

if (-not $WorkerImageTag) {
    $WorkerImageTag = $ApiImageTag
}

if ($EnableModelService -and -not $ModelServiceImageRepository) {
    $ModelServiceImageRepository = $ecrRepositoryUrls.modelService
}

if ($EnableModelService -and -not $ModelServiceImageTag) {
    $ModelServiceImageTag = $ApiImageTag
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
    $derivedParameters = New-DerivedSsmParameters `
        -ProductionDeploymentContract $productionDeploymentContract `
        -ParameterPrefix $prefix
    $mergedParameters = Merge-Parameters -Derived $derivedParameters -Manifest $manifestParameters
    Assert-RequiredSsmParameters `
        -Parameters $mergedParameters `
        -ExpectedParameterStorePaths $expectedParameterStorePaths

    Sync-SsmParameters -Parameters $mergedParameters
}

Invoke-External -FilePath "aws" -Arguments @("eks", "update-kubeconfig", "--region", $awsRegion, "--name", $clusterName)

if (-not $SkipAddons) {
    $addonArgs = New-AddonInstallArguments `
        -RepoRoot $repoRoot `
        -ClusterName $clusterName `
        -VpcId $vpcId `
        -ClusterAddonRoleArns $addonRoleArns `
        -PlatformValuesFile $resolvedPlatformValuesFile `
        -DryRun:$DryRun
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

if ($EnableModelService -and ($BuildModelServiceImage -or $PushModelServiceImage)) {
    Assert-Command -Name "docker"
    if (-not $ModelServiceImageRepository) {
        throw "ModelServiceImageRepository required when building or pushing model-service image."
    }
    if (-not $ModelServiceImageTag) {
        throw "ModelServiceImageTag required when building or pushing model-service image."
    }
    if ($PushModelServiceImage) {
        Invoke-External -FilePath "powershell" -Arguments @(
            "-Command",
            "aws ecr get-login-password --region '$awsRegion' | docker login --username AWS --password-stdin '$($ModelServiceImageRepository.Split('/')[0])'"
        )
    }

    Invoke-External -FilePath "docker" -Arguments @(
        "build",
        "-t",
        "$ModelServiceImageRepository`:$ModelServiceImageTag",
        (Join-Path $repoRoot "apps/model-service")
    )

    if ($PushModelServiceImage) {
        Invoke-External -FilePath "docker" -Arguments @("push", "$ModelServiceImageRepository`:$ModelServiceImageTag")
    }
}

if (-not $SkipBackendDeploy) {
    $deployArgs = New-BackendDeployArguments `
        -RepoRoot $repoRoot `
        -ReleaseName $ReleaseName `
        -Namespace $Namespace `
        -BackendValuesFile $resolvedBackendValuesFile `
        -ApiImageRepository $ApiImageRepository `
        -ApiImageTag $ApiImageTag `
        -WorkerImageRepository $WorkerImageRepository `
        -WorkerImageTag $WorkerImageTag `
        -AppWorkloadRoleArns $appRoleArns `
        -ApiWafAclArn $apiWafAclArn `
        -EnableModelService:$EnableModelService `
        -ModelServiceImageRepository $ModelServiceImageRepository `
        -ModelServiceImageTag $ModelServiceImageTag `
        -DryRun:$DryRun
    Invoke-External -FilePath "powershell" -Arguments $deployArgs
}

if ($SyncApiEdge -and -not $DryRun) {
    Sync-ApiEdgeState `
        -ReleaseName $ReleaseName `
        -Namespace $Namespace `
        -TerraformDirectory $resolvedTerraformDir `
        -TerraformVarsFile $resolvedTerraformVarsFile
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
