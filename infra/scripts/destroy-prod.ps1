param(
    [string]$ReleaseName = "pytorch-model",
    [string]$Namespace = "pytorch-model-prod",
    [string]$TerraformDir = "infra/terraform/environments/prod",
    [string]$TerraformVarsFile = "terraform.tfvars",
    [switch]$SkipHelm,
    [switch]$SkipAddons,
    [switch]$SkipTerraform,
    [switch]$AutoApprove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$resolvedTerraformDir = if ([System.IO.Path]::IsPathRooted($TerraformDir)) {
    $TerraformDir
}
else {
    Join-Path $repoRoot $TerraformDir
}

if (-not (Test-Path -LiteralPath $resolvedTerraformDir)) {
    throw "Terraform directory not found: $resolvedTerraformDir"
}

if (-not $SkipHelm) {
    if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
        throw "helm not found in PATH. Install helm or use -SkipHelm."
    }

    Write-Host "Uninstalling Helm release if present: $ReleaseName"
    & helm uninstall $ReleaseName --namespace $Namespace

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Helm uninstall returned non-zero exit code. Continuing. Release may already be absent."
    }
}

if (-not $SkipAddons) {
    if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
        throw "helm not found in PATH. Install helm or use -SkipAddons."
    }

    $addonReleases = @(
        @{ Name = "platform-addons"; Namespace = "amazon-cloudwatch" },
        @{ Name = "external-secrets"; Namespace = "external-secrets" },
        @{ Name = "aws-load-balancer-controller"; Namespace = "kube-system" }
    )

    foreach ($addon in $addonReleases) {
        Write-Host "Uninstalling add-on release if present: $($addon.Name)"
        & helm uninstall $addon.Name --namespace $addon.Namespace

        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Helm uninstall returned non-zero exit code for $($addon.Name). Continuing."
        }
    }
}

if (-not $SkipTerraform) {
    if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
        throw "terraform not found in PATH. Install terraform or use -SkipTerraform."
    }

    $terraformArgs = @(
        "-chdir=$resolvedTerraformDir",
        "destroy",
        "-var-file=$TerraformVarsFile"
    )

    if ($AutoApprove) {
        $terraformArgs += "-auto-approve"
    }

    Write-Host "Destroying Terraform-managed prod resources from: $resolvedTerraformDir"
    & terraform @terraformArgs
    if ($LASTEXITCODE -ne 0) {
        throw "terraform destroy failed."
    }
}
