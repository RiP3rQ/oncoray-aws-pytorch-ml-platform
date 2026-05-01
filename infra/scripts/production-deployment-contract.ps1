Set-StrictMode -Version Latest

function Get-RequiredTerraformOutputValue {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Outputs,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not $Outputs.ContainsKey($Name)) {
        throw "Terraform output missing: $Name"
    }

    return $Outputs[$Name].value
}

function Test-RequiredContractValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][object]$Value
    )

    if ($null -eq $Value -or ([string]$Value).Trim() -eq "") {
        throw "Production Deployment Contract missing required value: $Name"
    }
}

function New-ContractImage {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$Tag
    )

    return [ordered]@{
        repository = $Repository
        tag        = $Tag
    }
}

function New-ProductionDeploymentContract {
    param(
        [Parameter(Mandatory = $true)][hashtable]$TerraformOutputs,
        [Parameter(Mandatory = $true)][string]$ProjectName,
        [Parameter(Mandatory = $true)][string]$Environment,
        [Parameter(Mandatory = $true)][string]$Namespace,
        [Parameter(Mandatory = $true)][string]$ReleaseName,
        [string]$ApiImageRepository = "",
        [Parameter(Mandatory = $true)][string]$ApiImageTag,
        [string]$WorkerImageRepository = "",
        [string]$WorkerImageTag = "",
        [string]$ModelServiceImageRepository = "",
        [string]$ModelServiceImageTag = "",
        [bool]$EnableModelService = $false
    )

    $ecrRepositoryUrls = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "ecr_repository_urls"
    $clusterAddonRoleArns = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "cluster_addon_role_arns"
    $appWorkloadRoleArns = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "app_workload_role_arns"
    $kubernetesServiceAccounts = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "kubernetes_service_accounts"
    $expectedParameterStorePaths = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "expected_parameter_store_paths"
    $redis = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "redis"

    $resolvedApiImageRepository = if ($ApiImageRepository) { $ApiImageRepository } else { $ecrRepositoryUrls.api }
    $resolvedWorkerImageRepository = if ($WorkerImageRepository) { $WorkerImageRepository } else { $resolvedApiImageRepository }
    $resolvedWorkerImageTag = if ($WorkerImageTag) { $WorkerImageTag } else { $ApiImageTag }
    $resolvedModelServiceImageRepository = if ($ModelServiceImageRepository) { $ModelServiceImageRepository } else { $ecrRepositoryUrls.model_service }
    $resolvedModelServiceImageTag = if ($ModelServiceImageTag) { $ModelServiceImageTag } else { $ApiImageTag }
    $modelServiceRoleArn = if ($appWorkloadRoleArns.ContainsKey("model_service")) { $appWorkloadRoleArns.model_service } else { "" }
    $modelRuntimeServiceAccounts = if ($kubernetesServiceAccounts.ContainsKey("model_runtimes")) {
        $kubernetesServiceAccounts.model_runtimes
    }
    else {
        @{
            effnetb0 = "pytorch-model-model-service-effnetb0"
            vitb16   = "pytorch-model-model-service-vitb16"
        }
    }

    $contract = [ordered]@{
        schemaVersion               = 1
        projectName                 = $ProjectName
        environment                 = $Environment
        namespace                   = $Namespace
        releaseName                 = $ReleaseName
        awsRegion                   = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "aws_region"
        clusterName                 = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "cluster_name"
        vpcId                       = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "vpc_id"
        apiWafAclArn                = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "api_waf_acl_arn"
        frontendBucketName          = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "frontend_bucket_name"
        frontendDistributionId      = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "frontend_distribution_id"
        predictionArtifactsBucketName = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "prediction_artifacts_bucket_name"
        workerQueueUrl              = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "worker_queue_url"
        workerDlqUrl                = Get-RequiredTerraformOutputValue -Outputs $TerraformOutputs -Name "worker_dlq_url"
        redis                       = [ordered]@{
            primaryEndpoint = $redis.primary_endpoint
            readerEndpoint  = $redis.reader_endpoint
            port            = $redis.port
        }
        ecrRepositories             = [ordered]@{
            api          = $ecrRepositoryUrls.api
            modelService = $ecrRepositoryUrls.model_service
        }
        workloadImages              = [ordered]@{
            api          = New-ContractImage -Repository $resolvedApiImageRepository -Tag $ApiImageTag
            worker       = New-ContractImage -Repository $resolvedWorkerImageRepository -Tag $resolvedWorkerImageTag
            modelService = New-ContractImage -Repository $resolvedModelServiceImageRepository -Tag $resolvedModelServiceImageTag
        }
        clusterAddonRoleArns        = [ordered]@{
            awsLoadBalancerController = $clusterAddonRoleArns.aws_load_balancer_controller
            externalSecrets           = $clusterAddonRoleArns.external_secrets
            fluentBit                 = $clusterAddonRoleArns.fluent_bit
        }
        appWorkloadRoleArns         = [ordered]@{
            api          = $appWorkloadRoleArns.api
            worker       = $appWorkloadRoleArns.worker
            modelService = $modelServiceRoleArn
        }
        kubernetesServiceAccounts   = [ordered]@{
            namespace    = $kubernetesServiceAccounts.namespace
            api          = $kubernetesServiceAccounts.api
            worker       = $kubernetesServiceAccounts.worker
            modelService = $kubernetesServiceAccounts.model_service
        }
        expectedParameterStorePaths = $expectedParameterStorePaths
        modelRuntimes               = [ordered]@{
            effnetb0 = [ordered]@{
                enabled                     = $EnableModelService
                workloadName                = "model-service-effnetb0"
                serviceUrl                  = "http://$ReleaseName-backend-stack-model-service-effnetb0:8000"
                image                       = New-ContractImage -Repository $resolvedModelServiceImageRepository -Tag $resolvedModelServiceImageTag
                serviceAccountName          = $modelRuntimeServiceAccounts.effnetb0
                roleArn                     = $modelServiceRoleArn
                expectedParameterStorePaths = $expectedParameterStorePaths.model_service_effnetb0
            }
            vitb16   = [ordered]@{
                enabled                     = $EnableModelService
                workloadName                = "model-service-vitb16"
                serviceUrl                  = "http://$ReleaseName-backend-stack-model-service-vitb16:8000"
                image                       = New-ContractImage -Repository $resolvedModelServiceImageRepository -Tag $resolvedModelServiceImageTag
                serviceAccountName          = $modelRuntimeServiceAccounts.vitb16
                roleArn                     = $modelServiceRoleArn
                expectedParameterStorePaths = $expectedParameterStorePaths.model_service_vitb16
            }
        }
    }

    Assert-ProductionDeploymentContract -Contract $contract
    return $contract
}

