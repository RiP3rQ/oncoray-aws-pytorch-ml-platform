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

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    return (Resolve-ToolPath -Name $Name) -ne ""
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

    if ((Split-Path -Leaf $Path) -eq "public-repo-guard.yml") {
        $content = Get-Content -LiteralPath $Path -Raw
        $requiredPatterns = @(
            '(?m)^permissions:\s*$',
            '(?m)^\s+contents:\s+read\s*$',
            '(?m)^\s+fetch-depth:\s+0\s*$',
            '(?m)^\s+run:\s+python scripts/public_repo_guard.py all --json\s*$'
        )
        $missingPatterns = @($requiredPatterns | Where-Object { $content -notmatch $_ })
        if ($missingPatterns.Count -gt 0 -or $content -match '(?i)\bsecrets\.') {
            Add-Failure "Public repository guard workflow violates the read-only workflow policy: $Path"
            return
        }

        Add-Pass "Read-only public repository guard workflow $Path"
        return
    }

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

    $ignoredDirectories = @(".terraform")
    $ignoredFilePatterns = @(
        ".terraform.lock.hcl",
        "*.tfplan",
        "*.tfstate",
        "*.tfstate.*"
    )

    $matches = foreach ($root in $Roots) {
        Get-ChildItem -Path (Join-Path $repoRoot $root) -Recurse -File |
            Where-Object {
                $file = $_
                $hasIgnoredDirectory = $false
                foreach ($directoryPart in $file.DirectoryName.Split([IO.Path]::DirectorySeparatorChar)) {
                    if ($ignoredDirectories -contains $directoryPart) {
                        $hasIgnoredDirectory = $true
                        break
                    }
                }

                if ($hasIgnoredDirectory) {
                    return $false
                }

                foreach ($pattern in $ignoredFilePatterns) {
                    if ($file.Name -like $pattern) {
                        return $false
                    }
                }

                return $true
            } |
            Select-String -Pattern '^\*\*\* (Begin Patch|End Patch|Add File|Update File|Delete File)'
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

function Invoke-PesterTests {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Get-Module -ListAvailable -Name Pester)) {
        Add-Warning "Pester not found. Skipping $Path."
        return
    }

    $result = Invoke-Pester -Script $Path -PassThru
    if ($result.FailedCount -gt 0) {
        Add-Failure "Pester tests failed: $Path"
        return
    }

    Add-Pass "Pester tests $Path"
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

Get-ChildItem -Path (Join-Path $repoRoot "infra/scripts") -Filter "*.Tests.ps1" | ForEach-Object {
    Invoke-PesterTests -Path $_.FullName
}

Get-ChildItem -Path (Join-Path $repoRoot ".github/workflows") -Filter "*.yml" | ForEach-Object {
    Test-WorkflowCommented -Path $_.FullName
}

Test-NoPatchMarkers -Roots @("infra", "docs", ".github")

Test-ContentRule `
    -Label "Generated infra artifacts ignored" `
    -Path (Join-Path $repoRoot ".gitignore") `
    -Predicate { param($content) $content -match '(?m)^infra/generated/\s*$' } `
    -FailureMessage "infra/generated/ must stay gitignored."

Test-ContentRule `
    -Label "Local production values ignored" `
    -Path (Join-Path $repoRoot ".gitignore") `
    -Predicate {
        param($content)
        return (
            $content -match '(?m)^infra/terraform/environments/prod/terraform\.tfvars\s*$' -and
            $content -match '(?m)^infra/helm/values/addons\.yaml\s*$' -and
            $content -match '(?m)^infra/helm/values/prod\.yaml\s*$'
        )
    } `
    -FailureMessage "terraform.tfvars, addons.yaml, and prod.yaml must stay gitignored."

Test-ContentRule `
    -Label "SSM Parameter example completeness" `
    -Path (Join-Path $repoRoot "infra/helm/values/ssm-parameters.prod.example.json") `
    -Predicate {
        param($content)
        try {
            $parameters = $content | ConvertFrom-Json
            $names = @($parameters | ForEach-Object { $_.name })
            return (
                $names -contains "/pytorch-model/prod/api/AWS_REGION" -and
                $names -contains "/pytorch-model/prod/api/S3_BUCKET_NAME"
            )
        }
        catch {
            return $false
        }
    } `
    -FailureMessage "SSM example must include AWS region and S3 bucket API parameters."

Test-ContentRule `
    -Label "Terraform SSM path output completeness" `
    -Path (Join-Path $repoRoot "infra/terraform/environments/prod/outputs.tf") `
    -Predicate {
        param($content)
        return (
            $content -match 'EFFNETB0_MODEL_ARTIFACT_URL' -and
            $content -match 'VITB16_MODEL_ARTIFACT_URL' -and
            $content -match 'S3_BUCKET_NAME'
        )
    } `
    -FailureMessage "Terraform expected_parameter_store_paths must include Model Artifact URLs and API S3 bucket config."

