<#
.SYNOPSIS
    Creates sample tickets in GLPI to demonstrate the ticket-driven-remediation skill.

.DESCRIPTION
    Seeds GLPI with 3-4 realistic Wintel Ops tickets that the AI agent can read,
    investigate, and resolve. Run this BEFORE invoking the ticket-driven-remediation skill.

.PARAMETER GlpiUrl
    Base URL of the GLPI instance. Default: http://glpi-opsauto-demo.swedencentral.azurecontainer.io

.PARAMETER ClientId
    OAuth2 Client ID from GLPI Setup > OAuth Clients.

.PARAMETER ClientSecret
    OAuth2 Client Secret.

.PARAMETER Username
    GLPI username. Default: glpi

.PARAMETER Password
    GLPI admin password.

.EXAMPLE
    .\seed-glpi-tickets.ps1 -ClientId "abc123" -ClientSecret "secret456" -Password "MyPass!"
#>

param(
    [string]$GlpiUrl = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io",
    [Parameter(Mandatory)][string]$ClientId,
    [Parameter(Mandatory)][string]$ClientSecret,
    [string]$Username = "glpi",
    [Parameter(Mandatory)][string]$Password
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== GLPI Ticket Seeder ===" -ForegroundColor Cyan
Write-Host "URL: $GlpiUrl"
Write-Host ""

# --- Step 1: Get OAuth2 Token ---
Write-Host "[1/2] Authenticating to GLPI..." -ForegroundColor Yellow
$tokenBody = @{
    grant_type    = "password"
    client_id     = $ClientId
    client_secret = $ClientSecret
    username      = $Username
    password      = $Password
    scope         = "api"
}

try {
    $tokenResp = Invoke-RestMethod -Uri "$GlpiUrl/api.php/token" -Method Post -Body $tokenBody
    $token = $tokenResp.access_token
    Write-Host "  Token acquired." -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Failed to authenticate. Check credentials." -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
}

# --- Step 2: Create sample tickets ---
Write-Host "[2/2] Creating sample tickets..." -ForegroundColor Yellow

$tickets = @(
    @{
        name     = "[CMDB] ArcBox-Win2K25 OS mismatch — GLPI shows Windows Server 2022, actual is 2025"
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

$createdTickets = @()

foreach ($ticket in $tickets) {
    try {
        $body = $ticket | ConvertTo-Json -Depth 5
        $resp = Invoke-RestMethod -Uri "$GlpiUrl/api.php/v2.2/Assistance/Ticket" -Method Post -Headers $headers -Body $body
        $ticketId = $resp.id
        $createdTickets += [PSCustomObject]@{
            ID       = $ticketId
            Title    = $ticket.name
            Priority = $ticket.priority
            URL      = "$GlpiUrl/front/ticket.form.php?id=$ticketId"
        }
        Write-Host "  Created ticket #$ticketId : $($ticket.name)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR creating ticket: $($ticket.name)" -ForegroundColor Red
        Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
    }
}

# --- Summary ---
Write-Host "`n=== Tickets Created ===" -ForegroundColor Cyan
$createdTickets | Format-Table -AutoSize

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Verify tickets in GLPI UI: $GlpiUrl/front/ticket.php"
Write-Host "  2. Invoke the ticket-driven-remediation skill in Copilot CLI:"
Write-Host ""
Write-Host '  copilot -p "Use the /ticket-driven-remediation skill. Read open tickets from GLPI at GLPI_URL using client_id=CLIENT_ID, client_secret=CLIENT_SECRET, username=glpi, password=PASSWORD. Investigate each ticket and update with findings." --allow-all-tools' -ForegroundColor White
Write-Host ""
