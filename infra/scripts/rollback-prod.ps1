param(
    [string]$ReleaseName = "pytorch-model",
    [string]$Namespace = "pytorch-model-prod",
    [int]$Revision = 0,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    throw "helm not found in PATH."
}

$historyArgs = @("history", $ReleaseName, "--namespace", $Namespace)
Write-Host "Current Helm release history:"
& helm @historyArgs
if ($LASTEXITCODE -ne 0) {
    throw "helm history failed."
}

if ($DryRun) {
    Write-Host "Dry run only. No rollback executed."
    exit 0
}

$rollbackArgs = @("rollback", $ReleaseName)
if ($Revision -gt 0) {
    $rollbackArgs += "$Revision"
}
$rollbackArgs += @("--namespace", $Namespace, "--wait")

Write-Host "Rolling back Helm release: $ReleaseName"
& helm @rollbackArgs
if ($LASTEXITCODE -ne 0) {
    throw "helm rollback failed."
}

Write-Host "Rollback completed."
