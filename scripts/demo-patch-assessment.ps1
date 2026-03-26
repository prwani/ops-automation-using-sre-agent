<#
.SYNOPSIS
    Deterministic Patch Assessment Automation (~85% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for patch assessment.
    Queries Azure Update Manager for missing patches, classifies by severity,
    runs pre-patch checks, and generates an assessment report.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Run from: Any machine with az CLI authenticated
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$ResourceGroup = "rg-arcbox-itpro"
$LogAnalyticsWorkspaceId = "f98fca75-7479-45e5-bf0c-87b56a9f9e8c"

# Nested VM credentials (for Invoke-Command from ArcBox-Client)
$NestedUser = "arcdemo"
$NestedPass = ConvertTo-SecureString "JS123!!" -AsPlainText -Force
$NestedCred = New-Object System.Management.Automation.PSCredential($NestedUser, $NestedPass)
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC PATCH ASSESSMENT                         ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~85%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Checks: Missing patches, classification, pre-patch readiness   ║" -ForegroundColor Cyan
Write-Host "║  Output: Patch assessment report with severity breakdown        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
#endregion

#region Helper
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
#endregion

#region Step 1: Query Azure Update Manager for missing patches
Write-Host "━━━ Step 1: Querying Azure Update Manager for missing patches ━━━" -ForegroundColor White

$patchQuery = @"
patchassessmentresources
| where type == 'microsoft.hybridcompute/machines/patchassessmentresults'
| where id contains '$ResourceGroup'
| extend machineName = tostring(split(id, '/')[8])
| extend lastAssessment = properties.lastModifiedDateTime
| extend osType = properties.osType
| extend criticalCount = toint(properties.availablePatchCountByClassification.critical)
| extend securityCount = toint(properties.availablePatchCountByClassification.security)
| extend definitionCount = toint(properties.availablePatchCountByClassification.definition)
| extend updateRollupCount = toint(properties.availablePatchCountByClassification.updateRollup)
| extend featurePackCount = toint(properties.availablePatchCountByClassification.featurePack)
| extend otherCount = toint(properties.availablePatchCountByClassification.other)
| project machineName, osType, lastAssessment, criticalCount, securityCount,
          definitionCount, updateRollupCount, featurePackCount, otherCount
| order by machineName asc
"@

$patchData = @()
try {
    $result = az graph query -q $patchQuery --first 100 2>&1
    if ($LASTEXITCODE -eq 0) {
        $parsed = $result | ConvertFrom-Json
        $patchData = $parsed.data
        Write-Status "Retrieved patch assessment for $($patchData.Count) machines" -Level "Pass"
    }
    else {
        Write-Status "Azure Resource Graph patch query returned no data" -Level "Warn"
        Write-Status "This may mean Update Manager assessments haven't run yet" -Level "Info"
    }
}
catch {
    Write-Status "Error querying patch data: $_" -Level "Warn"
}

# Also try direct update assessment query
if ($patchData.Count -eq 0) {
    Write-Status "Trying alternative patch assessment query..." -Level "Info"
    $altQuery = @"
resources
| where type == 'microsoft.hybridcompute/machines'
| where resourceGroup =~ '$ResourceGroup'
| project name, osType = properties.osType, status = properties.status
| order by name asc
"@
    try {
        $altResult = az graph query -q $altQuery --first 100 2>&1
        if ($LASTEXITCODE -eq 0) {
            $altParsed = $altResult | ConvertFrom-Json
            $servers = $altParsed.data
            Write-Status "Found $($servers.Count) machines — checking update status via Log Analytics" -Level "Info"

            # Query Log Analytics for update data
            $updateQuery = @"
Update
| where TimeGenerated > ago(7d)
| where UpdateState == 'Needed'
| summarize
    CriticalCount = countif(Classification == 'Critical Updates'),
    SecurityCount = countif(Classification == 'Security Updates'),
    OtherCount = countif(Classification !in ('Critical Updates', 'Security Updates'))
    by Computer
| order by Computer asc
"@
            $laResult = az monitor log-analytics query -w $LogAnalyticsWorkspaceId --analytics-query $updateQuery 2>&1
            if ($LASTEXITCODE -eq 0) {
                $laData = $laResult | ConvertFrom-Json
                if ($laData -and $laData.Count -gt 0) {
                    $patchData = $laData | ForEach-Object {
                        [PSCustomObject]@{
                            machineName    = $_.Computer
                            criticalCount  = [int]$_.CriticalCount
                            securityCount  = [int]$_.SecurityCount
                            otherCount     = [int]$_.OtherCount
                        }
                    }
                    Write-Status "Retrieved patch data from Log Analytics for $($patchData.Count) machines" -Level "Pass"
                }
            }
        }
    }
    catch {
        Write-Status "Alternative query also failed: $_" -Level "Warn"
    }
}
Write-Host ""
#endregion

#region Step 2: Patch Classification Report
Write-Host "━━━ Step 2: Patch Classification Report ━━━" -ForegroundColor White
Write-Host ""

if ($patchData -and $patchData.Count -gt 0) {
    $totalCritical = ($patchData | Measure-Object -Property criticalCount -Sum).Sum
    $totalSecurity = ($patchData | Measure-Object -Property securityCount -Sum).Sum
    $totalOther = 0
    if ($patchData[0].PSObject.Properties.Name -contains 'otherCount') {
        $totalOther = ($patchData | Measure-Object -Property otherCount -Sum).Sum
    }

    Write-Host "  ┌──────────────────────┬──────────┬──────────┬──────────┬──────────┐" -ForegroundColor White
    Write-Host "  │ Machine              │ Critical │ Security │ Other    │ Total    │" -ForegroundColor White
    Write-Host "  ├──────────────────────┼──────────┼──────────┼──────────┼──────────┤" -ForegroundColor White

    foreach ($p in $patchData) {
        $mName = $p.machineName.PadRight(20).Substring(0, 20)
        $critical = "$($p.criticalCount)".PadRight(8)
        $security = "$($p.securityCount)".PadRight(8)
        $other = "$(if ($p.PSObject.Properties.Name -contains 'otherCount') { $p.otherCount } else { 0 })".PadRight(8)
        $total = ([int]$p.criticalCount + [int]$p.securityCount + $(if ($p.PSObject.Properties.Name -contains 'otherCount') { [int]$p.otherCount } else { 0 }))
        $totalStr = "$total".PadRight(8)
        $color = if ([int]$p.criticalCount -gt 0) { "Red" } elseif ([int]$p.securityCount -gt 0) { "Yellow" } else { "Green" }
        Write-Host "  │ $mName │ $critical │ $security │ $other │ $totalStr │" -ForegroundColor $color
    }
    Write-Host "  ├──────────────────────┼──────────┼──────────┼──────────┼──────────┤" -ForegroundColor White
    $tName = "TOTAL".PadRight(20)
    $tCrit = "$totalCritical".PadRight(8)
    $tSec = "$totalSecurity".PadRight(8)
    $tOther = "$totalOther".PadRight(8)
    $tAll = "$($totalCritical + $totalSecurity + $totalOther)".PadRight(8)
    Write-Host "  │ $tName │ $tCrit │ $tSec │ $tOther │ $tAll │" -ForegroundColor White
    Write-Host "  └──────────────────────┴──────────┴──────────┴──────────┴──────────┘" -ForegroundColor White

    if ($totalCritical -gt 0) {
        Write-Host ""
        Write-Status "$totalCritical CRITICAL patches missing — immediate attention required" -Level "Critical"
    }
    if ($totalSecurity -gt 0) {
        Write-Status "$totalSecurity Security patches missing — schedule for next window" -Level "Warn"
    }
}
else {
    Write-Status "No patch assessment data available — showing example output:" -Level "Info"
    Write-Host ""
    Write-Host "  ┌──────────────────────┬──────────┬──────────┬──────────┬──────────┐" -ForegroundColor White
    Write-Host "  │ Machine              │ Critical │ Security │ Other    │ Total    │" -ForegroundColor White
    Write-Host "  ├──────────────────────┼──────────┼──────────┼──────────┼──────────┤" -ForegroundColor White
    Write-Host "  │ ArcBox-Win2K22       │ 2        │ 5        │ 3        │ 10       │" -ForegroundColor Red
    Write-Host "  │ ArcBox-Win2K19       │ 0        │ 3        │ 7        │ 10       │" -ForegroundColor Yellow
    Write-Host "  │ ArcBox-SQL           │ 1        │ 4        │ 2        │ 7        │" -ForegroundColor Red
    Write-Host "  ├──────────────────────┼──────────┼──────────┼──────────┼──────────┤" -ForegroundColor White
    Write-Host "  │ TOTAL                │ 3        │ 12       │ 12       │ 27       │" -ForegroundColor White
    Write-Host "  └──────────────────────┴──────────┴──────────┴──────────┴──────────┘" -ForegroundColor White
    Write-Host "  (Example data — actual data requires Update Manager assessments)" -ForegroundColor DarkGray
}
Write-Host ""
#endregion

#region Step 3: Pre-patch readiness checks
Write-Host "━━━ Step 3: Pre-Patch Readiness Checks ━━━" -ForegroundColor White
Write-Host ""

$isArcBoxClient = (hostname) -match "ArcBox-Client"

# Get list of Windows servers
$windowsServers = @()
try {
    $winQuery = @"
resources
| where type == 'microsoft.hybridcompute/machines'
| where resourceGroup =~ '$ResourceGroup'
| where properties.osType == 'Windows'
| project name
"@
    $winResult = az graph query -q $winQuery --first 100 2>&1
    if ($LASTEXITCODE -eq 0) {
        $windowsServers = ($winResult | ConvertFrom-Json).data | ForEach-Object { $_.name }
    }
}
catch { }

if ($windowsServers.Count -eq 0) {
    $windowsServers = @("ArcBox-Win2K22", "ArcBox-Win2K19")
    Write-Status "Using default server list for pre-patch checks" -Level "Info"
}

foreach ($vmName in $windowsServers | Select-Object -First 3) {
    Write-Host "  ┌─ Pre-patch check: $vmName ────────────────────────" -ForegroundColor Cyan

    if ($isArcBoxClient) {
        try {
            # Disk space check
            $diskFree = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                $sysDrive = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
                [math]::Round($sysDrive.FreeSpace / 1GB, 1)
            } -ErrorAction Stop

            if ($diskFree -lt 5) {
                Write-Status "Disk C: has only $($diskFree) GB free — NOT ENOUGH for patching" -Level "Critical"
            }
            elseif ($diskFree -lt 10) {
                Write-Status "Disk C: has $($diskFree) GB free — marginal" -Level "Warn"
            }
            else {
                Write-Status "Disk C: has $($diskFree) GB free — sufficient" -Level "Pass"
            }

            # Pending reboot check
            $pendingReboot = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                $rebootPending = $false
                if (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired" -ErrorAction SilentlyContinue) {
                    $rebootPending = $true
                }
                if (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending" -ErrorAction SilentlyContinue) {
                    $rebootPending = $true
                }
                $rebootPending
            } -ErrorAction Stop

            if ($pendingReboot) {
                Write-Status "PENDING REBOOT detected — reboot before patching" -Level "Critical"
            }
            else {
                Write-Status "No pending reboot — ready for patching" -Level "Pass"
            }

            # Critical services check
            $critServices = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                $services = @("wuauserv", "TrustedInstaller", "BITS")
                foreach ($svc in $services) {
                    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
                    [PSCustomObject]@{ Name = $svc; Status = if ($s) { $s.Status.ToString() } else { "NotFound" } }
                }
            } -ErrorAction Stop

            foreach ($svc in $critServices) {
                if ($svc.Status -eq "Running" -or $svc.Status -eq "Stopped") {
                    Write-Status "Service $($svc.Name): $($svc.Status)" -Level "Pass"
                }
                else {
                    Write-Status "Service $($svc.Name): $($svc.Status) — may need attention" -Level "Warn"
                }
            }
        }
        catch {
            Write-Status "Cannot reach $vmName for pre-patch checks: $_" -Level "Warn"
        }
    }
    else {
        Write-Status "Pre-patch checks require ArcBox-Client (Invoke-Command)" -Level "Info"
        Write-Status "Checks would verify: disk space, pending reboots, critical services" -Level "Info"

        # Show what the checks would do
        Write-Status "  Check 1: Disk C: free space ≥ 10 GB" -Level "Info"
        Write-Status "  Check 2: No pending reboot (registry keys)" -Level "Info"
        Write-Status "  Check 3: Windows Update service (wuauserv) accessible" -Level "Info"
        Write-Status "  Check 4: BITS service accessible" -Level "Info"
        Write-Status "  Check 5: TrustedInstaller service accessible" -Level "Info"
    }

    Write-Host "  └──────────────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host ""
}
#endregion

