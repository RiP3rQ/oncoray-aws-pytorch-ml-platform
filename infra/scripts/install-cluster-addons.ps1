param(
    [Parameter(Mandatory = $true)]
    [string]$ClusterName,
    [Parameter(Mandatory = $true)]
    [string]$VpcId,
    [Parameter(Mandatory = $true)]
    [string]$LoadBalancerControllerRoleArn,
    [Parameter(Mandatory = $true)]
    [string]$ExternalSecretsRoleArn,
    [Parameter(Mandatory = $true)]
    [string]$FluentBitRoleArn,
    [string]$AwsRegion = "eu-central-1",
    [string]$PlatformValuesFile = "infra/helm/values/addons.yaml",
    [string]$AwsLoadBalancerControllerChartVersion = "1.14.1",
    [string]$ExternalSecretsChartVersion = "1.3.1",
    [string]$KedaChartVersion = "2.18.1",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $wingetPackageRoot = Join-Path $env:LOCALAPPDATA "Microsoft/WinGet/Packages"
    if (Test-Path -LiteralPath $wingetPackageRoot) {
        $candidate = Get-ChildItem -Path $wingetPackageRoot -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    return ""
}

$helmCommand = Resolve-ToolPath -Name "helm"
if (-not $helmCommand) {
    throw "helm not found. Install helm before using install-cluster-addons.ps1."
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$platformChartPath = Join-Path $repoRoot "infra/helm/charts/platform-addons"
$resolvedPlatformValuesFile = if ([System.IO.Path]::IsPathRooted($PlatformValuesFile)) {
    $PlatformValuesFile
}
else {
    Join-Path $repoRoot $PlatformValuesFile
}

if (-not (Test-Path -LiteralPath $resolvedPlatformValuesFile)) {
    throw "Platform values file not found: $resolvedPlatformValuesFile"
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$QuietOutput
    )

    if ($QuietOutput) {
        & $FilePath @Arguments | Out-Null
    }
    else {
        & $FilePath @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

Invoke-External -FilePath $helmCommand -Arguments @("repo", "add", "eks", "https://aws.github.io/eks-charts", "--force-update") -QuietOutput
Invoke-External -FilePath $helmCommand -Arguments @("repo", "add", "external-secrets", "https://charts.external-secrets.io", "--force-update") -QuietOutput
Invoke-External -FilePath $helmCommand -Arguments @("repo", "add", "kedacore", "https://kedacore.github.io/charts", "--force-update") -QuietOutput
Invoke-External -FilePath $helmCommand -Arguments @("repo", "update") -QuietOutput

$commonDryRunArgs = @()
if ($DryRun) {
    $commonDryRunArgs = @("--dry-run=client", "--debug")
}

$loadBalancerArgs = @(
    "upgrade",
    "--install",
    "aws-load-balancer-controller",
    "eks/aws-load-balancer-controller",
    "--namespace",
    "kube-system",
    "--version",
    $AwsLoadBalancerControllerChartVersion,
    "--set",
    "clusterName=$ClusterName",
    "--set",
    "region=$AwsRegion",
    "--set",
    "vpcId=$VpcId",
    "--set",
    "serviceAccount.create=true",
    "--set",
    "serviceAccount.name=aws-load-balancer-controller",
    "--set-string",
    "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=$LoadBalancerControllerRoleArn"
) + $commonDryRunArgs

$externalSecretsArgs = @(
    "upgrade",
    "--install",
    "external-secrets",
    "external-secrets/external-secrets",
    "--namespace",
    "external-secrets",
    "--create-namespace",
    "--version",
    $ExternalSecretsChartVersion,
    "--set",
    "installCRDs=true",
    "--set",
    "serviceAccount.create=true",
    "--set",
    "serviceAccount.name=external-secrets",
    "--set-string",
    "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=$ExternalSecretsRoleArn"
) + $commonDryRunArgs

$platformArgs = @(
    "upgrade",
    "--install",
    "platform-addons",
    $platformChartPath,
    "--namespace",
    "amazon-cloudwatch",
    "--create-namespace",
    "-f",
    $resolvedPlatformValuesFile,
    "--set",
    "global.clusterName=$ClusterName",
    "--set",
    "global.awsRegion=$AwsRegion",
    "--set",
    "externalSecrets.serviceAccount.name=external-secrets",
    "--set",
    "externalSecrets.serviceAccount.namespace=external-secrets",
    "--set-string",
    "fluentBit.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=$FluentBitRoleArn"
) + $commonDryRunArgs

$kedaArgs = @(
    "upgrade",
    "--install",
    "keda",
    "kedacore/keda",
    "--namespace",
    "keda",
    "--create-namespace",
    "--version",
    $KedaChartVersion
) + $commonDryRunArgs

Write-Host "Installing AWS Load Balancer Controller"
Invoke-External -FilePath $helmCommand -Arguments $loadBalancerArgs

Write-Host "Installing External Secrets Operator"
Invoke-External -FilePath $helmCommand -Arguments $externalSecretsArgs

Write-Host "Installing KEDA"
Invoke-External -FilePath $helmCommand -Arguments $kedaArgs

Write-Host "Installing platform add-on config and Fluent Bit"
Invoke-External -FilePath $helmCommand -Arguments $platformArgs
