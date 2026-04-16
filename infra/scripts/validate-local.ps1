param(
    [switch]$CheckHelm,
    [switch]$RequireHelm,
    [switch]$CheckTerraformValidate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([Parameter(Mandatory = $true)][string]$Message)

    $script:failures.Add($Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Add-Warning {
    param([Parameter(Mandatory = $true)][string]$Message)

    $script:warnings.Add($Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Add-Pass {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Host "PASS: $Message" -ForegroundColor Green
}

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
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
        Add-Failure "$Label failed."
        return $false
    }

    Add-Pass $Label
    return $true
}

function Test-PowerShellParse {
    param([Parameter(Mandatory = $true)][string]$Path)

    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path -LiteralPath $Path),
        [ref]$tokens,
        [ref]$errors
    ) > $null

    if ($errors.Count -gt 0) {
        foreach ($error in $errors) {
            Add-Failure "PowerShell parse error in ${Path}: $($error.Message)"
        }
        return
    }

    Add-Pass "PowerShell parse $Path"
}

function Test-WorkflowCommented {
    param([Parameter(Mandatory = $true)][string]$Path)

    $activeLines = @(Get-Content -LiteralPath $Path | Where-Object {
        $_.Trim() -ne "" -and $_ -notmatch '^\s*#'
    })

    if ($activeLines.Count -gt 0) {
        Add-Failure "Workflow file must stay commented: $Path"
        return
    }

    Add-Pass "Commented workflow $Path"
}

function Test-NoPatchMarkers {
    param([Parameter(Mandatory = $true)][string[]]$Roots)

    $matches = foreach ($root in $Roots) {
        Get-ChildItem -Path (Join-Path $repoRoot $root) -Recurse -File | Select-String -Pattern '^\*\*\* (Begin Patch|End Patch|Add File|Update File|Delete File)'
    }

    if ($matches) {
        foreach ($match in $matches) {
            Add-Failure "Patch marker left in $($match.Path):$($match.LineNumber)"
        }
        return
    }

    Add-Pass "No patch markers in $($Roots -join ', ')"
}

function Test-ContentRule {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][scriptblock]$Predicate,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $content = Get-Content -LiteralPath $Path -Raw
    if (-not (& $Predicate $content)) {
        Add-Failure "${Label}: $FailureMessage"
        return
    }

    Add-Pass $Label
}

Write-Host "Running local infra validation from $repoRoot"

if (-not (Test-Command -Name "terraform")) {
    Add-Failure "terraform not found in PATH."
}
else {
    $null = Invoke-CheckedCommand `
        -Label "terraform fmt -check" `
        -FilePath "terraform" `
        -Arguments @("fmt", "-check", "-recursive", (Join-Path $repoRoot "infra/terraform")) `
        -QuietOutput

    if ($CheckTerraformValidate) {
        $null = Invoke-CheckedCommand `
            -Label "terraform validate" `
            -FilePath "terraform" `
            -Arguments @("-chdir=$(Join-Path $repoRoot 'infra/terraform/environments/prod')", "validate") `
            -QuietOutput
    }
}

Get-ChildItem -Path (Join-Path $repoRoot "infra/scripts") -Filter "*.ps1" | ForEach-Object {
    Test-PowerShellParse -Path $_.FullName
}

Get-ChildItem -Path (Join-Path $repoRoot ".github/workflows") -Filter "*.yml" | ForEach-Object {
    Test-WorkflowCommented -Path $_.FullName
}

Test-NoPatchMarkers -Roots @("infra", "docs", ".github")

Test-ContentRule `
    -Label "Backend chart default image tag" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.yaml") `
    -Predicate { param($content) $content -notmatch '(?m)^\s*defaultImageTag:\s*latest\s*$' } `
    -FailureMessage "defaultImageTag must not be 'latest'."

Test-ContentRule `
    -Label "Prod example model-service URL" `
    -Path (Join-Path $repoRoot "infra/helm/values/prod.example.yaml") `
    -Predicate {
        param($content)
        if ($content -match '(?ms)^\s*model-service:\s*.*?^\s+enabled:\s*false\s*$') {
            return $content -match '(?m)^\s*MODEL_SERVICE_URL:\s*""\s*$'
        }
        return $true
    } `
    -FailureMessage "MODEL_SERVICE_URL must be empty while example model-service stays disabled."

Test-ContentRule `
    -Label "Terraform EKS endpoint CIDR default" `
    -Path (Join-Path $repoRoot "infra/terraform/environments/prod/variables.tf") `
    -Predicate { param($content) $content -notmatch '(?m)^\s*default\s*=\s*\[\s*"0\.0\.0\.0/0"\s*\]\s*$' } `
    -FailureMessage "variables.tf must not default cluster_endpoint_public_access_cidrs to 0.0.0.0/0."

Test-ContentRule `
    -Label "Terraform DB password default" `
    -Path (Join-Path $repoRoot "infra/terraform/environments/prod/variables.tf") `
    -Predicate { param($content) $content -notmatch '(?m)^\s*default\s*=\s*"replace-me-db-password"\s*$' } `
    -FailureMessage "variables.tf must not default db_password to placeholder value."

if ($CheckHelm -or $RequireHelm) {
    if (-not (Test-Command -Name "helm")) {
        if ($RequireHelm) {
            Add-Failure "helm not found in PATH."
        }
        else {
            Add-Warning "helm not found in PATH. Skipping helm checks."
        }
    }
    else {
        $null = Invoke-CheckedCommand `
            -Label "helm lint backend chart" `
            -FilePath "helm" `
            -Arguments @(
                "lint",
                (Join-Path $repoRoot "infra/helm/charts/backend-stack"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/prod.example.yaml")
            ) `
            -QuietOutput

        $null = Invoke-CheckedCommand `
            -Label "helm template backend chart" `
            -FilePath "helm" `
            -Arguments @(
                "template",
                "pytorch-model",
                (Join-Path $repoRoot "infra/helm/charts/backend-stack"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/prod.example.yaml")
            ) `
            -QuietOutput

        $null = Invoke-CheckedCommand `
            -Label "helm lint platform chart" `
            -FilePath "helm" `
            -Arguments @(
                "lint",
                (Join-Path $repoRoot "infra/helm/charts/platform-addons"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/addons.example.yaml")
            ) `
            -QuietOutput

        $null = Invoke-CheckedCommand `
            -Label "helm template platform chart" `
            -FilePath "helm" `
            -Arguments @(
                "template",
                "platform-addons",
                (Join-Path $repoRoot "infra/helm/charts/platform-addons"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/addons.example.yaml")
            ) `
            -QuietOutput
    }
}

Write-Host ""
Write-Host "Validation summary: $($failures.Count) failure(s), $($warnings.Count) warning(s)."

if ($failures.Count -gt 0) {
    exit 1
}

exit 0
