<#
.SYNOPSIS
    Deterministic Health Check Automation (~90% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for daily health checks.
    Queries Arc-enrolled VMs, runs threshold checks, creates GLPI tickets for critical findings.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Run from: ArcBox-Client VM (RDP) or any machine with az CLI authenticated
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$ResourceGroup = "rg-arcbox-itpro"
$GlpiUrl = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
$GlpiClientId = "YOUR_CLIENT_ID"
$GlpiClientSecret = "YOUR_CLIENT_SECRET"
$LogAnalyticsWorkspaceId = "f98fca75-7479-45e5-bf0c-87b56a9f9e8c"

# Thresholds
$DiskThresholdWarn = 80
$DiskThresholdCritical = 90
$CpuThresholdWarn = 75
$CpuThresholdCritical = 85
$MemThresholdWarn = 75
$MemThresholdCritical = 85

# Nested VM credentials (for Invoke-Command from ArcBox-Client)
$NestedUser = "arcdemo"
$NestedPass = ConvertTo-SecureString "JS123!!" -AsPlainText -Force
$NestedCred = New-Object System.Management.Automation.PSCredential($NestedUser, $NestedPass)
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC HEALTH CHECK AUTOMATION                  ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~90%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Checks: Disk, CPU, Memory, Services, Event Logs               ║" -ForegroundColor Cyan
Write-Host "║  Action: Auto-creates GLPI tickets for CRITICAL findings       ║" -ForegroundColor Cyan
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

function Get-GlpiSessionToken {
    <#
    .SYNOPSIS
        Authenticates to GLPI via OAuth2 and returns a session token.
    #>
    try {
        $tokenBody = @{
            grant_type    = "client_credentials"
            client_id     = $GlpiClientId
            client_secret = $GlpiClientSecret
            scope         = "write:helpdesk read:helpdesk"
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

function New-GlpiTicket {
    param(
        [string]$Title,
        [string]$Description,
        [int]$Urgency = 4,
        [hashtable]$Auth
    )
    if (-not $Auth) {
        Write-Status "No GLPI auth token — skipping ticket creation" -Level "Warn"
        return $null
    }
    try {
        $headers = @{
            "Authorization" = "Bearer $($Auth.AccessToken)"
            "Session-Token" = $Auth.SessionToken
            "Content-Type"  = "application/json"
        }
        $body = @{
            input = @{
                name    = $Title
                content = $Description
                urgency = $Urgency
                type    = 1  # Incident
            }
        } | ConvertTo-Json -Depth 5

        $response = Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/Ticket" `
            -Method Post -Headers $headers -Body $body
        return $response
    }
    catch {
        Write-Status "Failed to create GLPI ticket: $_" -Level "Warn"
        return $null
    }
}
#endregion

#region Step 1: Discover Arc-enrolled servers
Write-Host "━━━ Step 1: Discovering Arc-enrolled servers ━━━" -ForegroundColor White
$arcQuery = @"
resources
| where type == 'microsoft.hybridcompute/machines'
| where resourceGroup =~ '$ResourceGroup'
| project name, properties.osType, properties.status, location, id,
          properties.osName, properties.osVersion, properties.lastStatusChange
| order by name asc
"@

$servers = @()
try {
    $result = az graph query -q $arcQuery --first 100 2>&1
    if ($LASTEXITCODE -eq 0) {
        $parsed = $result | ConvertFrom-Json
        $servers = $parsed.data
        Write-Status "Found $($servers.Count) Arc-enrolled servers in $ResourceGroup" -Level "Pass"
        foreach ($s in $servers) {
            $status = $s.properties_status
            $statusColor = if ($status -eq "Connected") { "Pass" } else { "Warn" }
            Write-Status "$($s.name) | OS: $($s.properties_osType) | Status: $status" -Level $statusColor
        }
    }
    else {
        Write-Status "az graph query failed — ensure 'az extension add -n resource-graph'" -Level "Warn"
    }
}
catch {
    Write-Status "Error querying Azure Resource Graph: $_" -Level "Critical"
}
Write-Host ""
#endregion

#region Step 2: Run health checks per server
Write-Host "━━━ Step 2: Running health checks on each server ━━━" -ForegroundColor White

$findings = @()
$isArcBoxClient = (hostname) -match "ArcBox-Client"

foreach ($server in $servers) {
    $vmName = $server.name
    $osType = $server.properties_osType

    Write-Host ""
    Write-Host "  ┌─ Checking: $vmName ($osType) ─────────────────────" -ForegroundColor Cyan

    if ($osType -ne "Windows") {
        Write-Status "Skipping $vmName — Linux checks not in this demo" -Level "Info"
        Write-Host "  └──────────────────────────────────────────────────" -ForegroundColor Cyan
        continue
    }

    # Determine execution method
    $useInvokeCommand = $isArcBoxClient

    if ($useInvokeCommand) {
        #region Invoke-Command path (from ArcBox-Client)
        try {
            # Disk check
            Write-Status "Checking disk usage..." -Level "Info"
            $diskResult = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
                    [PSCustomObject]@{
                        Drive      = $_.DeviceID
                        SizeGB     = [math]::Round($_.Size / 1GB, 1)
                        FreeGB     = [math]::Round($_.FreeSpace / 1GB, 1)
                        UsedPct    = [math]::Round((($_.Size - $_.FreeSpace) / $_.Size) * 100, 1)
                    }
                }
            } -ErrorAction Stop

            foreach ($disk in $diskResult) {
                if ($disk.UsedPct -ge $DiskThresholdCritical) {
                    Write-Status "Disk $($disk.Drive) at $($disk.UsedPct)% (>$DiskThresholdCritical%) — $($disk.FreeGB) GB free" -Level "Critical"
                    $findings += [PSCustomObject]@{ Server=$vmName; Check="Disk"; Level="CRITICAL"; Detail="$($disk.Drive) at $($disk.UsedPct)%" }
                }
                elseif ($disk.UsedPct -ge $DiskThresholdWarn) {
                    Write-Status "Disk $($disk.Drive) at $($disk.UsedPct)% (>$DiskThresholdWarn%)" -Level "Warn"
                    $findings += [PSCustomObject]@{ Server=$vmName; Check="Disk"; Level="WARN"; Detail="$($disk.Drive) at $($disk.UsedPct)%" }
                }
                else {
                    Write-Status "Disk $($disk.Drive) at $($disk.UsedPct)% — OK" -Level "Pass"
                }
            }

            # CPU check
            Write-Status "Checking CPU usage..." -Level "Info"
            $cpuResult = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                $sample = Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 1
                [math]::Round($sample.CounterSamples[0].CookedValue, 1)
            } -ErrorAction Stop

            if ($cpuResult -ge $CpuThresholdCritical) {
                Write-Status "CPU at $cpuResult% (>$CpuThresholdCritical%)" -Level "Critical"
                $findings += [PSCustomObject]@{ Server=$vmName; Check="CPU"; Level="CRITICAL"; Detail="$cpuResult%" }
            }
            elseif ($cpuResult -ge $CpuThresholdWarn) {
                Write-Status "CPU at $cpuResult% (>$CpuThresholdWarn%)" -Level "Warn"
                $findings += [PSCustomObject]@{ Server=$vmName; Check="CPU"; Level="WARN"; Detail="$cpuResult%" }
            }
            else {
                Write-Status "CPU at $cpuResult% — OK" -Level "Pass"
            }

            # Memory check
            Write-Status "Checking memory usage..." -Level "Info"
            $memResult = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                $sample = Get-Counter '\Memory\% Committed Bytes In Use' -SampleInterval 1 -MaxSamples 1
                [math]::Round($sample.CounterSamples[0].CookedValue, 1)
            } -ErrorAction Stop

            if ($memResult -ge $MemThresholdCritical) {
                Write-Status "Memory at $memResult% (>$MemThresholdCritical%)" -Level "Critical"
                $findings += [PSCustomObject]@{ Server=$vmName; Check="Memory"; Level="CRITICAL"; Detail="$memResult%" }
            }
            elseif ($memResult -ge $MemThresholdWarn) {
                Write-Status "Memory at $memResult% (>$MemThresholdWarn%)" -Level "Warn"
                $findings += [PSCustomObject]@{ Server=$vmName; Check="Memory"; Level="WARN"; Detail="$memResult%" }
            }
            else {
                Write-Status "Memory at $memResult% — OK" -Level "Pass"
            }

            # Services check
            Write-Status "Checking stopped auto-start services..." -Level "Info"
            $stoppedServices = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } |
                    Select-Object Name, DisplayName, Status
            } -ErrorAction Stop

            if ($stoppedServices -and $stoppedServices.Count -gt 0) {
                foreach ($svc in $stoppedServices) {
                    Write-Status "Stopped auto-start service: $($svc.DisplayName) ($($svc.Name))" -Level "Warn"
                }
                $findings += [PSCustomObject]@{ Server=$vmName; Check="Services"; Level="WARN"; Detail="$($stoppedServices.Count) stopped auto-start services" }
            }
            else {
                Write-Status "All auto-start services running" -Level "Pass"
            }

            # Event log check
            Write-Status "Checking critical/error events (last 24h)..." -Level "Info"
            $events = Invoke-Command -VMName $vmName -Credential $NestedCred -ScriptBlock {
                try {
                    Get-WinEvent -FilterHashtable @{
                        LogName   = 'System'
                        Level     = 1, 2  # Critical, Error
                        StartTime = (Get-Date).AddHours(-24)
                    } -MaxEvents 10 -ErrorAction SilentlyContinue |
                        Select-Object TimeCreated, LevelDisplayName, ProviderName, Message
                }
                catch { @() }
            } -ErrorAction Stop

            if ($events -and $events.Count -gt 0) {
                Write-Status "$($events.Count) critical/error events in last 24h:" -Level "Warn"
                foreach ($evt in $events) {
                    $truncMsg = if ($evt.Message.Length -gt 80) { $evt.Message.Substring(0, 80) + "..." } else { $evt.Message }
                    Write-Status "  $($evt.TimeCreated.ToString('HH:mm')) [$($evt.LevelDisplayName)] $($evt.ProviderName): $truncMsg" -Level "Info"
                }
                $findings += [PSCustomObject]@{ Server=$vmName; Check="EventLog"; Level="WARN"; Detail="$($events.Count) critical/error events" }
            }
            else {
                Write-Status "No critical/error events in last 24h" -Level "Pass"
            }
        }
        catch {
            Write-Status "Invoke-Command to $vmName failed: $_" -Level "Critical"
            $findings += [PSCustomObject]@{ Server=$vmName; Check="Connectivity"; Level="CRITICAL"; Detail="Cannot reach VM via Invoke-Command" }
        }
        #endregion
    }
    else {
        #region az CLI path (from any machine)
        Write-Status "Not on ArcBox-Client — using az CLI / Log Analytics for health data" -Level "Info"

        # Query heartbeat to confirm connectivity
        try {
            $heartbeatQuery = "Heartbeat | where Computer == '$vmName' | summarize LastHeartbeat = max(TimeGenerated) | project LastHeartbeat, AgeMinutes = datetime_diff('minute', now(), max_TimeGenerated)"
            $hbResult = az monitor log-analytics query -w $LogAnalyticsWorkspaceId --analytics-query $heartbeatQuery 2>&1
            if ($LASTEXITCODE -eq 0) {
                $hbData = $hbResult | ConvertFrom-Json
                if ($hbData -and $hbData.Count -gt 0) {
                    Write-Status "Last heartbeat received — server is reporting" -Level "Pass"
                }
                else {
                    Write-Status "No heartbeat data — server may be offline" -Level "Critical"
                    $findings += [PSCustomObject]@{ Server=$vmName; Check="Heartbeat"; Level="CRITICAL"; Detail="No heartbeat in Log Analytics" }
                }
            }
        }
        catch {
            Write-Status "Log Analytics query failed: $_" -Level "Warn"
        }

        # Query Perf data from Log Analytics
        try {
            $perfQuery = @"
Perf
| where Computer == '$vmName'
| where TimeGenerated > ago(1h)
| where ObjectName in ('LogicalDisk', 'Processor', 'Memory')
| summarize AvgValue = avg(CounterValue) by ObjectName, CounterName, InstanceName
| order by ObjectName, CounterName
"@
            $perfResult = az monitor log-analytics query -w $LogAnalyticsWorkspaceId --analytics-query $perfQuery 2>&1
            if ($LASTEXITCODE -eq 0) {
                $perfData = $perfResult | ConvertFrom-Json
                if ($perfData -and $perfData.Count -gt 0) {
                    Write-Status "Retrieved $($perfData.Count) perf counters from Log Analytics" -Level "Pass"
                    foreach ($counter in $perfData) {
                        $val = [math]::Round($counter.AvgValue, 1)
                        $counterDisplay = "$($counter.ObjectName)\$($counter.CounterName)"
                        if ($counter.InstanceName) { $counterDisplay += " ($($counter.InstanceName))" }

                        if ($counter.CounterName -match "% Free Space" -and $val -lt (100 - $DiskThresholdCritical)) {
                            Write-Status "$counterDisplay = $val%" -Level "Critical"
                            $findings += [PSCustomObject]@{ Server=$vmName; Check="Disk"; Level="CRITICAL"; Detail="$($counter.InstanceName) free=$val%" }
                        }
                        elseif ($counter.CounterName -match "% Processor Time" -and $counter.InstanceName -eq "_Total" -and $val -ge $CpuThresholdCritical) {
                            Write-Status "$counterDisplay = $val%" -Level "Critical"
                            $findings += [PSCustomObject]@{ Server=$vmName; Check="CPU"; Level="CRITICAL"; Detail="$val%" }
                        }
                        else {
                            Write-Status "$counterDisplay = $val" -Level "Info"
                        }
                    }
                }
                else {
                    Write-Status "No perf data in Log Analytics for $vmName" -Level "Warn"
                }
            }
        }
        catch {
            Write-Status "Perf query failed: $_" -Level "Warn"
        }
        #endregion
    }

    Write-Host "  └──────────────────────────────────────────────────" -ForegroundColor Cyan
}
Write-Host ""
#endregion

