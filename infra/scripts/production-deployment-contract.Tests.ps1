$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "production-deployment-contract.ps1")
. (Join-Path $here "production-deployment-contract.TestHelpers.ps1")

Describe "Production Deployment Contract" {
    It "resolves image facts and Model Runtime entries" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test" `
            -EnableModelService $true

        $contract.workloadImages.api.repository | Should Be "123456789012.dkr.ecr.eu-central-1.amazonaws.com/pytorch-model/api"
        $contract.workloadImages.worker.tag | Should Be "sha-test"
        $contract.modelRuntimes.effnetb0.enabled | Should Be $true
        $contract.modelRuntimes.effnetb0.serviceUrl | Should Be "http://pytorch-model-backend-stack-model-service-effnetb0:8000"
        $contract.modelRuntimes.effnetb0.roleArn | Should Be "arn:aws:iam::123456789012:role/model-service"
        $contract.modelRuntimes.vitb16.serviceAccountName | Should Be "pytorch-model-model-service-vitb16"
    }

    It "fails when enabled Model Runtimes lack workload identity" {
        $outputs = New-TerraformOutputsFixture
        $outputs.app_workload_role_arns.value.Remove("model_service")

        {
            New-ProductionDeploymentContract `
                -TerraformOutputs $outputs `
                -ProjectName "pytorch-model" `
                -Environment "prod" `
                -Namespace "pytorch-model-prod" `
                -ReleaseName "pytorch-model" `
                -ApiImageTag "sha-test" `
                -EnableModelService $true
        } | Should Throw "Production Deployment Contract missing required value: modelRuntimes.effnetb0.roleArn"
    }

    It "fails when release namespace disagrees with Terraform namespace" {
        {
            New-ProductionDeploymentContract `
                -TerraformOutputs (New-TerraformOutputsFixture) `
                -ProjectName "pytorch-model" `
                -Environment "prod" `
                -Namespace "other-namespace" `
                -ReleaseName "pytorch-model" `
                -ApiImageTag "sha-test"
        } | Should Throw "Production Deployment Contract namespace mismatch"
    }

    It "writes latest and release artifact files" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test"

        $path = Save-ProductionDeploymentContract `
            -Contract $contract `
            -RepoRoot "TestDrive:\" `
            -ReleaseArtifactId "sha:test"

        Test-Path -LiteralPath $path | Should Be $true
        Test-Path -LiteralPath "TestDrive:\infra\generated\releases\production-deployment-contract.prod.sha-test.json" | Should Be $true
    }
}
