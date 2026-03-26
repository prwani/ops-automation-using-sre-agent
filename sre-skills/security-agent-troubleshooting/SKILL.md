---
name: security-agent-troubleshooting
version: 1.0.0
description: Diagnoses and remediates Microsoft Defender for Endpoint agent issues on Windows servers.
triggers:
  - Defender for Cloud alert: "Agent health issue detected"
  - Defender device health shows "not reporting" for >30 minutes
  - User reports Defender not working on a server
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - glpi-create-ticket
  - glpi-query-cmdb
sop_source: docs/sops/security-agent-troubleshooting.md
---

# Security Agent Troubleshooting

## Context

This skill handles Defender for Endpoint agent health issues. The agent (MdCoreSvc) must be running and reporting to maintain security coverage.

## Investigation Steps

### Step 1 — Get current agent health from Defender API

```
RunAzCliReadCommands(server_id=<server_id>)
```

Check: `onboardingStatus`, `healthStatus`, `lastSeen`, `agentVersion`.

### Step 2 — Run local agent check via Arc

```
RunAzCliReadCommands(server_id=<server_id>, script="""
$svc = Get-Service MdCoreSvc -ErrorAction SilentlyContinue
$mde = Get-Service "Sense" -ErrorAction SilentlyContinue
@{
  MdCoreSvc = if ($svc) { $svc.Status.ToString() } else { "NotFound" }
  SenseService = if ($mde) { $mde.Status.ToString() } else { "NotFound" }
  LastBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
} | ConvertTo-Json
""")
```

### Step 3 — Check network connectivity to Defender endpoints

```
RunAzCliReadCommands(server_id=<server_id>, script="""
$endpoints = @(
  "winatp-gw-eus.microsoft.com",
  "winatp-gw-neu.microsoft.com", 
  "us-v20.events.data.microsoft.com"
)
$results = $endpoints | ForEach-Object {
  $result = Test-NetConnection -ComputerName $_ -Port 443 -InformationLevel Quiet
  [PSCustomObject]@{ Endpoint = $_; Reachable = $result }
}
$results | ConvertTo-Json
""")
```

### Step 4 — Remediation by root cause

| Finding | Remediation |
|---|---|
| MdCoreSvc stopped | `RunAzCliWriteCommands(script="Restart-Service MdCoreSvc -Force")` |
| Sense stopped | `RunAzCliWriteCommands(script="Restart-Service Sense -Force")` |
| Network unreachable | Create P2 firewall change ticket in GLPI |
| Agent not onboarded | Run onboarding package via Arc Run Command |
| Agent version outdated | Trigger Update Manager patch for security updates |

### Step 5 — Verify remediation

Wait 5 minutes, then re-run Step 1. Confirm `healthStatus = "Active"` and `lastSeen` within last 10 minutes.

### Step 6 — Create ticket

Always create a ticket for audit purposes, even if auto-remediated:

```
glpi-create-ticket(
  title="[Security] Defender agent issue resolved: <server_name>",
  description=<full diagnostic + remediation steps taken>,
  priority="P3" (or P2 if network issue),
  server_id=<server_id>
)
```
