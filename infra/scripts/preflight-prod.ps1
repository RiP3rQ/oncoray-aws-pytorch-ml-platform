param(
    [string]$TerraformDir = "infra/terraform/environments/prod",
    [string]$TerraformVarsFile = "terraform.tfvars",
    [string]$BackendValuesFile = "infra/helm/values/prod.yaml",
    [string]$AddonsValuesFile = "infra/helm/values/addons.yaml",
    [ValidateSet("DnsBootstrap", "FullDeploy")]
    [string]$Phase = "FullDeploy",
    [switch]$RequireAwsIdentity
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return ""
}

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $repoRoot $Path
}

function Assert-Tool {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Resolve-ToolPath -Name $Name)) {
        throw "$Name not found in PATH."
    }
}

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required production file missing: $Path"
    }
}

function Assert-NoPlaceholder {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Patterns
    )

    $content = Get-Content -LiteralPath $Path -Raw
    foreach ($pattern in $Patterns) {
        if ($content -like "*$pattern*") {
            throw "Production file contains unresolved placeholder '$pattern': $Path"
        }
    }
}

function Get-TerraformStringValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $content = Get-Content -LiteralPath $Path -Raw
    $match = [regex]::Match($content, "(?m)^\s*$Name\s*=\s*""([^""]+)""\s*$")
    if (-not $match.Success) {
        return ""
    }

    return $match.Groups[1].Value
}

function Get-TerraformBooleanValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $content = Get-Content -LiteralPath $Path -Raw
    $match = [regex]::Match($content, "(?m)^\s*$Name\s*=\s*(true|false)\s*$")
    if (-not $match.Success) {
        return $false
    }

    return $match.Groups[1].Value -eq "true"
}

function Assert-NoLocalstackStateReuse {
    param(
        [Parameter(Mandatory = $true)][string]$TerraformDir,
        [Parameter(Mandatory = $true)][string]$TerraformVarsFile
    )

    if (Get-TerraformBooleanValue -Path $TerraformVarsFile -Name "use_localstack") {
        return
    }

    $statePath = Join-Path $TerraformDir "terraform.tfstate"
    if (-not (Test-Path -LiteralPath $statePath)) {
        return
    }

    $stateContent = Get-Content -LiteralPath $statePath -Raw
    $localstackMarkers = @(
        "localhost.localstack.cloud",
        "000000000000",
        "pytorch-model-local"
    )

    foreach ($marker in $localstackMarkers) {
        if ($stateContent -like "*$marker*") {
            throw "Refusing production preflight: $statePath contains LocalStack marker '$marker'. Reinitialize prod with a clean/remote backend before planning or applying real AWS."
        }
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Label
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed."
    }
    Write-Host "PASS: $Label"
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$resolvedTerraformDir = Resolve-RepoPath -Path $TerraformDir
$resolvedTerraformVarsFile = if ([System.IO.Path]::IsPathRooted($TerraformVarsFile)) {
    $TerraformVarsFile
}
else {
    Join-Path $resolvedTerraformDir $TerraformVarsFile
}
$resolvedBackendValuesFile = Resolve-RepoPath -Path $BackendValuesFile
$resolvedAddonsValuesFile = Resolve-RepoPath -Path $AddonsValuesFile

Assert-Tool -Name "terraform"
Assert-Tool -Name "aws"
if ($Phase -eq "FullDeploy") {
    Assert-Tool -Name "helm"
    Assert-Tool -Name "kubectl"
    Assert-Tool -Name "docker"
    Assert-Tool -Name "bun"
}

Assert-FileExists -Path $resolvedTerraformVarsFile
if ($Phase -eq "FullDeploy") {
    Assert-FileExists -Path $resolvedBackendValuesFile
    Assert-FileExists -Path $resolvedAddonsValuesFile
}

$placeholderPatterns = @(
    "REPLACE_ME",
    "replace-me",
    "example.com",
    "123456789012",
    "203.0.113.",
    "Z1234567890EXAMPLE"
)

Assert-NoPlaceholder -Path $resolvedTerraformVarsFile -Patterns $placeholderPatterns
if ($Phase -eq "FullDeploy") {
    Assert-NoPlaceholder -Path $resolvedBackendValuesFile -Patterns $placeholderPatterns
    Assert-NoPlaceholder -Path $resolvedAddonsValuesFile -Patterns $placeholderPatterns
}
Assert-NoLocalstackStateReuse -TerraformDir $resolvedTerraformDir -TerraformVarsFile $resolvedTerraformVarsFile

Invoke-Checked -FilePath "terraform" -Arguments @("-chdir=$resolvedTerraformDir", "fmt", "-check") -Label "terraform fmt"
Invoke-Checked -FilePath "terraform" -Arguments @("-chdir=$resolvedTerraformDir", "validate") -Label "terraform validate"
if ($Phase -eq "FullDeploy") {
    Invoke-Checked -FilePath "helm" -Arguments @("lint", (Join-Path $repoRoot "infra/helm/charts/backend-stack"), "-f", $resolvedBackendValuesFile) -Label "helm lint backend-stack"
    Invoke-Checked -FilePath "helm" -Arguments @("template", "pytorch-model", (Join-Path $repoRoot "infra/helm/charts/backend-stack"), "-f", $resolvedBackendValuesFile) -Label "helm template backend-stack"
    Invoke-Checked -FilePath "helm" -Arguments @("lint", (Join-Path $repoRoot "infra/helm/charts/platform-addons"), "-f", $resolvedAddonsValuesFile) -Label "helm lint platform-addons"
    Invoke-Checked -FilePath "helm" -Arguments @("template", "platform-addons", (Join-Path $repoRoot "infra/helm/charts/platform-addons"), "-f", $resolvedAddonsValuesFile) -Label "helm template platform-addons"
}

if ($RequireAwsIdentity) {
    $awsRegion = Get-TerraformStringValue -Path $resolvedTerraformVarsFile -Name "aws_region"
    $expectedAccountId = Get-TerraformStringValue -Path $resolvedTerraformVarsFile -Name "expected_aws_account_id"
    if (-not $expectedAccountId) {
        throw "expected_aws_account_id must be set in $resolvedTerraformVarsFile when -RequireAwsIdentity is used."
    }
    $expectedPrincipalArn = Get-TerraformStringValue -Path $resolvedTerraformVarsFile -Name "expected_aws_principal_arn"
    if (-not $expectedPrincipalArn) {
        throw "expected_aws_principal_arn must be set in $resolvedTerraformVarsFile when -RequireAwsIdentity is used."
    }

    $awsArgs = @("sts", "get-caller-identity")
    if ($awsRegion) {
        $awsArgs += @("--region", $awsRegion)
    }

    $identityOutput = & aws @awsArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        $message = ($identityOutput | Out-String).Trim()
        throw "aws sts get-caller-identity failed. $message"
    }

    $identity = $identityOutput | ConvertFrom-Json
    if ($identity.Account -ne $expectedAccountId) {
        throw "AWS caller account mismatch. Expected $expectedAccountId but got $($identity.Account) from $($identity.Arn)."
    }
    if ($identity.Arn -ne $expectedPrincipalArn) {
        throw "AWS caller ARN mismatch. Expected $expectedPrincipalArn but got $($identity.Arn)."
    }

    Write-Host "PASS: aws sts get-caller-identity matched expected account and principal"
}

Write-Host "Production preflight completed."
