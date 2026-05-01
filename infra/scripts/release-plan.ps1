Set-StrictMode -Version Latest

function ConvertTo-PlanParameter {
    param([Parameter(Mandatory = $true)][object]$Parameter)

    $valueKind = if ($Parameter.type -eq "SecureString") { "secret" } else { "plain" }
    return [ordered]@{
        name      = $Parameter.name
        type      = $Parameter.type
        valueKind = $valueKind
    }
}

function Get-SkipFlag {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Skip,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($Skip.ContainsKey($Name)) {
        return [bool]$Skip[$Name]
    }

    return $false
}

function New-ReleasePlan {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$ProductionDeploymentContract,
        [Parameter(Mandatory = $true)][string]$ProductionDeploymentContractPath,
        [Parameter(Mandatory = $true)][string]$BackendHelmValuesOverridePath,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$SsmParameters,
        [Parameter(Mandatory = $true)][string]$TerraformDirectory,
        [Parameter(Mandatory = $true)][string]$TerraformVarsFile,
        [Parameter(Mandatory = $true)][string]$BackendValuesFile,
        [Parameter(Mandatory = $true)][string]$PlatformValuesFile,
        [Parameter(Mandatory = $true)][hashtable]$Skip
    )

    return [ordered]@{
        schemaVersion                     = 1
        environment                       = $ProductionDeploymentContract.environment
        releaseName                       = $ProductionDeploymentContract.releaseName
        namespace                         = $ProductionDeploymentContract.namespace
        productionDeploymentContractPath  = $ProductionDeploymentContractPath
        backendHelmValuesOverridePath     = $BackendHelmValuesOverridePath
        terraformDirectory                = $TerraformDirectory
        terraformVarsFile                 = $TerraformVarsFile
        backendValuesFile                 = $BackendValuesFile
        platformValuesFile                = $PlatformValuesFile
        phases                            = [ordered]@{
            terraform     = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "Terraform" }
            parameterSync = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "ParameterSync" }
            addons        = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "Addons" }
            backendDeploy = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "BackendDeploy" }
            frontendDeploy = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "FrontendDeploy" }
            apiEdgeSync   = [ordered]@{ skipped = Get-SkipFlag -Skip $Skip -Name "ApiEdgeSync" }
        }
        workloadImages                    = $ProductionDeploymentContract.workloadImages
        modelRuntimes                     = $ProductionDeploymentContract.modelRuntimes
        ssmParameters                     = @($SsmParameters | ForEach-Object { ConvertTo-PlanParameter -Parameter $_ })
        commands                          = @(
            "terraform -chdir=$TerraformDirectory plan -var-file=$TerraformVarsFile",
            "helm upgrade --install $($ProductionDeploymentContract.releaseName) infra/helm/charts/backend-stack --namespace $($ProductionDeploymentContract.namespace) -f $BackendValuesFile -f $BackendHelmValuesOverridePath"
        )
    }
}

function Save-ReleasePlan {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Plan,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Environment,
        [Parameter(Mandatory = $true)][string]$ReleaseArtifactId
    )

    $generatedDir = Join-Path $RepoRoot "infra/generated/releases"
    if (-not (Test-Path -LiteralPath $generatedDir)) {
        New-Item -ItemType Directory -Path $generatedDir | Out-Null
    }

    $safeReleaseArtifactId = $ReleaseArtifactId -replace '[^A-Za-z0-9_.-]', '-'
    $path = Join-Path $generatedDir "release-plan.$Environment.$safeReleaseArtifactId.json"
    $Plan | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
    return $path
}