Test-ContentRule `
    -Label "Backend chart default image tag" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.yaml") `
    -Predicate { param($content) $content -notmatch '(?m)^\s*defaultImageTag:\s*latest\s*$' } `
    -FailureMessage "defaultImageTag must not be 'latest'."

Test-ContentRule `
    -Label "Backend chart values schema" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.schema.json") `
    -Predicate {
        param($content)
        try {
            $schema = $content | ConvertFrom-Json
            return (
                $schema.required -contains "migrations" -and
                $null -ne $schema.definitions.migrations
            )
        }
        catch {
            return $false
        }
    } `
    -FailureMessage "backend-stack values.schema.json must be valid JSON and define migrations."

Test-ContentRule `
    -Label "Backend chart Model Runtime Interface" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.yaml") `
    -Predicate {
        param($content)
        return (
            $content -match '(?ms)^workloads:\s*.*?^\s{2}model-runtime-host:\s*$' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{6}MODEL_SLUGS:\s*effnetb0,vitb16\s*$' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{4}envFromSecrets:\s*.*?model-runtime-host-secrets' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{8}- secretKey:\s*EFFNETB0_MODEL_ARTIFACT_URL' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{8}- secretKey:\s*VITB16_MODEL_ARTIFACT_URL' -and
            $content -notmatch '(?m)^\s{2}model-service-(effnetb0|vitb16):\s*$' -and
            $content -notmatch '(?m)^modelRuntime(Default|s)'
        )
    } `
    -FailureMessage "Model Runtime values must use one model-runtime-host workload and source artifact config from ExternalSecret."

Test-ContentRule `
    -Label "Prod example model-service URL" `
    -Path (Join-Path $repoRoot "infra/helm/values/prod.example.yaml") `
    -Predicate {
        param($content)
        return $content -match '(?m)^\s*MODEL_SERVICE_URL:\s*http://pytorch-model-backend-stack-model-runtime-host:8001\s*$'
    } `
    -FailureMessage "API must use one MODEL_SERVICE_URL for the Model Runtime Host service."

Test-ContentRule `
    -Label "Prod example Model Runtime Interface" `
    -Path (Join-Path $repoRoot "infra/helm/values/prod.example.yaml") `
    -Predicate {
        param($content)
        return (
            $content -match '(?ms)^workloads:\s*.*?^\s{2}model-runtime-host:\s*.*?^\s{4}enabled:\s*false\s*$' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{6}MODEL_SLUGS:\s*effnetb0,vitb16\s*$' -and
            $content -match '(?ms)^\s{2}model-runtime-host:\s*.*?^\s{4}externalSecret:\s*.*?^\s{6}enabled:\s*true\s*$' -and
            $content -match '(?ms)^migrations:\s*.*?^\s{2}enabled:\s*true\s*$' -and
            $content -notmatch '(?m)^\s{2}model-service-(effnetb0|vitb16):\s*$' -and
            $content -notmatch '(?m)^modelRuntimes:'
        )
    } `
    -FailureMessage "Prod Model Runtime overrides must use one multi-model runtime host config, ExternalSecret, and migrations."

Test-ContentRule `
    -Label "Production Helm values guard" `
    -Path (Join-Path $repoRoot "infra/scripts/deploy-prod.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'function Test-ProductionValuesFile' -and
            $content -match 'Production Helm values file contains unresolved placeholder' -and
            $content -match '--wait-for-jobs' -and
            $content -match 'migrations\.enabled=true'
        )
    } `
    -FailureMessage "deploy-prod.ps1 must reject unresolved placeholders and wait for enabled migration jobs."

Test-ContentRule `
    -Label "Production preflight script" `
    -Path (Join-Path $repoRoot "infra/scripts/preflight-prod.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'Assert-NoPlaceholder' -and
            $content -match 'DnsBootstrap' -and
            $content -match 'FullDeploy' -and
            $content -match 'terraform validate' -and
            $content -match 'helm template'
        )
    } `
    -FailureMessage "preflight-prod.ps1 must validate prod inputs and render Terraform/Helm before AWS deploy."

Test-ContentRule `
    -Label "Production SSM upload script" `
    -Path (Join-Path $repoRoot "infra/scripts/put-ssm-parameters.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'get-caller-identity' -and
            $content -match 'put-parameter' -and
            $content -match 'Assert-NoUnsafeValue' -and
            $content -match 'REPLACE_ME'
        )
    } `
    -FailureMessage "put-ssm-parameters.ps1 must verify AWS identity and reject unsafe SSM values before upload."

