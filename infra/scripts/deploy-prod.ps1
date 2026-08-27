param(
    [string]$ReleaseName = "pytorch-model",
    [string]$Namespace = "pytorch-model-prod",
    [string]$ValuesFile = "infra/helm/values/prod.yaml",
    [string]$ApiImageRepository = "",
    [string]$ApiImageTag = "",
    [string]$ApiServiceAccountRoleArn = "",
    [string]$ApiWafAclArn = "",
    [string]$ModelServiceServiceAccountRoleArn = "",
    [string]$ModelServiceImageRepository = "",
    [string]$ModelServiceImageTag = "",
    [string]$ModelServiceUrl = "",
    [switch]$EnableModelService,
    [switch]$Force,
    [string]$Timeout = "10m",
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

function Test-ProductionValuesFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fileName = [System.IO.Path]::GetFileName($Path)
    if ($fileName -ne "prod.yaml") {
        return
    }

    $content = Get-Content -LiteralPath $Path -Raw
    $forbiddenPatterns = @(
        "REPLACE_ME",
        "replace-me",
        "example.com",
        "123456789012"
    )

    foreach ($pattern in $forbiddenPatterns) {
        if ($content -like "*$pattern*") {
            throw "Production Helm values file contains unresolved placeholder '$pattern': $Path"
        }
    }
}

$helmCommand = Resolve-ToolPath -Name "helm"
if (-not $helmCommand) {
    throw "helm not found. Install helm before using deploy-prod.ps1."
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$chartPath = Join-Path $repoRoot "infra/helm/charts/backend-stack"
$resolvedValuesFile = if ([System.IO.Path]::IsPathRooted($ValuesFile)) {
    $ValuesFile
}
else {
    Join-Path $repoRoot $ValuesFile
}

if (-not (Test-Path -LiteralPath $resolvedValuesFile)) {
    throw "Values file not found: $resolvedValuesFile"
}
Test-ProductionValuesFile -Path $resolvedValuesFile

if (-not $ApiImageRepository) {
    throw "ApiImageRepository required."
}
if (-not $ApiImageTag) {
    throw "ApiImageTag required."
}
if ($ApiImageTag -eq "latest" -or $ApiImageTag -like "*REPLACE_ME*") {
    throw "ApiImageTag must be an immutable real tag, not latest or a placeholder."
}

if ($DryRun) {
    $helmArgs = @(
        "template",
        $ReleaseName,
        $chartPath,
        "--namespace",
        $Namespace,
        "-f",
        $resolvedValuesFile
    )
}
else {
    $helmArgs = @(
        "upgrade",
        "--install",
        $ReleaseName,
        $chartPath,
        "--namespace",
        $Namespace,
        "--create-namespace",
        "-f",
        $resolvedValuesFile,
        "--wait",
        "--wait-for-jobs",
        "--timeout",
        $Timeout
    )

    if ($Force) {
        $helmArgs += "--force"
    }
}

$helmArgs += @(
    "--set",
    "workloads.api.image.repository=$ApiImageRepository",
    "--set",
    "workloads.api.image.tag=$ApiImageTag",
    "--set",
    "migrations.image.repository=$ApiImageRepository",
    "--set",
    "migrations.image.tag=$ApiImageTag",
    "--set",
    "migrations.enabled=true"
)

if ($ApiServiceAccountRoleArn) {
    $helmArgs += @(
        "--set-string",
        "workloads.api.serviceAccount.annotations.eks\.amazonaws\.com/role-arn=$ApiServiceAccountRoleArn"
    )
}

if ($ApiWafAclArn) {
    $helmArgs += @(
        "--set-string",
        "workloads.api.ingress.annotations.alb\.ingress\.kubernetes\.io/wafv2-acl-arn=$ApiWafAclArn"
    )
}

if ($EnableModelService) {
    if (-not $ModelServiceImageRepository) {
        throw "ModelServiceImageRepository required when -EnableModelService is set."
    }
    if (-not $ModelServiceImageTag) {
        throw "ModelServiceImageTag required when -EnableModelService is set."
    }
    if ($ModelServiceImageTag -eq "latest" -or $ModelServiceImageTag -like "*REPLACE_ME*") {
        throw "ModelServiceImageTag must be an immutable real tag, not latest or a placeholder."
    }
    if (-not $ModelServiceUrl) {
        $ModelServiceUrl = "http://$ReleaseName-backend-stack-model-runtime-host:8001"
    }

    $helmArgs += @(
        "--set",
        "workloads.model-runtime-host.enabled=true",
        "--set",
        "workloads.model-runtime-host.image.repository=$ModelServiceImageRepository",
        "--set",
        "workloads.model-runtime-host.image.tag=$ModelServiceImageTag",
        "--set-string",
        "workloads.api.env.MODEL_SERVICE_URL=$ModelServiceUrl"
    )

    if ($ModelServiceServiceAccountRoleArn) {
        $helmArgs += @(
            "--set-string",
            "workloads.model-runtime-host.serviceAccount.annotations.eks\.amazonaws\.com/role-arn=$ModelServiceServiceAccountRoleArn"
        )
    }
}

Write-Host "Running helm with values file: $resolvedValuesFile"
Write-Host "Release: $ReleaseName"
Write-Host "Namespace: $Namespace"

& $helmCommand @helmArgs
if ($LASTEXITCODE -ne 0) {
    throw "helm upgrade failed."
}
