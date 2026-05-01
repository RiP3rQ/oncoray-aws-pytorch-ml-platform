$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "backend-helm-values.ps1")
. (Join-Path $here "production-deployment-contract.ps1")
. (Join-Path $here "production-deployment-contract.TestHelpers.ps1")

Describe "Backend Helm Values Override" {
    It "writes release facts from the Production Deployment Contract" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test" `
            -EnableModelService $true

        $values = New-BackendHelmValuesOverride -ProductionDeploymentContract $contract

        $values.workloads.api.image.tag | Should Be "sha-test"
        $values.workloads.api.serviceAccount.annotations["eks.amazonaws.com/role-arn"] | Should Be "arn:aws:iam::123456789012:role/api"
        $values.workloads.api.ingress.annotations["alb.ingress.kubernetes.io/wafv2-acl-arn"] | Should Be "arn:aws:wafv2:api"
        $values.workloads.api.env.MODEL_RUNTIME_URLS | Should Be "effnetb0=http://pytorch-model-backend-stack-model-service-effnetb0:8000,vitb16=http://pytorch-model-backend-stack-model-service-vitb16:8000"
        $values.modelRuntimes.effnetb0.enabled | Should Be $true
        $values.modelRuntimes.effnetb0.workloadName | Should Be "model-service-effnetb0"
        $values.modelRuntimes.effnetb0.serviceAccount.annotations["eks.amazonaws.com/role-arn"] | Should Be "arn:aws:iam::123456789012:role/model-service"
    }

    It "omits Model Runtime values when they are disabled" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test"

        $values = New-BackendHelmValuesOverride -ProductionDeploymentContract $contract

        $values.modelRuntimes.Contains("effnetb0") | Should Be $false
        $values.workloads.api.Contains("env") | Should Be $false
    }

    It "writes JSON values file for Helm" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test"

        $values = New-BackendHelmValuesOverride -ProductionDeploymentContract $contract
        $path = Save-BackendHelmValuesOverride `
            -Values $values `
            -RepoRoot "TestDrive:\" `
            -Environment "prod" `
            -ReleaseArtifactId "sha:test"

        Test-Path -LiteralPath $path | Should Be $true
        $raw = Get-Content -LiteralPath $path -Raw
        ($raw | ConvertFrom-Json).workloads.api.image.tag | Should Be "sha-test"
    }
}
