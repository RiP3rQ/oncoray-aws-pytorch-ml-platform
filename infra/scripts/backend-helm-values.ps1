Set-StrictMode -Version Latest

function New-RoleAnnotation {
    param([string]$RoleArn = "")

    if (-not $RoleArn) {
        return [ordered]@{}
    }

    return [ordered]@{
        "eks.amazonaws.com/role-arn" = $RoleArn
    }
}

function New-BackendHelmValuesOverride {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$ProductionDeploymentContract)

    $api = [ordered]@{
        image          = [ordered]@{
            repository = $ProductionDeploymentContract.workloadImages.api.repository
            tag        = $ProductionDeploymentContract.workloadImages.api.tag
        }
        serviceAccount = [ordered]@{
            annotations = New-RoleAnnotation -RoleArn $ProductionDeploymentContract.appWorkloadRoleArns.api
        }
    }

    if ($ProductionDeploymentContract.apiWafAclArn) {
        $api.ingress = [ordered]@{
            annotations = [ordered]@{
                "alb.ingress.kubernetes.io/wafv2-acl-arn" = $ProductionDeploymentContract.apiWafAclArn
            }
        }
    }

    $worker = [ordered]@{
        image          = [ordered]@{
            repository = $ProductionDeploymentContract.workloadImages.worker.repository
            tag        = $ProductionDeploymentContract.workloadImages.worker.tag
        }
        serviceAccount = [ordered]@{
            annotations = New-RoleAnnotation -RoleArn $ProductionDeploymentContract.appWorkloadRoleArns.worker
        }
    }

    $workloads = [ordered]@{
        api    = $api
        worker = $worker
    }

    $modelRuntimes = [ordered]@{}
    foreach ($runtimeName in $ProductionDeploymentContract.modelRuntimes.Keys) {
        $runtime = $ProductionDeploymentContract.modelRuntimes[$runtimeName]
        if (-not $runtime.enabled) {
            continue
        }

        $modelRuntimes[$runtimeName] = [ordered]@{
            enabled        = $true
            workloadName   = $runtime.workloadName
            image          = [ordered]@{
                repository = $runtime.image.repository
                tag        = $runtime.image.tag
            }
            serviceAccount = [ordered]@{
                annotations = New-RoleAnnotation -RoleArn $runtime.roleArn
            }
        }
    }

    if ($ProductionDeploymentContract.modelRuntimes.effnetb0.enabled -or $ProductionDeploymentContract.modelRuntimes.vitb16.enabled) {
        $workloads.api.env = [ordered]@{
            MODEL_RUNTIME_URLS = "effnetb0=$($ProductionDeploymentContract.modelRuntimes.effnetb0.serviceUrl),vitb16=$($ProductionDeploymentContract.modelRuntimes.vitb16.serviceUrl)"
        }
    }

    return [ordered]@{
        workloads     = $workloads
        modelRuntimes = $modelRuntimes
    }
}

function Save-BackendHelmValuesOverride {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Values,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Environment,
        [Parameter(Mandatory = $true)][string]$ReleaseArtifactId
    )

    $generatedDir = Join-Path $RepoRoot "infra/generated/helm"
    if (-not (Test-Path -LiteralPath $generatedDir)) {
        New-Item -ItemType Directory -Path $generatedDir | Out-Null
    }

    $safeReleaseArtifactId = $ReleaseArtifactId -replace '[^A-Za-z0-9_.-]', '-'
    $path = Join-Path $generatedDir "backend-stack.$Environment.$safeReleaseArtifactId.json"
    $Values | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
    return $path
}
