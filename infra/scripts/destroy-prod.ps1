param(
    [string]$ReleaseName = "pytorch-model",
    [string]$Namespace = "pytorch-model-prod",
    [string]$TerraformDir = "infra/terraform/environments/prod",
    [string]$TerraformVarsFile = "terraform.tfvars",
    [switch]$SkipHelm,
    [switch]$SkipAddons,
    [switch]$SkipTerraform,
    [switch]$PurgeS3Buckets,
    [switch]$ConfirmDestructiveBucketPurge,
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

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$ContinueOnError
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0 -and -not $ContinueOnError) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Get-TerraformOutputValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    $output = & terraform -chdir=$resolvedTerraformDir output -raw $Name 2>$null
    if ($LASTEXITCODE -ne 0) {
        return ""
    }

    return $output.Trim()
}

function Clear-S3Bucket {
    param([Parameter(Mandatory = $true)][string]$BucketName)

    if (-not $BucketName -or $BucketName -eq "null") {
        return
    }

    Write-Host "Purging S3 bucket contents: $BucketName"
    Invoke-External -FilePath "aws" -Arguments @("s3", "rm", "s3://$BucketName", "--recursive")

    while ($true) {
        Write-Host "Purging S3 bucket non-current object versions/delete markers: $BucketName"
        $versionsJson = & aws s3api list-object-versions --bucket $BucketName --output json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $versionsJson) {
            return
        }

        $versions = $versionsJson | ConvertFrom-Json
        $objects = @()
        foreach ($version in @($versions.Versions)) {
            if ($null -ne $version -and $null -ne $version.Key -and $null -ne $version.VersionId) {
                $objects += @{ Key = $version.Key; VersionId = $version.VersionId }
            }
        }
        foreach ($marker in @($versions.DeleteMarkers)) {
            if ($null -ne $marker -and $null -ne $marker.Key -and $null -ne $marker.VersionId) {
                $objects += @{ Key = $marker.Key; VersionId = $marker.VersionId }
            }
        }

        if ($objects.Count -eq 0) {
            return
        }

        $deleteSpec = @{ Objects = $objects; Quiet = $true } | ConvertTo-Json -Depth 5 -Compress
        $tempFile = New-TemporaryFile
        try {
            Set-Content -LiteralPath $tempFile.FullName -Value $deleteSpec -NoNewline
            Invoke-External -FilePath "aws" -Arguments @(
                "s3api",
                "delete-objects",
                "--bucket",
                $BucketName,
                "--delete",
                "file://$($tempFile.FullName)"
            )
        }
        finally {
            Remove-Item -LiteralPath $tempFile.FullName -Force -ErrorAction SilentlyContinue
        }
    }
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

    if ($PurgeS3Buckets) {
        if (-not $ConfirmDestructiveBucketPurge) {
            throw "-PurgeS3Buckets requires -ConfirmDestructiveBucketPurge."
        }
        if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
            throw "aws not found in PATH. Install AWS CLI or omit -PurgeS3Buckets."
        }

        Clear-S3Bucket -BucketName (Get-TerraformOutputValue -Name "frontend_bucket_name")
        Clear-S3Bucket -BucketName (Get-TerraformOutputValue -Name "prediction_artifacts_bucket_name")
        Clear-S3Bucket -BucketName (Get-TerraformOutputValue -Name "cloudtrail_bucket_name")
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