#region Step 3: Summary report
Write-Host "━━━ Step 3: Health Check Summary Report ━━━" -ForegroundColor White
Write-Host ""

$criticalCount = ($findings | Where-Object { $_.Level -eq "CRITICAL" }).Count
$warnCount = ($findings | Where-Object { $_.Level -eq "WARN" }).Count

Write-Host "  ┌──────────────────┬──────────┬──────────┬────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ Server           │ Check    │ Level    │ Detail                             │" -ForegroundColor White
Write-Host "  ├──────────────────┼──────────┼──────────┼────────────────────────────────────┤" -ForegroundColor White

if ($findings.Count -eq 0) {
    Write-Host "  │ (none)           │ —        │ —        │ All checks passed                  │" -ForegroundColor Green
}
else {
    foreach ($f in $findings) {
        $srvPad = $f.Server.PadRight(16)
        $chkPad = $f.Check.PadRight(8)
        $lvlPad = $f.Level.PadRight(8)
        $dtlPad = $f.Detail.PadRight(34).Substring(0, 34)
        $color = if ($f.Level -eq "CRITICAL") { "Red" } elseif ($f.Level -eq "WARN") { "Yellow" } else { "Green" }
        Write-Host "  │ $srvPad │ $chkPad │ $lvlPad │ $dtlPad │" -ForegroundColor $color
    }
}
Write-Host "  └──────────────────┴──────────┴──────────┴────────────────────────────────────┘" -ForegroundColor White
Write-Host ""
Write-Host "  Total findings: $($findings.Count) ($criticalCount critical, $warnCount warnings)" -ForegroundColor $(if ($criticalCount -gt 0) { "Red" } elseif ($warnCount -gt 0) { "Yellow" } else { "Green" })
Write-Host ""
#endregion