function Assert-ProductionDeploymentContract {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Contract)

    Test-RequiredContractValue -Name "environment" -Value $Contract.environment
    Test-RequiredContractValue -Name "namespace" -Value $Contract.namespace
    Test-RequiredContractValue -Name "awsRegion" -Value $Contract.awsRegion
    Test-RequiredContractValue -Name "clusterName" -Value $Contract.clusterName
    Test-RequiredContractValue -Name "vpcId" -Value $Contract.vpcId
    Test-RequiredContractValue -Name "releaseName" -Value $Contract.releaseName
    Test-RequiredContractValue -Name "ecrRepositories.api" -Value $Contract.ecrRepositories.api
    Test-RequiredContractValue -Name "ecrRepositories.modelService" -Value $Contract.ecrRepositories.modelService
    Test-RequiredContractValue -Name "workloadImages.api.repository" -Value $Contract.workloadImages.api.repository
    Test-RequiredContractValue -Name "workloadImages.api.tag" -Value $Contract.workloadImages.api.tag
    Test-RequiredContractValue -Name "workloadImages.worker.repository" -Value $Contract.workloadImages.worker.repository
    Test-RequiredContractValue -Name "workloadImages.worker.tag" -Value $Contract.workloadImages.worker.tag
    Test-RequiredContractValue -Name "workloadImages.modelService.repository" -Value $Contract.workloadImages.modelService.repository
    Test-RequiredContractValue -Name "workloadImages.modelService.tag" -Value $Contract.workloadImages.modelService.tag
    Test-RequiredContractValue -Name "clusterAddonRoleArns.awsLoadBalancerController" -Value $Contract.clusterAddonRoleArns.awsLoadBalancerController
    Test-RequiredContractValue -Name "clusterAddonRoleArns.externalSecrets" -Value $Contract.clusterAddonRoleArns.externalSecrets
    Test-RequiredContractValue -Name "clusterAddonRoleArns.fluentBit" -Value $Contract.clusterAddonRoleArns.fluentBit
    Test-RequiredContractValue -Name "appWorkloadRoleArns.api" -Value $Contract.appWorkloadRoleArns.api
    Test-RequiredContractValue -Name "appWorkloadRoleArns.worker" -Value $Contract.appWorkloadRoleArns.worker
    Test-RequiredContractValue -Name "kubernetesServiceAccounts.api" -Value $Contract.kubernetesServiceAccounts.api
    Test-RequiredContractValue -Name "kubernetesServiceAccounts.worker" -Value $Contract.kubernetesServiceAccounts.worker
    Test-RequiredContractValue -Name "workerQueueUrl" -Value $Contract.workerQueueUrl
    Test-RequiredContractValue -Name "predictionArtifactsBucketName" -Value $Contract.predictionArtifactsBucketName
    Test-RequiredContractValue -Name "redis.primaryEndpoint" -Value $Contract.redis.primaryEndpoint
    Test-RequiredContractValue -Name "redis.port" -Value $Contract.redis.port
    Test-RequiredContractValue -Name "expectedParameterStorePaths.api" -Value $Contract.expectedParameterStorePaths.api
    Test-RequiredContractValue -Name "expectedParameterStorePaths.worker" -Value $Contract.expectedParameterStorePaths.worker
    Test-RequiredContractValue -Name "modelRuntimes.effnetb0.workloadName" -Value $Contract.modelRuntimes.effnetb0.workloadName
    Test-RequiredContractValue -Name "modelRuntimes.effnetb0.serviceUrl" -Value $Contract.modelRuntimes.effnetb0.serviceUrl
    Test-RequiredContractValue -Name "modelRuntimes.effnetb0.expectedParameterStorePaths" -Value $Contract.modelRuntimes.effnetb0.expectedParameterStorePaths
    Test-RequiredContractValue -Name "modelRuntimes.vitb16.workloadName" -Value $Contract.modelRuntimes.vitb16.workloadName
    Test-RequiredContractValue -Name "modelRuntimes.vitb16.serviceUrl" -Value $Contract.modelRuntimes.vitb16.serviceUrl
    Test-RequiredContractValue -Name "modelRuntimes.vitb16.expectedParameterStorePaths" -Value $Contract.modelRuntimes.vitb16.expectedParameterStorePaths

    if ($Contract.kubernetesServiceAccounts.namespace -ne $Contract.namespace) {
        throw "Production Deployment Contract namespace mismatch: release namespace '$($Contract.namespace)' does not match Terraform namespace '$($Contract.kubernetesServiceAccounts.namespace)'."
    }

    foreach ($runtimeName in @("effnetb0", "vitb16")) {
        $runtime = $Contract.modelRuntimes[$runtimeName]
        if ($runtime.enabled) {
            Test-RequiredContractValue -Name "modelRuntimes.$runtimeName.roleArn" -Value $runtime.roleArn
        }
    }
}

function Save-ProductionDeploymentContract {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Contract,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [string]$ReleaseArtifactId = ""
    )

    $generatedDir = Join-Path $RepoRoot "infra/generated"
    if (-not (Test-Path -LiteralPath $generatedDir)) {
        New-Item -ItemType Directory -Path $generatedDir | Out-Null
    }

    $path = Join-Path $generatedDir "production-deployment-contract.$($Contract.environment).json"
    $Contract | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8

    if ($ReleaseArtifactId) {
        $releaseArtifactDir = Join-Path $generatedDir "releases"
        if (-not (Test-Path -LiteralPath $releaseArtifactDir)) {
            New-Item -ItemType Directory -Path $releaseArtifactDir | Out-Null
        }

        $safeReleaseArtifactId = $ReleaseArtifactId -replace '[^A-Za-z0-9_.-]', '-'
        $releaseArtifactPath = Join-Path $releaseArtifactDir "production-deployment-contract.$($Contract.environment).$safeReleaseArtifactId.json"
        $Contract | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $releaseArtifactPath -Encoding utf8
    }

    return $path
}
