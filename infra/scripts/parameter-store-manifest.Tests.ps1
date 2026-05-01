$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "parameter-store-manifest.ps1")

function New-ManifestParameter {
    param(
        [string]$Name = "/pytorch-model/prod/api/SECRET_KEY",
        [string]$Type = "SecureString",
        [string]$Value = "real-secret"
    )

    return [pscustomobject]@{
        name  = $Name
        type  = $Type
        value = $Value
    }
}

Describe "Parameter Store Manifest" {
    It "accepts valid operator-supplied parameters" {
        {
            Assert-ParameterManifest -Parameters @(
                (New-ManifestParameter),
                (New-ManifestParameter -Name "/pytorch-model/prod/api/MAIL_SERVER" -Type "String" -Value "smtp.example.com")
            )
        } | Should Not Throw
    }

    It "rejects duplicate names" {
        {
            Assert-ParameterManifest -Parameters @(
                (New-ManifestParameter),
                (New-ManifestParameter)
            )
        } | Should Throw "Parameter manifest contains duplicate name"
    }

    It "rejects invalid types" {
        {
            Assert-ParameterManifest -Parameters @(
                (New-ManifestParameter -Type "StringList")
            )
        } | Should Throw "Parameter manifest type must be String or SecureString"
    }

    It "rejects placeholder values" {
        {
            Assert-ParameterManifest -Parameters @(
                (New-ManifestParameter -Value "postgresql://appuser:replace-me@postgres.example.internal:5432/pytorchmodel")
            )
        } | Should Throw "Parameter manifest contains placeholder value"
    }

    It "reads JSON array manifests" {
        $path = "TestDrive:\manifest.json"
        @(
            (New-ManifestParameter),
            (New-ManifestParameter -Name "/pytorch-model/prod/api/MAIL_SERVER" -Type "String" -Value "smtp.example.com")
        ) | ConvertTo-Json | Set-Content -LiteralPath $path

        $parameters = Read-ParameterManifest -PathValue $path

        $parameters.Count | Should Be 2
    }

    It "merges manifest values over derived values" {
        $derived = @(
            (New-ManifestParameter -Name "/pytorch-model/prod/api/REDIS_HOST" -Type "String" -Value "derived-redis")
        )
        $manifest = @(
            (New-ManifestParameter -Name "/pytorch-model/prod/api/REDIS_HOST" -Type "String" -Value "manifest-redis")
        )

        $merged = Merge-Parameters -Derived $derived -Manifest $manifest

        $merged[0].value | Should Be "manifest-redis"
    }

    It "requires enabled Model Runtime paths" {
        $parameters = @(
            (New-ManifestParameter -Name "/pytorch-model/prod/api/SECRET_KEY"),
            (New-ManifestParameter -Name "/pytorch-model/prod/worker/SQS_QUEUE_URL" -Type "String" -Value "queue-url")
        )
        $expectedPaths = [pscustomobject]@{
            api    = @("/pytorch-model/prod/api/SECRET_KEY")
            worker = @("/pytorch-model/prod/worker/SQS_QUEUE_URL")
        }
        $modelRuntimes = @{
            effnetb0 = [pscustomobject]@{
                enabled                     = $true
                expectedParameterStorePaths = @("/pytorch-model/prod/model-service-effnetb0/HF_TOKEN")
            }
        }

        {
            Assert-RequiredSsmParameters `
                -Parameters $parameters `
                -ExpectedParameterStorePaths $expectedPaths `
                -ModelRuntimes $modelRuntimes
        } | Should Throw "Missing Parameter Store values"
    }
}
