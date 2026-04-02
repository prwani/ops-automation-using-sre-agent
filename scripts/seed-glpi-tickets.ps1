<#
.SYNOPSIS
    Creates sample tickets in GLPI to demonstrate the ticket-driven-remediation skill.

.DESCRIPTION
    Seeds GLPI with 4 realistic Wintel Ops tickets that the AI agent can read,
    investigate, and resolve. Run this BEFORE invoking the ticket-driven-remediation skill.

    Authentication: Tries OAuth2 first. If that fails (e.g. GLPI build doesn't
    support it), automatically falls back to the legacy REST API with HTTP Basic auth.

.PARAMETER GlpiUrl
    Base URL of the GLPI instance. Default: http://glpi-opsauto-demo.swedencentral.azurecontainer.io

.PARAMETER ClientId
    OAuth2 Client ID from GLPI Setup > OAuth Clients. Optional — only needed for OAuth2.

.PARAMETER ClientSecret
    OAuth2 Client Secret. Optional — only needed for OAuth2.

.PARAMETER Username
    GLPI username. Default: glpi

.PARAMETER Password
    GLPI admin password. Default: glpi

.EXAMPLE
    # OAuth2 (if configured)
    .\seed-glpi-tickets.ps1 -ClientId "abc123" -ClientSecret "secret456" -Password "MyPass!"

.EXAMPLE
    # Legacy API (no OAuth2 needed — just username/password)
    .\seed-glpi-tickets.ps1 -Password "glpi"

.EXAMPLE
    # All defaults (glpi/glpi, legacy fallback)
    .\seed-glpi-tickets.ps1
#>

