$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "release-plan.ps1")
. (Join-Path $here "production-deployment-contract.ps1")
. (Join-Path $here "production-deployment-contract.TestHelpers.ps1")

Describe "Release Plan" {
    It "captures release artifacts and redacts secret values" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test" `
            -EnableModelService $true
        $parameters = @(
            [pscustomobject]@{ name = "/pytorch-model/prod/api/SECRET_KEY"; type = "SecureString"; value = "super-secret" },
            [pscustomobject]@{ name = "/pytorch-model/prod/api/REDIS_HOST"; type = "String"; value = "redis.example" }
        )

        $plan = New-ReleasePlan `
            -ProductionDeploymentContract $contract `
            -ProductionDeploymentContractPath "infra/generated/production-deployment-contract.prod.json" `
            -BackendHelmValuesOverridePath "infra/generated/helm/backend-stack.prod.sha-test.json" `
            -SsmParameters $parameters `
            -TerraformDirectory "infra/terraform/environments/prod" `
            -TerraformVarsFile "terraform.tfvars" `
            -BackendValuesFile "infra/helm/values/prod.yaml" `
            -PlatformValuesFile "infra/helm/values/addons.yaml" `
            -Skip @{ Terraform = $false; ParameterSync = $false; Addons = $true; BackendDeploy = $false; FrontendDeploy = $true; ApiEdgeSync = $true }

        $plan.backendHelmValuesOverridePath | Should Be "infra/generated/helm/backend-stack.prod.sha-test.json"
        $plan.phases.addons.skipped | Should Be $true
        $plan.ssmParameters[0].valueKind | Should Be "secret"
        ($plan | ConvertTo-Json -Depth 20) | Should Not Match "super-secret"
    }

    It "writes release plan artifact" {
        $contract = New-ProductionDeploymentContract `
            -TerraformOutputs (New-TerraformOutputsFixture) `
            -ProjectName "pytorch-model" `
            -Environment "prod" `
            -Namespace "pytorch-model-prod" `
            -ReleaseName "pytorch-model" `
            -ApiImageTag "sha-test"
        $plan = New-ReleasePlan `
            -ProductionDeploymentContract $contract `
            -ProductionDeploymentContractPath "contract.json" `
            -BackendHelmValuesOverridePath "values.json" `
            -SsmParameters @() `
            -TerraformDirectory "terraform" `
            -TerraformVarsFile "terraform.tfvars" `
            -BackendValuesFile "prod.yaml" `
            -PlatformValuesFile "addons.yaml" `
            -Skip @{}

        $path = Save-ReleasePlan -Plan $plan -RepoRoot "TestDrive:\" -Environment "prod" -ReleaseArtifactId "sha:test"

        Test-Path -LiteralPath $path | Should Be $true
        ($path -like "*release-plan.prod.sha-test.json") | Should Be $true
    }
}
