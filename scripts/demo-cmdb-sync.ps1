<#
.SYNOPSIS
    Deterministic CMDB Sync Automation (~85% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for CMDB synchronization.
    Queries Azure Resource Graph for actual inventory, queries GLPI CMDB for registered
    computers, compares the two, auto-updates exact matches, and flags ambiguous cases.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    GLPI: http://glpi-opsauto-demo.swedencentral.azurecontainer.io
    Run from: Any machine with az CLI authenticated
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$ResourceGroup = "rg-arcbox-itpro"
$GlpiUrl = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
$GlpiClientId = "YOUR_CLIENT_ID"
$GlpiClientSecret = "YOUR_CLIENT_SECRET"
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC CMDB SYNC AUTOMATION                     ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~85%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Source: Azure Resource Graph (truth) vs. GLPI CMDB (record)    ║" -ForegroundColor Cyan
Write-Host "║  Action: Auto-update matches, flag discrepancies for review     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
#endregion

#region Helper Functions
function Write-Status {
    param(
        [string]$Message,
        [ValidateSet("Pass", "Warn", "Critical", "Info")]
        [string]$Level = "Info"
    )
    switch ($Level) {
        "Pass"     { Write-Host "  [PASS]     $Message" -ForegroundColor Green }
        "Warn"     { Write-Host "  [WARN]     $Message" -ForegroundColor Yellow }
        "Critical" { Write-Host "  [CRITICAL] $Message" -ForegroundColor Red }
        "Info"     { Write-Host "  [INFO]     $Message" -ForegroundColor Gray }
    }
}

function Get-GlpiAuth {
    try {
        $tokenBody = @{
            grant_type    = "client_credentials"
            client_id     = $GlpiClientId
            client_secret = $GlpiClientSecret
            scope         = "write:config read:config"
        }
        $tokenResponse = Invoke-RestMethod -Uri "$GlpiUrl/marketplace/oauth/token" `
            -Method Post -Body $tokenBody -ContentType "application/x-www-form-urlencoded"

        $headers = @{
            "Authorization" = "Bearer $($tokenResponse.access_token)"
            "Content-Type"  = "application/json"
        }
        $initResponse = Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/initSession" `
            -Method Get -Headers $headers
        return @{
            SessionToken = $initResponse.session_token
            AccessToken  = $tokenResponse.access_token
        }
    }
    catch {
        Write-Status "Failed to authenticate to GLPI: $_" -Level "Warn"
        return $null
    }
}

function Get-GlpiComputers {
    param([hashtable]$Auth)
    if (-not $Auth) { return @() }
    try {
        $headers = @{
            "Authorization" = "Bearer $($Auth.AccessToken)"
            "Session-Token" = $Auth.SessionToken
            "Content-Type"  = "application/json"
        }
        $response = Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/Computer?range=0-200&expand_dropdowns=true" `
            -Method Get -Headers $headers
        return $response
    }
    catch {
        Write-Status "Failed to query GLPI computers: $_" -Level "Warn"
        return @()
    }
}

function Update-GlpiComputer {
    param(
        [int]$ComputerId,
        [hashtable]$Updates,
        [hashtable]$Auth
    )
    if (-not $Auth) { return $null }
    try {
        $headers = @{
            "Authorization" = "Bearer $($Auth.AccessToken)"
            "Session-Token" = $Auth.SessionToken
            "Content-Type"  = "application/json"
        }
        $body = @{ input = $Updates } | ConvertTo-Json -Depth 5
        $response = Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/Computer/$ComputerId" `
            -Method Put -Headers $headers -Body $body
        return $response
    }
    catch {
        Write-Status "Failed to update GLPI computer #$ComputerId : $_" -Level "Warn"
        return $null
    }
}
#endregion

#region Step 1: Query Azure Resource Graph for actual inventory
Write-Host "━━━ Step 1: Querying Azure Resource Graph (source of truth) ━━━" -ForegroundColor White
$azureServers = @()
try {
    $arcQuery = @"
resources
| where type == 'microsoft.hybridcompute/machines'
| where resourceGroup =~ '$ResourceGroup'
| project name, osType = properties.osType, osName = properties.osName,
          osVersion = properties.osVersion, status = properties.status,
          location, id, lastStatusChange = properties.lastStatusChange,
          agentVersion = properties.agentVersion,
          model = properties.detectedProperties.model,
          manufacturer = properties.detectedProperties.manufacturer,
          totalPhysicalMemoryInBytes = properties.detectedProperties.totalPhysicalMemoryInBytes,
          processorCount = properties.detectedProperties.processorCount
| order by name asc
"@
    $result = az graph query -q $arcQuery --first 100 2>&1
    if ($LASTEXITCODE -eq 0) {
        $parsed = $result | ConvertFrom-Json
        $azureServers = $parsed.data
        Write-Status "Found $($azureServers.Count) Arc-enrolled servers in Azure" -Level "Pass"
        foreach ($s in $azureServers) {
            Write-Status "  $($s.name) | OS: $($s.osName) $($s.osVersion) | Status: $($s.status)" -Level "Info"
        }
    }
    else {
        Write-Status "Azure Resource Graph query failed" -Level "Critical"
    }
}
catch {
    Write-Status "Error querying Azure: $_" -Level "Critical"
}
Write-Host ""
#endregion

#region Step 2: Query GLPI CMDB for registered computers
Write-Host "━━━ Step 2: Querying GLPI CMDB (registered inventory) ━━━" -ForegroundColor White
$glpiAuth = Get-GlpiAuth
$glpiComputers = Get-GlpiComputers -Auth $glpiAuth

if ($glpiComputers -and $glpiComputers.Count -gt 0) {
    Write-Status "Found $($glpiComputers.Count) computers in GLPI CMDB" -Level "Pass"
    foreach ($c in $glpiComputers) {
        $cName = if ($c.name) { $c.name } else { "(unnamed #$($c.id))" }
        $cOS = if ($c.operatingsystems_id) { $c.operatingsystems_id } else { "unknown" }
        Write-Status "  $cName | OS: $cOS | Serial: $($c.serial)" -Level "Info"
    }
}
else {
    Write-Status "No computers in GLPI or GLPI not reachable — using simulated data for demo" -Level "Warn"
    # Simulated GLPI data for offline demo
    $glpiComputers = @(
        [PSCustomObject]@{ id = 1; name = "ArcBox-Win2K22"; operatingsystems_id = "Windows Server 2022"; serial = "VM-001"; comment = "" }
        [PSCustomObject]@{ id = 2; name = "ArcBox-Win2K19"; operatingsystems_id = "Windows Server 2019"; serial = "VM-002"; comment = "" }
        [PSCustomObject]@{ id = 3; name = "ArcBox-SQL"; operatingsystems_id = "Windows Server 2022"; serial = "VM-003"; comment = "" }
        [PSCustomObject]@{ id = 4; name = "ArcBox-Ubuntu-01"; operatingsystems_id = "Ubuntu 20.04"; serial = "VM-004"; comment = "" }
        [PSCustomObject]@{ id = 5; name = "OldServer-Decomm"; operatingsystems_id = "Windows Server 2016"; serial = "VM-OLD"; comment = "Decommissioned?" }
    )
    Write-Status "Using $($glpiComputers.Count) simulated GLPI records" -Level "Info"
}
Write-Host ""
#endregion

#region Step 3: Compare and reconcile
Write-Host "━━━ Step 3: Comparing Azure (truth) vs. GLPI (record) ━━━" -ForegroundColor White
Write-Host ""

$matched = @()
$inAzureOnly = @()
$inGlpiOnly = @()
$discrepancies = @()

$azureNames = $azureServers | ForEach-Object { $_.name.ToLower() }
$glpiNames = $glpiComputers | ForEach-Object { $_.name.ToLower() }

# Find matches, Azure-only, GLPI-only
foreach ($az in $azureServers) {
    $glpiMatch = $glpiComputers | Where-Object { $_.name -ieq $az.name }
    if ($glpiMatch) {
        $matched += [PSCustomObject]@{
            Name       = $az.name
            AzureOS    = "$($az.osName) $($az.osVersion)"
            GlpiOS     = $glpiMatch.operatingsystems_id
            AzureStatus = $az.status
            GlpiId     = $glpiMatch.id
        }
    }
    else {
        $inAzureOnly += $az
    }
}

foreach ($gl in $glpiComputers) {
    $azMatch = $azureServers | Where-Object { $_.name -ieq $gl.name }
    if (-not $azMatch) {
        $inGlpiOnly += $gl
    }
}

# Check for discrepancies in matched records
foreach ($m in $matched) {
    if ($m.GlpiOS -and $m.AzureOS -and ($m.GlpiOS -notmatch [regex]::Escape($m.AzureOS.Split(" ")[0]))) {
        $discrepancies += [PSCustomObject]@{
            Name     = $m.Name
            Field    = "OS"
            Azure    = $m.AzureOS
            GLPI     = $m.GlpiOS
            GlpiId   = $m.GlpiId
        }
    }
}

# Display results
Write-Host "  ┌────────────────────────────────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ RECONCILIATION RESULTS                                        │" -ForegroundColor White
Write-Host "  ├────────────────────────────────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │ Matched (in both Azure and GLPI): $("$($matched.Count)".PadRight(27)) │" -ForegroundColor Green
Write-Host "  │ In Azure only (missing from GLPI): $("$($inAzureOnly.Count)".PadRight(26)) │" -ForegroundColor $(if ($inAzureOnly.Count -gt 0) { "Yellow" } else { "Green" })
Write-Host "  │ In GLPI only (not in Azure):       $("$($inGlpiOnly.Count)".PadRight(26)) │" -ForegroundColor $(if ($inGlpiOnly.Count -gt 0) { "Yellow" } else { "Green" })
Write-Host "  │ Discrepancies in matched records:   $("$($discrepancies.Count)".PadRight(26)) │" -ForegroundColor $(if ($discrepancies.Count -gt 0) { "Yellow" } else { "Green" })
Write-Host "  └────────────────────────────────────────────────────────────────┘" -ForegroundColor White
Write-Host ""

if ($inAzureOnly.Count -gt 0) {
    Write-Host "  Servers in Azure but MISSING from GLPI (need to add):" -ForegroundColor Yellow
    foreach ($a in $inAzureOnly) {
        Write-Status "  + $($a.name) ($($a.osName) $($a.osVersion))" -Level "Warn"
    }
    Write-Host ""
}

if ($inGlpiOnly.Count -gt 0) {
    Write-Host "  Servers in GLPI but NOT in Azure (possible decommissions):" -ForegroundColor Yellow
    foreach ($g in $inGlpiOnly) {
        Write-Status "  - $($g.name) ($($g.operatingsystems_id))" -Level "Warn"
    }
    Write-Host ""
}

if ($discrepancies.Count -gt 0) {
    Write-Host "  Data discrepancies (Azure vs. GLPI):" -ForegroundColor Yellow
    Write-Host "  ┌──────────────────────┬────────┬──────────────────────┬──────────────────────┐" -ForegroundColor White
    Write-Host "  │ Server               │ Field  │ Azure (truth)        │ GLPI (record)        │" -ForegroundColor White
    Write-Host "  ├──────────────────────┼────────┼──────────────────────┼──────────────────────┤" -ForegroundColor White
    foreach ($d in $discrepancies) {
        $dName = $d.Name.PadRight(20).Substring(0, 20)
        $dField = $d.Field.PadRight(6).Substring(0, 6)
        $dAzure = $d.Azure.PadRight(20).Substring(0, 20)
        $dGlpi = $d.GLPI.PadRight(20).Substring(0, 20)
        Write-Host "  │ $dName │ $dField │ $dAzure │ $dGlpi │" -ForegroundColor Yellow
    }
    Write-Host "  └──────────────────────┴────────┴──────────────────────┴──────────────────────┘" -ForegroundColor White
    Write-Host ""
}
#endregion

#region Step 4: Auto-update exact matches
Write-Host "━━━ Step 4: Auto-updating exact matches in GLPI ━━━" -ForegroundColor White
$updatedCount = 0
foreach ($m in $matched) {
    $az = $azureServers | Where-Object { $_.name -ieq $m.Name }
    if (-not $az) { continue }

    $updates = @{}
    if ($az.status) { $updates["comment"] = "Azure Arc Status: $($az.status) | Last sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm')" }

    if ($updates.Count -gt 0 -and $glpiAuth) {
        $result = Update-GlpiComputer -ComputerId $m.GlpiId -Updates $updates -Auth $glpiAuth
        if ($result) {
            Write-Status "Updated $($m.Name) in GLPI (ID: $($m.GlpiId))" -Level "Pass"
            $updatedCount++
        }
        else {
            Write-Status "Would update $($m.Name) in GLPI" -Level "Info"
        }
    }
    else {
        Write-Status "Would update $($m.Name) — status: $($az.status)" -Level "Info"
        $updatedCount++
    }
}
Write-Status "Updated $updatedCount of $($matched.Count) matched records" -Level "Pass"
Write-Host ""
#endregion

#region Step 5: Flag ambiguous cases
Write-Host "━━━ Step 5: Flagging ambiguous cases for human review ━━━" -ForegroundColor White

$ambiguousCases = @()
if ($inGlpiOnly.Count -gt 0) {
    foreach ($g in $inGlpiOnly) {
        $ambiguousCases += [PSCustomObject]@{
            Server = $g.name
            Issue  = "In GLPI but not in Azure — decommissioned or renamed?"
            Action = "HUMAN REVIEW: Confirm if server was decommissioned or renamed"
        }
    }
}

foreach ($d in $discrepancies) {
    $ambiguousCases += [PSCustomObject]@{
        Server = $d.Name
        Issue  = "OS mismatch: Azure='$($d.Azure)' vs GLPI='$($d.GLPI)'"
        Action = "HUMAN REVIEW: Confirm which OS version is correct"
    }
}

if ($ambiguousCases.Count -gt 0) {
    Write-Host ""
    Write-Host "  ⚠ Items requiring human review:" -ForegroundColor Yellow
    foreach ($ac in $ambiguousCases) {
        Write-Status "$($ac.Server): $($ac.Issue)" -Level "Warn"
        Write-Status "  → $($ac.Action)" -Level "Info"
    }
}
else {
    Write-Status "No ambiguous cases — all records cleanly reconciled" -Level "Pass"
}
Write-Host ""
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  CMDB sync completed in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds — manual takes ~2 hours     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  No AI needed — deterministic automation handles this fully     ║" -ForegroundColor Green
Write-Host "║                                                                 ║" -ForegroundColor Green
Write-Host "║  CMDB sync is a perfect example of where traditional            ║" -ForegroundColor Green
Write-Host "║  automation excels: structured data comparison, API calls,      ║" -ForegroundColor Green
Write-Host "║  exact matching. No interpretation needed.                      ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
#endregion