Test-ContentRule `
    -Label "Environment parity validator" `
    -Path (Join-Path $repoRoot "infra/scripts/validate-env-parity.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'apps/api/.env.example' -and
            $content -match 'apps/model-service/.env.example' -and
            $content -match 'ssm-parameters.prod.example.json' -and
            $content -match 'AllowedMissing'
        )
    } `
    -FailureMessage "validate-env-parity.ps1 must compare app .env.example files against Helm, SSM, and documented frontend build env."

Test-ContentRule `
    -Label "Production rollback script" `
    -Path (Join-Path $repoRoot "infra/scripts/rollback-prod.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'helm history' -and
            $content -match 'helm rollback'
        )
    } `
    -FailureMessage "rollback-prod.ps1 must expose Helm rollback."

Test-ContentRule `
    -Label "Production destroy bucket purge guard" `
    -Path (Join-Path $repoRoot "infra/scripts/destroy-prod.ps1") `
    -Predicate {
        param($content)
        return (
            $content -match 'PurgeS3Buckets' -and
            $content -match 'ConfirmDestructiveBucketPurge' -and
            $content -match 'Clear-S3Bucket'
        )
    } `
    -FailureMessage "destroy-prod.ps1 must require explicit confirmation before purging Terraform-managed buckets."

Test-ContentRule `
    -Label "Prod example disables Scalar docs" `
    -Path (Join-Path $repoRoot "infra/helm/values/prod.example.yaml") `
    -Predicate { param($content) $content -match '(?m)^\s*SCALAR_DOCS_ENABLED:\s*"false"\s*$' } `
    -FailureMessage "Production Helm values must disable Scalar docs."

Test-ContentRule `
    -Label "Backend chart model-service production env" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/values.yaml") `
    -Predicate {
        param($content)
        return (
            $content -notmatch '(?ms)^\s*model-service-effnetb0:\s*.*?^\s+APP_ENVIRONMENT:\s+development\s*$' -and
            $content -notmatch '(?ms)^\s*model-service-vitb16:\s*.*?^\s+APP_ENVIRONMENT:\s+development\s*$' -and
            $content -notmatch '(?ms)^\s*model-runtime-host:\s*.*?^\s+APP_ENVIRONMENT:\s+development\s*$'
        )
    } `
    -FailureMessage "Model Runtime chart defaults must not override APP_ENVIRONMENT to development."

Test-ContentRule `
    -Label "Backend chart disruption budgets" `
    -Path (Join-Path $repoRoot "infra/helm/charts/backend-stack/templates/pdb.yaml") `
    -Predicate { param($content) $content -match 'kind:\s*PodDisruptionBudget' } `
    -FailureMessage "backend-stack must render PodDisruptionBudgets for production workloads."

Test-ContentRule `
    -Label "Model Artifact immutable revision validation" `
    -Path (Join-Path $repoRoot "apps/model-service/src/config.py") `
    -Predicate {
        param($content)
        return (
            $content -match 'EFFNETB0_MODEL_ARTIFACT_URL' -and
            $content -match 'VITB16_MODEL_ARTIFACT_URL' -and
            $content -match 'must use an immutable Hugging Face revision'
        )
    } `
    -FailureMessage "Model Runtime Host must require immutable Model Artifact revisions in production."

Test-ContentRule `
    -Label "Terraform CloudTrail audit logging" `
    -Path (Join-Path $repoRoot "infra/terraform/environments/prod/security.tf") `
    -Predicate { param($content) $content -match 'aws_cloudtrail' } `
    -FailureMessage "Terraform must keep CloudTrail audit logging."

Test-ContentRule `
    -Label "Terraform WAF disabled by default" `
    -Path (Join-Path $repoRoot "infra/terraform/environments/prod/variables.tf") `
    -Predicate {
        param($content)
        return (
            $content -match '(?ms)variable "enable_frontend_waf".*?default\s*=\s*false' -and
            $content -match '(?ms)variable "enable_api_waf".*?default\s*=\s*false'
        )
    } `
    -FailureMessage "WAF must stay disabled by default for the budget-first architecture."

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
            -FilePath (Resolve-ToolPath -Name "helm") `
            -Arguments @(
                "lint",
                (Join-Path $repoRoot "infra/helm/charts/backend-stack"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/prod.example.yaml")
            ) `
            -QuietOutput

        $null = Invoke-CheckedCommand `
            -Label "helm template backend chart" `
            -FilePath (Resolve-ToolPath -Name "helm") `
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
            -FilePath (Resolve-ToolPath -Name "helm") `
            -Arguments @(
                "lint",
                (Join-Path $repoRoot "infra/helm/charts/platform-addons"),
                "-f",
                (Join-Path $repoRoot "infra/helm/values/addons.example.yaml")
            ) `
            -QuietOutput

        $null = Invoke-CheckedCommand `
            -Label "helm template platform chart" `
            -FilePath (Resolve-ToolPath -Name "helm") `
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