#region Step 4: Patch Deployment Recommendation (deterministic)
Write-Host "━━━ Step 4: Deterministic Patch Deployment Recommendation ━━━" -ForegroundColor White
Write-Host ""
Write-Host "  Rule-based deployment recommendation:" -ForegroundColor Gray
Write-Host ""
Write-Host "  ┌──────────────────┬──────────────────┬────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ Classification   │ SLA              │ Recommendation                     │" -ForegroundColor White
Write-Host "  ├──────────────────┼──────────────────┼────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │ Critical         │ 72 hours         │ Deploy in next maintenance window   │" -ForegroundColor Red
Write-Host "  │ Security         │ 7 days           │ Schedule for weekly patch cycle     │" -ForegroundColor Yellow
Write-Host "  │ Update Rollup    │ 14 days          │ Include in monthly rollup           │" -ForegroundColor White
Write-Host "  │ Feature Pack     │ 30 days          │ Test in dev first, then production  │" -ForegroundColor Gray
Write-Host "  │ Other            │ 30 days          │ Low priority — batch with rollups   │" -ForegroundColor DarkGray
Write-Host "  └──────────────────┴──────────────────┴────────────────────────────────────┘" -ForegroundColor White
Write-Host ""
Write-Status "This is a STATIC rule — same classification always gets same SLA" -Level "Info"
Write-Status "Cannot factor in: application dependencies, business calendar, risk" -Level "Info"
Write-Host ""
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Assessment completed in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds — manual takes ~1 hour     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  WHAT AUTOMATION CANNOT DO (the remaining ~15%)                 ║" -ForegroundColor Yellow
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║  • Cannot assess business risk of specific patches              ║" -ForegroundColor Yellow
Write-Host "║  • Cannot recommend wave grouping based on dependencies         ║" -ForegroundColor Yellow
Write-Host "║  • Cannot predict patch conflicts from historical data          ║" -ForegroundColor Yellow
Write-Host "║  • Cannot adjust schedule based on business calendar            ║" -ForegroundColor Yellow
Write-Host "║  • Cannot write change advisory board (CAB) justification       ║" -ForegroundColor Yellow
Write-Host "║  → Patch Risk Agent adds intelligence + risk assessment         ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
#endregion
