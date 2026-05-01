param(
    [switch]$Install,
    [switch]$InitTerraform
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$terraformDir = Join-Path $repoRoot "infra/terraform/environments/prod"

$tools = @(
    @{ Name = "terraform"; WingetId = "Hashicorp.Terraform"; Required = $true },
    @{ Name = "helm"; WingetId = "Helm.Helm"; Required = $false },
    @{ Name = "aws"; WingetId = "Amazon.AWSCLI"; Required = $false },
    @{ Name = "kubectl"; WingetId = "Kubernetes.kubectl"; Required = $false }
)

function Resolve-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $knownPaths = @(
        (Join-Path $env:ProgramFiles "Amazon/AWSCLIV2/$Name.exe")
    )
    foreach ($path in $knownPaths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
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

function Test-Tool {
    param([Parameter(Mandatory = $true)][string]$Name)

    return (Resolve-ToolPath -Name $Name) -ne ""
}

function Install-ToolWithWinget {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$WingetId
    )

    if (-not (Test-Tool -Name "winget")) {
        throw "winget not found. Install $Name manually or install winget first."
    }

    & winget install --id $WingetId --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $Name ($WingetId)."
    }
}

Write-Host "Checking local infra tools"
$missingRequired = [System.Collections.Generic.List[string]]::new()
$missingOptional = [System.Collections.Generic.List[string]]::new()

foreach ($tool in $tools) {
    if (Test-Tool -Name $tool.Name) {
        Write-Host "PASS: $($tool.Name) found at $(Resolve-ToolPath -Name $tool.Name)" -ForegroundColor Green
        continue
    }

    if ($Install) {
        Write-Host "Installing $($tool.Name) with winget package $($tool.WingetId)"
        Install-ToolWithWinget -Name $tool.Name -WingetId $tool.WingetId
        continue
    }

    $message = "$($tool.Name) missing. Install with: winget install --id $($tool.WingetId) --exact"
    if ($tool.Required) {
        $missingRequired.Add($message)
        Write-Host "FAIL: $message" -ForegroundColor Red
    }
    else {
        $missingOptional.Add($message)
        Write-Host "WARN: $message" -ForegroundColor Yellow
    }
}

if ($InitTerraform) {
    if (-not (Test-Tool -Name "terraform")) {
        throw "terraform required for -InitTerraform."
    }

    Write-Host "Running terraform init -backend=false"
    & terraform "-chdir=$terraformDir" init -backend=false
    if ($LASTEXITCODE -ne 0) {
        throw "terraform init failed. If .terraform module cache is locked, close tools using it and remove infra/terraform/environments/prod/.terraform manually."
    }
}

if ($missingRequired.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing required tools: $($missingRequired.Count)" -ForegroundColor Red
    exit 1
}

if ($missingOptional.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing optional tools: $($missingOptional.Count)" -ForegroundColor Yellow
}

exit 0