param(
    [string]$GlpiUrl      = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io",
    [string]$ClientId     = "",
    [string]$ClientSecret = "",
    [string]$Username     = "glpi",
    [string]$Password     = "glpi"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== GLPI Ticket Seeder ===" -ForegroundColor Cyan
Write-Host "URL: $GlpiUrl"
Write-Host ""

# ── Authentication ───────────────────────────────────────────────────────────
# Try OAuth2 first; fall back to legacy REST API if it fails.

$authMode   = $null   # "oauth2" or "legacy"
$authHeader = @{}

# --- Attempt 1: OAuth2 (if credentials supplied) ---
if ($ClientId -and $ClientSecret) {
    Write-Host "[Auth] Trying OAuth2..." -ForegroundColor Yellow
    try {
        $tokenResp = Invoke-RestMethod -Uri "$GlpiUrl/api.php/token" -Method Post -Body @{
            grant_type    = "password"
            client_id     = $ClientId
            client_secret = $ClientSecret
            username      = $Username
            password      = $Password
            scope         = "api"
        }
        $authHeader = @{
            "Authorization" = "Bearer $($tokenResp.access_token)"
            "Content-Type"  = "application/json"
        }
        $authMode = "oauth2"
        Write-Host "  OAuth2 token acquired." -ForegroundColor Green
    } catch {
        Write-Host "  OAuth2 failed: $($_.Exception.Message)" -ForegroundColor DarkYellow
        Write-Host "  Falling back to legacy API..." -ForegroundColor DarkYellow
    }
}

# --- Attempt 2: Legacy REST API (Basic auth → session token) ---
if (-not $authMode) {
    Write-Host "[Auth] Using legacy REST API (Basic auth)..." -ForegroundColor Yellow
    $base64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${Username}:${Password}"))
    try {
        $sessionResp = Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/initSession" `
            -Headers @{ "Authorization" = "Basic $base64"; "Content-Type" = "application/json" }
        $authHeader = @{
            "Session-Token" = $sessionResp.session_token
            "Content-Type"  = "application/json"
        }
        $authMode = "legacy"
        Write-Host "  Session token acquired." -ForegroundColor Green
    } catch {
        Write-Host "  Legacy API also failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  Check that GLPI is running and credentials are correct." -ForegroundColor Red
        exit 1
    }
}

# ── Helper: pick the right endpoint & body shape ─────────────────────────────
function New-GlpiTicket {
    param([hashtable]$Ticket)

    if ($authMode -eq "oauth2") {
        $uri  = "$GlpiUrl/api.php/v2.2/Assistance/Ticket"
        $body = $Ticket | ConvertTo-Json -Depth 5
    } else {
        $uri  = "$GlpiUrl/apirest.php/Ticket"
        $body = @{ input = $Ticket } | ConvertTo-Json -Depth 5
    }

    $resp = Invoke-RestMethod -Uri $uri -Method Post -Headers $authHeader -Body $body
    return $resp.id
}

# ── Ticket Definitions ───────────────────────────────────────────────────────
Write-Host "`n[Tickets] Creating sample tickets..." -ForegroundColor Yellow

$tickets = @(
    @{
        name     = "[CMDB] ArcBox-Win2K25 OS mismatch - GLPI shows Windows Server 2022, actual is 2025"
        content  = @"
<p>During monthly CMDB reconciliation, a mismatch was detected:</p>
<ul>
<li><b>Server:</b> ArcBox-Win2K25</li>
<li><b>GLPI CMDB record:</b> Windows Server 2022</li>
<li><b>Expected (from Azure Arc):</b> Windows Server 2025</li>
</ul>
<p>Please verify the actual OS version from Azure Arc and update the GLPI CMDB record accordingly.</p>
<p>Category: CMDB Update</p>
"@
        type     = 1  # Incident
        urgency  = 3  # Medium
        priority = 3
    },
    @{
        name     = "[Health] Investigate high CPU alert on ArcBox-Win2K22"
        content  = @"
<p>Azure Monitor fired a high CPU alert for server ArcBox-Win2K22.</p>
<ul>
<li><b>Alert:</b> CPU above 80% for 15 minutes</li>
<li><b>Server:</b> ArcBox-Win2K22</li>
<li><b>Time:</b> Last hour</li>
</ul>
<p>Please investigate current CPU, memory, and disk usage. Check if any runaway processes or services are causing the spike. Report findings.</p>
"@
        type     = 1
        urgency  = 4  # High
        priority = 4
    },
    @{
        name     = "[Security] Verify Defender for Endpoint agent on all Linux servers"
        content  = @"
<p>Monthly security review: Verify that Microsoft Defender for Endpoint (MDE) agent is installed and reporting on all Linux Arc-enrolled servers.</p>
<ul>
<li><b>Scope:</b> All Linux servers (Arcbox-Ubuntu-01, Arcbox-Ubuntu-02)</li>
<li><b>Check:</b> MDE.Linux extension installed, provisioning succeeded, heartbeat in last 24h</li>
</ul>
<p>Report any servers where MDE is missing or not reporting.</p>
"@
        type     = 1
        urgency  = 3
        priority = 3
    },
    @{
        name     = "[Compliance] Monthly MCSB compliance posture review"
        content  = @"
<p>Monthly compliance task: Run a compliance posture check against Microsoft Cloud Security Benchmark (MCSB) and report any failing controls.</p>
<ul>
<li><b>Scope:</b> All subscriptions</li>
<li><b>Standards:</b> MCSB, CIS, NIST (whatever is available)</li>
<li><b>Action:</b> List failing controls, count affected resources, prioritize P1-P4</li>
</ul>
<p>Attach the compliance summary to this ticket.</p>
"@
        type     = 1
        urgency  = 2  # Low
        priority = 2
    }
)

# ── Create Tickets ───────────────────────────────────────────────────────────
$createdTickets = @()

foreach ($ticket in $tickets) {
    try {
        $ticketId = New-GlpiTicket -Ticket $ticket
        $createdTickets += [PSCustomObject]@{
            ID       = $ticketId
            Title    = $ticket.name
            Priority = $ticket.priority
            URL      = "$GlpiUrl/front/ticket.form.php?id=$ticketId"
        }
        Write-Host "  Created #$ticketId : $($ticket.name)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR creating ticket: $($ticket.name)" -ForegroundColor Red
        Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
    }
}

# ── Cleanup: kill legacy session ─────────────────────────────────────────────
if ($authMode -eq "legacy") {
    try { Invoke-RestMethod -Uri "$GlpiUrl/apirest.php/killSession" -Headers $authHeader | Out-Null } catch {}
}

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host "`n=== Tickets Created ($authMode auth) ===" -ForegroundColor Cyan
$createdTickets | Format-Table -AutoSize

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify tickets in GLPI UI: $GlpiUrl/front/ticket.php"
Write-Host "  2. Invoke the ticket-driven-remediation skill in Copilot CLI:"
Write-Host ""
Write-Host '  copilot -p "Use the /ticket-driven-remediation skill. Connect to GLPI at ' -NoNewline
Write-Host "$GlpiUrl" -NoNewline -ForegroundColor White
Write-Host ' with username=glpi, password=glpi. Read all open tickets, investigate each one, update with findings, and solve." --allow-all-tools'
Write-Host ""
