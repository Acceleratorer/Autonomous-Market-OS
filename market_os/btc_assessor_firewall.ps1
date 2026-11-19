[CmdletBinding()]
param(
    [ValidateSet("Install", "Verify")]
    [string]$Mode = "Verify",
    [Parameter(Mandatory = $true)]
    [string]$PythonExecutable,
    [Parameter(Mandatory = $true)]
    [string]$ServerExecutable,
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
$schema = "market-os.btc-assessor-firewall.v1"
$group = "Market OS BTC Local Assessor Egress"
$createdRuleNames = @()
$blockedRemoteAddresses = @(
    "0.0.0.0-126.255.255.255",
    "128.0.0.0-255.255.255.255",
    "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"
)

function Get-FullPath([string]$PathValue) {
    return [System.IO.Path]::GetFullPath($PathValue)
}

function Test-UnderDirectory([string]$PathValue, [string]$Directory) {
    $root = (Get-FullPath $Directory).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    return (Get-FullPath $PathValue).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-ExpectedRule($Rule, [string]$Executable) {
    if ($Rule.Enabled -ne "True" -or $Rule.Direction -ne "Outbound" -or $Rule.Action -ne "Block" -or [string]$Rule.Profile -ne "Any") {
        return $false
    }

    $applications = @($Rule | Get-NetFirewallApplicationFilter)
    if ($applications.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$applications[0].Program)) {
        return $false
    }
    if (-not [string]::Equals((Get-FullPath ([string]$applications[0].Program)), (Get-FullPath $Executable), [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }

    $addressFilters = @($Rule | Get-NetFirewallAddressFilter)
    if ($addressFilters.Count -ne 1) {
        return $false
    }
    $actual = @($addressFilters[0].RemoteAddress | ForEach-Object { [string]$_ } | Sort-Object)
    $expected = @($blockedRemoteAddresses | Sort-Object)
    if ($actual.Count -ne $expected.Count) {
        return $false
    }
    return -not [bool](Compare-Object -ReferenceObject $expected -DifferenceObject $actual -CaseSensitive)
}

function Test-FirewallProfiles {
    $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
    if ($profiles.Count -lt 3) {
        return $false
    }
    foreach ($name in @("Domain", "Private", "Public")) {
        $profile = @($profiles | Where-Object { [string]$_.Name -eq $name })
        if ($profile.Count -ne 1 -or $profile[0].Enabled -ne "True") {
            return $false
        }
    }
    return $true
}

function Get-VerificationResult([string]$Status, [string]$Reason) {
    return [ordered]@{
        schema = $schema
        status = $Status
        reason = $Reason
        checked_executables = [ordered]@{
            python = Get-FullPath $PythonExecutable
            llama_server = Get-FullPath $ServerExecutable
        }
    }
}

function Remove-CreatedRules {
    foreach ($name in $createdRuleNames) {
        Remove-NetFirewallRule -PolicyStore PersistentStore -Name $name -ErrorAction SilentlyContinue
    }
}

try {
    $python = Get-FullPath $PythonExecutable
    $server = Get-FullPath $ServerExecutable
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $server -PathType Leaf)) {
        throw "Python executable or pinned llama-server executable is missing"
    }
    if ([string]::Equals($python, $server, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Python and llama-server must be distinct executable paths"
    }

    $specifications = @(
        @{ Name = "MarketOS-BTC-LocalAssessor-Python-OutboundBlock"; Executable = $python },
        @{ Name = "MarketOS-BTC-LocalAssessor-LlamaServer-OutboundBlock"; Executable = $server }
    )

    if ($Mode -eq "Install") {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw "Install mode requires an elevated administrator PowerShell session"
        }
        if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
            throw "Install mode requires ProjectRoot"
        }
        $project = Get-FullPath $ProjectRoot
        $pythonRoot = Join-Path $project ".market_os\runtimes"
        $serverRoot = Join-Path $project ".market_os\local-evidence-runtime"
        if (-not (Test-UnderDirectory $python $pythonRoot) -or -not (Test-UnderDirectory $server $serverRoot)) {
            throw "Install mode only accepts executables inside the project-local runtime directories"
        }
        if (-not (Test-FirewallProfiles)) {
            throw "Windows Firewall must be enabled for Domain, Private, and Public profiles before installing app rules"
        }

        foreach ($specification in $specifications) {
            $existing = @(Get-NetFirewallRule -PolicyStore PersistentStore -Name $specification.Name -ErrorAction SilentlyContinue)
            if ($existing.Count -gt 1) {
                throw "Multiple persistent firewall rules use the managed rule name $($specification.Name)"
            }
            if ($existing.Count -eq 1) {
                if (-not (Test-ExpectedRule $existing[0] $specification.Executable)) {
                    throw "The persistent managed firewall rule $($specification.Name) exists with unexpected settings; review it manually"
                }
                continue
            }
            New-NetFirewallRule `
                -PolicyStore PersistentStore `
                -Name $specification.Name `
                -DisplayName $specification.Name `
                -Group $group `
                -Description "Block non-loopback outbound traffic for the local BTC evidence assessor." `
                -Direction Outbound `
                -Action Block `
                -Program $specification.Executable `
                -RemoteAddress $blockedRemoteAddresses `
                -Profile Any `
                -Enabled True | Out-Null
            $createdRuleNames += $specification.Name
        }
    }

    if (-not (Test-FirewallProfiles)) {
        Remove-CreatedRules
        $result = Get-VerificationResult "unverified" "one_or_more_firewall_profiles_are_disabled_or_unavailable"
        $result | ConvertTo-Json -Depth 5 -Compress
        exit 2
    }

    foreach ($specification in $specifications) {
        $effective = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $specification.Name -ErrorAction SilentlyContinue)
        if ($effective.Count -ne 1 -or -not (Test-ExpectedRule $effective[0] $specification.Executable)) {
            Remove-CreatedRules
            $result = Get-VerificationResult "unverified" "missing_or_mismatched_active_store_rule"
            $result | ConvertTo-Json -Depth 5 -Compress
            exit 2
        }
    }

    $result = Get-VerificationResult "configured" ""
    $result | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
catch {
    Remove-CreatedRules
    $result = Get-VerificationResult "unverified" $_.Exception.Message
    $result | ConvertTo-Json -Depth 5 -Compress
    exit 2
}
