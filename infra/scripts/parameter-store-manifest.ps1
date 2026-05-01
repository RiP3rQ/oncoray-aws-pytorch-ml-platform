Set-StrictMode -Version Latest

function Assert-ParameterManifest {
    param([Parameter(Mandatory = $true)][object[]]$Parameters)

    $seen = @{}
    foreach ($parameter in $Parameters) {
        if (-not $parameter.PSObject.Properties["name"] -or [string]::IsNullOrWhiteSpace([string]$parameter.name)) {
            throw "Parameter manifest item missing required name."
        }
        if (-not $parameter.PSObject.Properties["type"] -or [string]::IsNullOrWhiteSpace([string]$parameter.type)) {
            throw "Parameter manifest item missing required type: $($parameter.name)"
        }
        if (-not $parameter.PSObject.Properties["value"] -or $null -eq $parameter.value -or [string]::IsNullOrWhiteSpace([string]$parameter.value)) {
            throw "Parameter manifest item missing required value: $($parameter.name)"
        }
        if ($parameter.name -notmatch '^/') {
            throw "Parameter manifest name must be absolute Parameter Store path: $($parameter.name)"
        }
        if ($parameter.type -notin @("String", "SecureString")) {
            throw "Parameter manifest type must be String or SecureString: $($parameter.name)"
        }
        if ([string]$parameter.value -match '(^|[:/@_-])replace-me') {
            throw "Parameter manifest contains placeholder value: $($parameter.name)"
        }
        if ($seen.ContainsKey($parameter.name)) {
            throw "Parameter manifest contains duplicate name: $($parameter.name)"
        }

        $seen[$parameter.name] = $true
    }
}

function Read-ParameterManifest {
    param([string]$PathValue)

    if (-not $PathValue) {
        return @()
    }

    $manifestPath = Resolve-Path -LiteralPath $PathValue
    $raw = Get-Content -Raw $manifestPath
    $items = $raw | ConvertFrom-Json
    if ($items -isnot [System.Collections.IEnumerable] -or $items -is [string]) {
        throw "Parameter manifest must be a JSON array."
    }

    $parameters = @($items)
    Assert-ParameterManifest -Parameters $parameters
    return $parameters
}

function Merge-Parameters {
    param(
        [Parameter(Mandatory = $true)][object[]]$Derived,
        [Parameter(Mandatory = $true)][object[]]$Manifest
    )

    $byName = [ordered]@{}
    foreach ($item in $Derived + $Manifest) {
        $byName[$item.name] = $item
    }

    return @($byName.Values)
}

function Assert-RequiredSsmParameters {
    param(
        [Parameter(Mandatory = $true)][object[]]$Parameters,
        [Parameter(Mandatory = $true)][object]$ExpectedParameterStorePaths,
        [AllowNull()][object]$ModelRuntimes = $null
    )

    $requiredParameterNames = @()
    $requiredParameterNames += @($ExpectedParameterStorePaths.api)
    $requiredParameterNames += @($ExpectedParameterStorePaths.worker)
    if ($ModelRuntimes) {
        foreach ($runtimeName in $ModelRuntimes.Keys) {
            $runtime = $ModelRuntimes[$runtimeName]
            if ($runtime.enabled) {
                $requiredParameterNames += @($runtime.expectedParameterStorePaths)
            }
        }
    }

    $missingParameters = @($requiredParameterNames | Where-Object {
        $_ -notin $Parameters.name
    })
    if ($missingParameters.Count -gt 0) {
        throw "Missing Parameter Store values: $($missingParameters -join ', '). Supply them in -ParameterManifestFile."
    }
}
