<#
.SYNOPSIS
    Deterministic Alert Monitoring Automation (~70% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for alert monitoring.
    Lists active alerts, shows alert rules, demonstrates rule-based severity mapping,
    and auto-creates GLPI tickets for fired alerts.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Alert rules resource group: rg-opsauto-sc
    Run from: Any machine with az CLI authenticated
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$ResourceGroup = "rg-arcbox-itpro"
$AlertRulesRG = "rg-opsauto-sc"
$GlpiUrl = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
$GlpiClientId = "YOUR_CLIENT_ID"
$GlpiClientSecret = "YOUR_CLIENT_SECRET"
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC ALERT MONITORING                         ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~70%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Checks: Active alerts, alert rules, severity mapping           ║" -ForegroundColor Cyan
Write-Host "║  Action: Auto-creates GLPI tickets when alerts fire             ║" -ForegroundColor Cyan
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

function Get-SeverityLabel {
    param([string]$Severity)
    switch ($Severity) {
        "0" { "Critical" }
        "1" { "Error" }
        "2" { "Warning" }
        "3" { "Informational" }
        "4" { "Verbose" }
        "Sev0" { "Critical" }
        "Sev1" { "Error" }
        "Sev2" { "Warning" }
        "Sev3" { "Informational" }
        default { $Severity }
    }
}

function Get-GlpiSessionToken {
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
        [int]$Urgency = 3,
        [hashtable]$Auth
    )
    if (-not $Auth) {
        Write-Status "No GLPI auth — skipping ticket creation" -Level "Warn"
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
                type    = 1
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

#region Step 1: List Active Azure Monitor Alerts
Write-Host "━━━ Step 1: Current Azure Monitor Alerts ━━━" -ForegroundColor White
$activeAlerts = @()
try {
    $alertsResult = az monitor alert list --resource-group $ResourceGroup 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Try the newer command
        $alertsResult = az monitor metrics alert list --resource-group $ResourceGroup 2>&1
    }

    if ($LASTEXITCODE -eq 0) {
        $alertsData = $alertsResult | ConvertFrom-Json
        if ($alertsData -and $alertsData.Count -gt 0) {
            Write-Status "Found $($alertsData.Count) metric alert rules in $ResourceGroup" -Level "Info"
            foreach ($alert in $alertsData) {
                $severity = Get-SeverityLabel $alert.severity
                $enabled = if ($alert.enabled) { "Enabled" } else { "Disabled" }
                $name = $alert.name
                $level = if ($severity -eq "Critical") { "Critical" } elseif ($severity -eq "Error") { "Warn" } else { "Info" }
                Write-Status "$name | Severity: $severity | $enabled" -Level $level
                $activeAlerts += $alert
            }
        }
        else {
            Write-Status "No metric alert rules found in $ResourceGroup" -Level "Info"
        }
    }
    else {
        Write-Status "Alert list command not available for this resource group" -Level "Info"
    }
}
catch {
    Write-Status "Error querying alerts: $_" -Level "Warn"
}

# Also check for fired alerts using Resource Graph
Write-Host ""
Write-Host "  Checking for recently fired alerts..." -ForegroundColor Gray
try {
    $firedQuery = @"
alertsmanagementresources
| where type == 'microsoft.alertsmanagement/alerts'
| where properties.essentials.monitorCondition == 'Fired'
| where properties.essentials.startDateTime > ago(24h)
| project name, properties.essentials.severity, properties.essentials.monitorCondition,
          properties.essentials.startDateTime, properties.essentials.targetResource
| order by properties_essentials_startDateTime desc
"@
    $firedResult = az graph query -q $firedQuery --first 20 2>&1
    if ($LASTEXITCODE -eq 0) {
        $firedData = ($firedResult | ConvertFrom-Json).data
        if ($firedData -and $firedData.Count -gt 0) {
            Write-Status "Found $($firedData.Count) fired alerts in last 24 hours" -Level "Warn"
            Write-Host ""
            Write-Host "  ┌──────────────────────────────────┬──────────┬──────────────────────────────┐" -ForegroundColor White
            Write-Host "  │ Alert Name                       │ Severity │ Target Resource              │" -ForegroundColor White
            Write-Host "  ├──────────────────────────────────┼──────────┼──────────────────────────────┤" -ForegroundColor White

            foreach ($fired in $firedData) {
                $aName = $fired.name.PadRight(32).Substring(0, 32)
                $aSev = (Get-SeverityLabel $fired.properties_essentials_severity).PadRight(8).Substring(0, 8)
                $aTarget = if ($fired.properties_essentials_targetResource) {
                    $fired.properties_essentials_targetResource.Split("/")[-1].PadRight(28).Substring(0, 28)
                } else { "unknown".PadRight(28) }
                $color = switch ($fired.properties_essentials_severity) {
                    "Sev0" { "Red" }
                    "Sev1" { "Red" }
                    "Sev2" { "Yellow" }
                    default { "Gray" }
                }
                Write-Host "  │ $aName │ $aSev │ $aTarget │" -ForegroundColor $color
            }
            Write-Host "  └──────────────────────────────────┴──────────┴──────────────────────────────┘" -ForegroundColor White
        }
        else {
            Write-Status "No fired alerts in last 24 hours" -Level "Pass"
        }
    }
}
catch {
    Write-Status "Error querying fired alerts: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Step 2: Show Alert Rules (Scheduled Queries)
Write-Host "━━━ Step 2: Scheduled Query Alert Rules ━━━" -ForegroundColor White
try {
    $sqRules = az monitor scheduled-query list --resource-group $AlertRulesRG 2>&1
    if ($LASTEXITCODE -eq 0) {
        $sqData = $sqRules | ConvertFrom-Json
        if ($sqData -and $sqData.Count -gt 0) {
            Write-Status "Found $($sqData.Count) scheduled query alert rules in $AlertRulesRG" -Level "Pass"
            Write-Host ""
            Write-Host "  ┌──────────────────────────────────────────┬──────────┬──────────┬──────────┐" -ForegroundColor White
            Write-Host "  │ Rule Name                                │ Severity │ Enabled  │ Freq     │" -ForegroundColor White
            Write-Host "  ├──────────────────────────────────────────┼──────────┼──────────┼──────────┤" -ForegroundColor White

            foreach ($rule in $sqData) {
                $rName = $rule.name.PadRight(40).Substring(0, 40)
                $rSev = (Get-SeverityLabel $rule.severity).PadRight(8).Substring(0, 8)
                $rEnabled = if ($rule.enabled) { "Yes".PadRight(8) } else { "No".PadRight(8) }
                $rFreq = if ($rule.evaluationFrequency) { $rule.evaluationFrequency.PadRight(8).Substring(0, 8) } else { "—".PadRight(8) }
                Write-Host "  │ $rName │ $rSev │ $rEnabled │ $rFreq │" -ForegroundColor White
            }
            Write-Host "  └──────────────────────────────────────────┴──────────┴──────────┴──────────┘" -ForegroundColor White
        }
        else {
            Write-Status "No scheduled query rules found in $AlertRulesRG" -Level "Info"
        }
    }
    else {
        Write-Status "Scheduled query list failed — ensure resource group $AlertRulesRG exists" -Level "Warn"
    }
}
catch {
    Write-Status "Error listing scheduled query rules: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Step 3: Rule-Based Severity Mapping
Write-Host "━━━ Step 3: Rule-Based Severity → GLPI Urgency Mapping ━━━" -ForegroundColor White
Write-Host ""
Write-Host "  This is the DETERMINISTIC mapping — no AI interpretation:" -ForegroundColor Gray
Write-Host ""
Write-Host "  ┌───────────────────┬────────────────┬────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ Azure Severity    │ GLPI Urgency   │ Action                             │" -ForegroundColor White
Write-Host "  ├───────────────────┼────────────────┼────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │ Sev0 (Critical)   │ 5 (Very High)  │ Auto-create P1 ticket + page       │" -ForegroundColor Red
Write-Host "  │ Sev1 (Error)      │ 4 (High)       │ Auto-create P2 ticket              │" -ForegroundColor Yellow
Write-Host "  │ Sev2 (Warning)    │ 3 (Medium)     │ Auto-create P3 ticket              │" -ForegroundColor White
Write-Host "  │ Sev3 (Info)       │ 2 (Low)        │ Log only — no ticket               │" -ForegroundColor Gray
Write-Host "  │ Sev4 (Verbose)    │ 1 (Very Low)   │ Log only — no ticket               │" -ForegroundColor DarkGray
Write-Host "  └───────────────────┴────────────────┴────────────────────────────────────┘" -ForegroundColor White
Write-Host ""
Write-Status "This mapping is static — same alert always maps to same urgency" -Level "Info"
Write-Status "Cannot adjust urgency based on context (e.g., production vs. dev)" -Level "Info"
Write-Host ""
#endregion

#region Step 4: Demo Auto-Ticket Creation
Write-Host "━━━ Step 4: Demonstrating Auto-Ticket Creation ━━━" -ForegroundColor White

$glpiAuth = Get-GlpiSessionToken

$sampleAlert = @{
    Name     = "High CPU on ArcBox-Win2K22"
    Severity = "Sev1"
    Target   = "ArcBox-Win2K22"
    Time     = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
}

$ticketTitle = "[ALERT] $($sampleAlert.Name) — $(Get-SeverityLabel $sampleAlert.Severity)"
$ticketDesc = @"
<p><b>Azure Monitor Alert → GLPI Ticket (Auto-Created)</b></p>
<p><b>Alert:</b> $($sampleAlert.Name)</p>
<p><b>Severity:</b> $($sampleAlert.Severity) ($(Get-SeverityLabel $sampleAlert.Severity))</p>
<p><b>Target:</b> $($sampleAlert.Target)</p>
<p><b>Fired at:</b> $($sampleAlert.Time)</p>
<hr>
<p><i>This ticket was auto-created by rule-based alert-to-ticket mapping.</i></p>
<p><i>No AI interpretation — just deterministic severity → urgency mapping.</i></p>
"@

# Map severity to GLPI urgency
$glpiUrgency = switch ($sampleAlert.Severity) {
    "Sev0" { 5 }
    "Sev1" { 4 }
    "Sev2" { 3 }
    default { 2 }
}

$ticket = New-GlpiTicket -Title $ticketTitle -Description $ticketDesc -Urgency $glpiUrgency -Auth $glpiAuth
if ($ticket) {
    Write-Status "Created sample GLPI ticket #$($ticket.id): $ticketTitle" -Level "Pass"
    Write-Status "Urgency mapped: $($sampleAlert.Severity) → GLPI urgency $glpiUrgency" -Level "Pass"
}
else {
    Write-Status "Would create ticket: $ticketTitle (GLPI not reachable)" -Level "Info"
    Write-Status "Would map: $($sampleAlert.Severity) → GLPI urgency $glpiUrgency" -Level "Info"
}
Write-Host ""
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Alert check completed in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds                           ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  WHAT AUTOMATION CANNOT DO (the remaining ~30%)                 ║" -ForegroundColor Yellow
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║  • Cannot correlate multiple alerts into a single incident      ║" -ForegroundColor Yellow
Write-Host "║  • Cannot determine root cause from alert patterns              ║" -ForegroundColor Yellow
Write-Host "║  • Cannot suggest specific remediation steps                    ║" -ForegroundColor Yellow
Write-Host "║  • Cannot adjust severity based on business context             ║" -ForegroundColor Yellow
Write-Host "║  • Cannot suppress duplicate/flapping alerts intelligently      ║" -ForegroundColor Yellow
Write-Host "║  → SRE Agent adds correlation + context + remediation           ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
#endregion
