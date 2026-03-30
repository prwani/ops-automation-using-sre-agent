---
name: wintel-health-check-investigation
version: 1.0.0
description: Investigates Windows server health check failures and warnings reported by the automated health check system.
triggers:
  - Health check run completed with WARNING or CRITICAL status
  - Alert from Azure Monitor: disk, CPU, memory, or service threshold exceeded
  - User asks about a server health issue
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - glpi-create-ticket
sop_source: docs/sops/daily-health-check.md
---

# Wintel Health Check Investigation

## Context

This skill is invoked when an automated health check reports a WARNING or CRITICAL status on one or more Windows servers enrolled in Azure Arc.

## Investigation Steps

### Step 1 — Identify the affected server and check type

Query the health check script output or ask the user for context.

Note the `server_id`, failing checks, and any relevant details from the output.

### Step 2 — Check for active suppression rules

Check if the user has mentioned any known suppression rules for this server or check type.

If a suppression exists and hasn't expired, document it and do NOT create a ticket. Note the suppression in your response.

### Step 3 — Run live diagnostic

Run the appropriate diagnostic script via Arc Run Command based on the failing check:

**Disk:**
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_disk.ps1)
```
If disk >90%: Identify largest directories, check for log file accumulation, orphaned temp files.

**Services:**
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_services.ps1)
```
If service stopped: Check if restart resolves it. Check Event Log for crash reason.

**Event Log:**
```
RunAzCliReadCommands(server_id=<server_id>, script=scripts/check_eventlog.ps1, args="-HoursBack 6")
```
For errors found: Check Event ID, source, and message pattern.

**CPU/Memory:**
```
RunAzCliReadCommands: az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where Computer == '<server_name>' | where TimeGenerated > ago(24h) | where ObjectName in ('Processor', 'Memory') | summarize avg(CounterValue), max(CounterValue) by bin(TimeGenerated, 1h), CounterName" -o json
```
Identify if this is a spike or sustained high usage. Check for known batch job patterns in memories.

### Step 4 — Determine root cause and action

| Finding | Action |
|---|---|
| Disk >90% | Identify top consumers → create cleanup ticket if not batch job |
| Disk >95% | CRITICAL → immediate P1 ticket + notify on-call |
| Service stopped, restarts OK | Informational ticket, log for pattern |
| Service stopped, won't restart | P2 ticket → escalate to app team |
| CPU spike <2 hours | Log, check if known batch job (check memories) |
| CPU sustained >80% for 4+ hours | P3 ticket → capacity review |
| Event Log errors >20 | P3 ticket with error details |

### Step 5 — Create ticket if required

```
glpi-create-ticket(
  title="[Health Check] <server_name>: <issue summary>",
  description=<full diagnostic output>,
  priority=<P1/P2/P3/P4>,
  server_id=<server_id>
)
```

## Expected Output

- Root cause assessment (1-2 sentences)
- Action taken (auto-remediation or ticket link)
- Recommendation for memory creation if this is a known pattern
