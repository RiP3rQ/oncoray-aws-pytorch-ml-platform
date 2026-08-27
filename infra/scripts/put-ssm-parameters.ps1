param(
    [string]$ParameterFile = "infra/helm/values/ssm-parameters.prod.json",
    [string]$ExpectedAccountId = $env:PYTORCH_MODEL_EXPECTED_AWS_ACCOUNT_ID,
    [string]$ExpectedPrincipalArn = $env:PYTORCH_MODEL_EXPECTED_AWS_PRINCIPAL_ARN,
    [string]$Region = "eu-central-1",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $repoRoot $Path
}

function Assert-Tool {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found in PATH."
    }
}

function Assert-NoUnsafeValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowEmptyString()][string]$Value
    )

    $forbidden = @(
        "REPLACE_ME",
        "replace-me",
        "example.com",
        "123456789012"
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "SSM parameter has empty value: $Name"
    }

    foreach ($pattern in $forbidden) {
        if ($Value -like "*$pattern*") {
            throw "SSM parameter contains unsafe placeholder '$pattern': $Name"
        }
    }
}

function Invoke-AwsJson {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & aws @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $message = ($output | Out-String).Trim()
        throw "aws $($Arguments -join ' ') failed. $message"
    }

    return $output | ConvertFrom-Json
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$resolvedParameterFile = Resolve-RepoPath -Path $ParameterFile

Assert-Tool -Name "aws"

if (-not (Test-Path -LiteralPath $resolvedParameterFile)) {
    throw "Parameter file not found: $resolvedParameterFile"
}

$identity = Invoke-AwsJson -Arguments @("sts", "get-caller-identity", "--region", $Region)
if ([string]::IsNullOrWhiteSpace($ExpectedAccountId)) {
    throw "ExpectedAccountId is required. Pass -ExpectedAccountId or set PYTORCH_MODEL_EXPECTED_AWS_ACCOUNT_ID."
}
if ([string]::IsNullOrWhiteSpace($ExpectedPrincipalArn)) {
    throw "ExpectedPrincipalArn is required. Pass -ExpectedPrincipalArn or set PYTORCH_MODEL_EXPECTED_AWS_PRINCIPAL_ARN."
}
if ($identity.Account -ne $ExpectedAccountId) {
    throw "AWS caller account mismatch. Expected $ExpectedAccountId but got $($identity.Account)."
}
if ($identity.Arn -ne $ExpectedPrincipalArn) {
    throw "AWS caller ARN mismatch. Expected $ExpectedPrincipalArn but got $($identity.Arn)."
}

$parameters = Get-Content -LiteralPath $resolvedParameterFile -Raw | ConvertFrom-Json
$requiredFields = @("name", "type", "value")

foreach ($parameter in @($parameters)) {
    foreach ($field in $requiredFields) {
        if (-not $parameter.PSObject.Properties.Name.Contains($field)) {
            throw "SSM parameter entry missing '$field'."
        }
    }

    if ($parameter.name -notlike "/pytorch-model/prod/*") {
        throw "SSM parameter path must stay under /pytorch-model/prod/: $($parameter.name)"
    }
    if ($parameter.type -notin @("String", "SecureString")) {
        throw "Unsupported SSM parameter type for $($parameter.name): $($parameter.type)"
    }

    Assert-NoUnsafeValue -Name $parameter.name -Value ([string]$parameter.value)
}

foreach ($parameter in @($parameters)) {
    if ($DryRun) {
        Write-Host "DRY RUN: $($parameter.type) $($parameter.name)"
        continue
    }

    & aws ssm put-parameter `
        --region $Region `
        --name $parameter.name `
        --type $parameter.type `
        --value ([string]$parameter.value) `
        --overwrite | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to put SSM parameter: $($parameter.name)"
    }

    Write-Host "PUT: $($parameter.name)"
}

Write-Host "SSM Parameter Store upload completed."
