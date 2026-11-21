[CmdletBinding()]
param(
    [ValidateSet("Install", "Verify")]
    [string]$Mode = "Verify",
    [string]$PythonExecutable,
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
    if ([string]$Rule.Group -ne $group) {
        return $false
    }
    if ((-not [string]::IsNullOrWhiteSpace([string]$Rule.Owner) -and [string]$Rule.Owner -ne "Any") -or
        [string]$Rule.LocalOnlyMapping -eq "True" -or [string]$Rule.LooseSourceMapping -eq "True") {
        return $false
    }

    $applications = @($Rule | Get-NetFirewallApplicationFilter)
    if ($applications.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$applications[0].Program)) {
        return $false
    }
    if ([string]$applications[0].Package -notin @("", "Any")) {
        return $false
    }
    if (-not [string]::Equals((Get-FullPath ([string]$applications[0].Program)), (Get-FullPath $Executable), [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }

    $addressFilters = @($Rule | Get-NetFirewallAddressFilter)
    if ($addressFilters.Count -ne 1 -or [string]$addressFilters[0].LocalAddress -ne "Any") {
        return $false
    }
    $localDynamicAddresses = @($addressFilters[0].LocalDynamicKeywordAddresses | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    $remoteDynamicAddresses = @($addressFilters[0].RemoteDynamicKeywordAddresses | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($localDynamicAddresses.Count -gt 0 -or $remoteDynamicAddresses.Count -gt 0) {
        return $false
    }
    $actual = @($addressFilters[0].RemoteAddress | ForEach-Object { [string]$_ } | Sort-Object)
    $expected = @($blockedRemoteAddresses | Sort-Object)
    if ($actual.Count -ne $expected.Count) {
        return $false
    }

    $portFilters = @($Rule | Get-NetFirewallPortFilter)
    if ($portFilters.Count -ne 1) {
        return $false
    }
    foreach ($property in @("Protocol", "LocalPort", "RemotePort", "IcmpType", "DynamicTarget")) {
        $values = @($portFilters[0].$property | ForEach-Object { [string]$_ })
        if ($values.Count -ne 1 -or $values[0] -ne "Any") {
            return $false
        }
    }

    $serviceFilters = @($Rule | Get-NetFirewallServiceFilter)
    if ($serviceFilters.Count -ne 1 -or [string]$serviceFilters[0].Service -ne "Any") {
        return $false
    }

    $interfaceFilters = @($Rule | Get-NetFirewallInterfaceFilter)
    if ($interfaceFilters.Count -ne 1 -or [string]$interfaceFilters[0].InterfaceAlias -ne "Any") {
        return $false
    }
    $interfaceTypeFilters = @($Rule | Get-NetFirewallInterfaceTypeFilter)
    if ($interfaceTypeFilters.Count -ne 1 -or [string]$interfaceTypeFilters[0].InterfaceType -ne "Any") {
        return $false
    }

    $securityFilters = @($Rule | Get-NetFirewallSecurityFilter)
    if ($securityFilters.Count -gt 1) {
        return $false
    }
    if ($securityFilters.Count -eq 1) {
        $security = $securityFilters[0]
        if ([string]$security.Authentication -ne "NotRequired" -or
            [string]$security.Encryption -ne "NotRequired" -or
            [string]$security.OverrideBlockRules -ne "False" -or
            [string]$security.LocalUser -ne "Any" -or
            [string]$security.RemoteUser -ne "Any" -or
            [string]$security.RemoteMachine -ne "Any") {
            return $false
        }
    }

    return -not [bool](Compare-Object -ReferenceObject $expected -DifferenceObject $actual -CaseSensitive)
}

function Test-RuleEnforced($Rule) {
    if ([string]$Rule.PrimaryStatus -ne "OK") {
        return $false
    }
    $statuses = @($Rule.EnforcementStatus | ForEach-Object { [string]$_ })
    return ($statuses -contains "Enforced") -or ($statuses -contains "Full")
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
    if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
        $PythonExecutable = $env:MARKET_OS_PYTHON_EXECUTABLE
    }
    if ([string]::IsNullOrWhiteSpace($ServerExecutable)) {
        $ServerExecutable = $env:MARKET_OS_SERVER_EXECUTABLE
    }
    if ([string]::IsNullOrWhiteSpace($PythonExecutable) -or [string]::IsNullOrWhiteSpace($ServerExecutable)) {
        throw "PythonExecutable and ServerExecutable must be supplied directly or through MARKET_OS_PYTHON_EXECUTABLE and MARKET_OS_SERVER_EXECUTABLE"
    }

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
                if (Test-RuleEnforced $existing[0]) {
                    continue
                }
                Remove-NetFirewallRule -PolicyStore PersistentStore -Name $specification.Name
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
        if (-not (Test-RuleEnforced $effective[0])) {
            Remove-CreatedRules
            $statuses = @($effective[0].EnforcementStatus | ForEach-Object { [string]$_ })
            $reason = "active_store_rule_not_enforced:primary_status=$($effective[0].PrimaryStatus);enforcement_status=$($statuses -join ',')"
            $result = Get-VerificationResult "unverified" $reason
            $result | ConvertTo-Json -Depth 5 -Compress
            exit 2
        }
    }

    $result = Get-VerificationResult "enforced" ""
    $result | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
catch {
    Remove-CreatedRules
    $result = Get-VerificationResult "unverified" $_.Exception.Message
    $result | ConvertTo-Json -Depth 5 -Compress
    exit 2
}