#region Step 4: Auto-create GLPI tickets for critical findings
if ($criticalCount -gt 0) {
    Write-Host "━━━ Step 4: Auto-creating GLPI tickets for CRITICAL findings ━━━" -ForegroundColor White

    $glpiAuth = Get-GlpiSessionToken
    $criticalFindings = $findings | Where-Object { $_.Level -eq "CRITICAL" }

    foreach ($cf in $criticalFindings) {
        $ticketTitle = "[AUTO] Health Check CRITICAL: $($cf.Server) - $($cf.Check)"
        $ticketDesc = @"
<p><b>Automated Health Check Finding</b></p>
<p><b>Server:</b> $($cf.Server)</p>
<p><b>Check:</b> $($cf.Check)</p>
<p><b>Level:</b> CRITICAL</p>
<p><b>Detail:</b> $($cf.Detail)</p>
<p><b>Detected at:</b> $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')</p>
<hr>
<p><i>Auto-generated by deterministic health check automation.</i></p>
"@
        $ticket = New-GlpiTicket -Title $ticketTitle -Description $ticketDesc -Urgency 5 -Auth $glpiAuth
        if ($ticket) {
            Write-Status "Created GLPI ticket #$($ticket.id): $ticketTitle" -Level "Pass"
        }
        else {
            Write-Status "Would create ticket: $ticketTitle (GLPI not reachable)" -Level "Info"
        }
    }
    Write-Host ""
}
else {
    Write-Host "━━━ Step 4: No CRITICAL findings — no tickets needed ━━━" -ForegroundColor Green
    Write-Host ""
}
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime
$elapsedStr = "{0:mm\:ss}" -f $elapsed

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Completed in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds — manual process takes 30-45 minutes    ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  WHAT AUTOMATION CANNOT DO (the remaining ~10%)                 ║" -ForegroundColor Yellow
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║  • Cannot interpret WHY thresholds are breached                 ║" -ForegroundColor Yellow
Write-Host "║  • Cannot spot trends (e.g., disk filling 2GB/day)             ║" -ForegroundColor Yellow
Write-Host "║  • Cannot correlate issues across servers                       ║" -ForegroundColor Yellow
Write-Host "║  • Cannot recommend specific remediation steps                  ║" -ForegroundColor Yellow
Write-Host "║  • Cannot assess business impact of findings                    ║" -ForegroundColor Yellow
Write-Host "║  → This is where the SRE Agent adds value                      ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
#endregion
