---
name: patch-validation
version: 1.0.0
description: Validates server health before and after Windows patch deployment. Assesses rollback need.
triggers:
  - Patch deployment completed (success or failure)
  - Pre-patch validation required before maintenance window
  - User requests post-patch verification
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - glpi-create-ticket
sop_source: docs/sops/windows-patching.md
---

# Patch Validation

## Pre-Patch Validation

Run before any patch deployment:

### Check 1 — Disk space (>20% free required)
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_disk.ps1)
```
**Block if** C: drive free < 20%.

### Check 2 — Active incidents
```
glpi-query-cmdb(server_name=<server_name>)
```
Check for open P1/P2 incidents. **Block if** open critical incident exists.

### Check 3 — Services baseline
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_services.ps1)
```
Record pre-patch service state as baseline.

## Post-Patch Validation

Run after patch deployment completes:

### Check 1 — Reboot completed
```
RunAzCliReadCommands(server_id=<server_id>, script="(Get-CimInstance Win32_OperatingSystem).LastBootUpTime | ConvertTo-Json")
```
Verify reboot time is after patch deployment start time.

### Check 2 — Services restored
Compare against pre-patch baseline. Any service that was Running and is now Stopped = **FAIL**.

### Check 3 — Event log clean
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_eventlog.ps1, args="-HoursBack 2")
```
Any Critical events post-patch = **WARN**. Crash dump events = **FAIL → rollback**.

### Check 4 — Missing patches cleared
```
RunAzCliReadCommands: az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Update | where TimeGenerated >= ago(7d) | where UpdateState == 'Needed' | where Computer == '<server_name>' | summarize MissingPatches=count(), CriticalCount=countif(MSRCSeverity == 'Critical') by Computer, Classification" -o json
```
Verify patched KBs now show as installed.

## Rollback Decision

**Auto-rollback NOT recommended** — create P1 ticket for human decision.

| Condition | Recommendation |
|---|---|
| Critical service down >15 min | Rollback — P1 ticket |
| Application owner request | Rollback — follow change process |
| Event log critical errors | Assess — may not require rollback |
| Health check clean | No rollback needed |
