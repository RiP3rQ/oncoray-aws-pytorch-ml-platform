Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([Parameter(Mandatory = $true)][string]$Message)

    $script:failures.Add($Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Add-Pass {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Host "PASS: $Message" -ForegroundColor Green
}

function Get-EnvExampleKeys {
    param([Parameter(Mandatory = $true)][string]$Path)

    $keys = [System.Collections.Generic.HashSet[string]]::new()
    Get-Content -LiteralPath $Path | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
            $null = $keys.Add($matches[1])
        }
    }

    return $keys
}

function Get-BackendHelmEnvKeys {
    param([Parameter(Mandatory = $true)][string]$Path)

    $keys = [System.Collections.Generic.HashSet[string]]::new()
    Select-String -Path $Path -Pattern '^\s{6}([A-Z][A-Z0-9_]+):' | ForEach-Object {
        $null = $_.Line -match '^\s{6}([A-Z][A-Z0-9_]+):'
        $null = $keys.Add($matches[1])
    }

    return $keys
}

function Get-SsmKeys {
    param([Parameter(Mandatory = $true)][string]$Path)

    $keys = [System.Collections.Generic.HashSet[string]]::new()
    $parameters = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    foreach ($parameter in @($parameters)) {
        $leaf = [System.IO.Path]::GetFileName([string]$parameter.name)
        $null = $keys.Add($leaf)
    }

    return $keys
}

function Assert-Covered {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][System.Collections.Generic.HashSet[string]]$ExampleKeys,
        [Parameter(Mandatory = $true)][System.Collections.Generic.HashSet[string]]$CoveredKeys,
        [string[]]$AllowedMissing = @()
    )

    $missing = @(
        $ExampleKeys |
            Where-Object { -not $CoveredKeys.Contains($_) -and $_ -notin $AllowedMissing } |
            Sort-Object
    )

    if ($missing.Count -gt 0) {
        Add-Failure "$Label missing production coverage for: $($missing -join ', ')"
        return
    }

    Add-Pass "$Label env example keys covered by production infra"
}

$apiExample = Get-EnvExampleKeys -Path (Join-Path $repoRoot "apps/api/.env.example")
$webExample = Get-EnvExampleKeys -Path (Join-Path $repoRoot "apps/astro-web/.env.example")
$modelServiceExample = Get-EnvExampleKeys -Path (Join-Path $repoRoot "apps/model-service/.env.example")
$pytorchEngineExample = Get-EnvExampleKeys -Path (Join-Path $repoRoot "apps/pytorch-engine/.env.example")

$helmKeys = Get-BackendHelmEnvKeys -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.yaml")
$ssmKeys = Get-SsmKeys -Path (Join-Path $repoRoot "infra/helm/values/ssm-parameters.prod.example.json")
$localSsmPath = Join-Path $repoRoot "infra/helm/values/ssm-parameters.prod.json"
if (Test-Path -LiteralPath $localSsmPath) {
    $localSsmKeys = Get-SsmKeys -Path $localSsmPath
    $missingLocalSsmKeys = @($ssmKeys | Where-Object { -not $localSsmKeys.Contains($_) } | Sort-Object)
    if ($missingLocalSsmKeys.Count -gt 0) {
        Add-Failure "Local ssm-parameters.prod.json missing keys from example: $($missingLocalSsmKeys -join ', ')"
    }
    else {
        Add-Pass "Local ssm-parameters.prod.json includes every tracked SSM key"
    }
}

$coveredBackendKeys = [System.Collections.Generic.HashSet[string]]::new()
foreach ($key in $helmKeys) {
    $null = $coveredBackendKeys.Add($key)
}
foreach ($key in $ssmKeys) {
    $null = $coveredBackendKeys.Add($key)
}

Assert-Covered `
    -Label "API" `
    -ExampleKeys $apiExample `
    -CoveredKeys $coveredBackendKeys `
    -AllowedMissing @(
        "POSTGRES_SERVER",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY"
    )

Assert-Covered `
    -Label "Model Runtime Host" `
    -ExampleKeys $modelServiceExample `
    -CoveredKeys $coveredBackendKeys

$frontendRequired = @(
    "PUBLIC_API_BASE_URL",
    "PUBLIC_SENTRY_DSN",
    "PUBLIC_APP_ENVIRONMENT",
    "PUBLIC_APP_RELEASE",
    "PUBLIC_SENTRY_TRACES_SAMPLE_RATE",
    "SENTRY_AUTH_TOKEN",
    "SENTRY_ORG",
    "SENTRY_PROJECT"
)
$docsContent = Get-Content -LiteralPath (Join-Path $repoRoot "docs/DEPLOYMENT_RUNBOOK.md") -Raw
$missingFrontendDocs = @($frontendRequired | Where-Object { $webExample.Contains($_) -and $docsContent -notmatch [regex]::Escape($_) })
if ($missingFrontendDocs.Count -gt 0) {
    Add-Failure "Frontend build env missing deploy-doc coverage for: $($missingFrontendDocs -join ', ')"
}
else {
    Add-Pass "Frontend env example keys covered by deploy docs"
}

Assert-Covered `
    -Label "PyTorch Engine" `
    -ExampleKeys $pytorchEngineExample `
    -CoveredKeys $coveredBackendKeys `
    -AllowedMissing @("HF_USERNAME", "HF_TOKEN")

Write-Host ""
Write-Host "Env parity validation summary: $($failures.Count) failure(s)."

if ($failures.Count -gt 0) {
    exit 1
}

exit 0
