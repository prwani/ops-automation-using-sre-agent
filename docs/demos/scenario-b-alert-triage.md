# Scenario B: Alert Triage & Ticket Creation

## Overview

| Field | Value |
|---|---|
| **Duration** | ~15 minutes |
| **Scope** | Spike CPU + stop service → real Azure Monitor alerts → SRE Agent triage → GLPI ticket |
| **Resource groups** | `rg-arcbox-itpro` (Arc VMs, Sweden Central), `rg-opsauto-sc` (alert rules, solution stack) |
| **Alert rules** | `alert-heartbeat-loss` (Sev 1), `alert-high-cpu` (Sev 2), `alert-low-disk` (Sev 2) |
| **ITSM** | GLPI — `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **Target VM** | ArcBox-Win2K22 (Windows Server 2022, application server role) |

This demo walks through the full alert-to-ticket lifecycle in two phases: first with deterministic automation (PowerShell scripts + alert rules), then with SRE Agent adding AI-driven correlation, context, and root-cause analysis.

## What the team does today

1. **Azure Monitor fires an alert** — an on-call engineer receives an email or Teams notification.
2. **Engineer triages manually** — opens the Azure portal, reads the alert, SSH/RDPs into the server, runs diagnostic commands.
3. **Engineer creates a ticket** — copies alert details into ManageEngine, assigns severity based on gut feel, writes a description from memory.
4. **Engineer escalates (maybe)** — if it looks serious, pings a senior engineer on Teams. No formal SLA tracking.

**Pain points:** ~20 minutes per alert, inconsistent severity assignment, no correlation between related alerts, ticket descriptions lack context, escalation is ad-hoc.

## Phase 1: Deterministic Automation (~70%)

### What it solves

| Capability | How |
|---|---|
| **Alert ingestion** | PowerShell script (`scripts/demo-b-alert-triage.ps1`) polls Azure Monitor, deduplicates alerts |
| **Rule-based severity mapping** | `alert-heartbeat-loss` (Sev 1) → P1, `alert-high-cpu` (Sev 2) → P2, `alert-low-disk` (Sev 2) → P2 |
| **Auto-create GLPI ticket** | POST to GLPI REST API with templated title and description |
| **Time-based escalation** | P1 not acknowledged within 15 min → page on-call via webhook |

### Step-by-step demo

#### Step 1: Trigger a CPU spike on ArcBox-Win2K22

Run an infinite loop that pegs one CPU core. This fires the `alert-high-cpu` rule within ~5 minutes.

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "spike-cpu" \
  --script "while (\$true) { [math]::Sqrt(12345) }" \
  --async-execution \
  --no-wait
```

> **Note:** `--async-execution` keeps the command running on the VM after the CLI returns. We clean it up at the end.

#### Step 2: Stop a critical Windows service

Stop the Windows Time service (`W32Time`). This simulates an unexpected service failure alongside the CPU spike.

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "stop-w32time" \
  --script "Stop-Service -Name W32Time -Force; Get-Service W32Time | Select-Object Name, Status"
```

Expected output:
```
Name    Status
----    ------
W32Time Stopped
```

#### Step 3: Show Azure Monitor firing alerts

Wait ~5 minutes for the alert evaluation cycle, then verify alerts are firing.

**Option A — Azure Portal:**

Navigate to **Monitor → Alerts** and filter by resource group `rg-arcbox-itpro`. You should see:

| Alert rule | Severity | Target | State |
|---|---|---|---|
| alert-high-cpu | Sev 2 | ArcBox-Win2K22 | Fired |

**Option B — Azure CLI:**

```bash
az monitor alert list \
  --resource-group rg-opsauto-sc \
  --output table
```

Or query specific fired alerts:

```bash
az monitor metrics alert show \
  --resource-group rg-opsauto-sc \
  --name alert-high-cpu \
  --output table
```

#### Step 4: Show alert rules with rule-based severity mapping

Show the audience how each alert rule maps to a ticket priority. This is the deterministic logic — no AI involved.

```bash
az monitor metrics alert list \
  --resource-group rg-opsauto-sc \
  --output table \
  --query "[].{Name:name, Severity:severity, Enabled:enabled}"
```

Expected mapping:

| Alert Rule | Azure Monitor Severity | GLPI Priority | GLPI Priority Value |
|---|---|---|---|
| `alert-heartbeat-loss` | Sev 1 (Critical) | P1 — Very High | 5 |
| `alert-high-cpu` | Sev 2 (High) | P2 — High | 4 |
| `alert-low-disk` | Sev 2 (High) | P2 — High | 4 |

This mapping is defined in `src/alerting/ingestor.py`:

```python
_SEVERITY_PRIORITY = {
    "critical": TicketPriority.P1,  # → GLPI priority 5
    "high":     TicketPriority.P2,  # → GLPI priority 4
}
```

#### Step 5: Show auto-created GLPI ticket with templated description

Open GLPI in a browser:

```
http://glpi-opsauto-demo.swedencentral.azurecontainer.io
```

Login: `glpi` / `glpi` (default admin). Navigate to **Assistance → Tickets**. You should see a new ticket:

| Field | Value |
|---|---|
| **Title** | `[HIGH] alert-high-cpu — ArcBox-Win2K22` |
| **Priority** | High (4) |
| **Status** | New |
| **Type** | Incident |
| **Description** | Templated: "Azure Monitor alert 'alert-high-cpu' fired on ArcBox-Win2K22. Severity: 2. Investigate CPU utilization." |

> **Tip:** Point out that the description is generic — it tells you *what* alerted but not *why*, and it doesn't mention the stopped service at all.

#### Step 6: Show escalation workflow

Explain the time-based escalation logic:

| Priority | SLA | Escalation |
|---|---|---|
| P1 (Very High) | 15 min to acknowledge | Page on-call engineer via webhook |
| P2 (High) | 30 min to acknowledge | Send Teams notification to ops channel |
| P3 (Medium) | 4 hours to acknowledge | Email ops team |

For the demo, show the escalation configuration in the script or describe the flow:

```
Alert fires → Script creates ticket → Timer starts
  → 15 min (P1) / 30 min (P2): no acknowledgement?
    → Escalation webhook fires → on-call paged
```

### What automation CANNOT do

This is the key transition slide to Phase 2. Call out these gaps explicitly:

| Gap | Example |
|---|---|
| **Cannot distinguish real alerts from noise** | CPU spike during a planned backup window still creates a P2 ticket |
| **Cannot correlate related alerts** | "CPU high + service stopped + app timeout" are three separate tickets, not one incident |
| **Cannot suggest remediation** | Ticket says "CPU high" but not "check process X" or "restart service Y" |
| **Cannot add context** | Ticket doesn't mention the server's role (app server), recent changes, or maintenance windows |
| **Templated descriptions only** | Every CPU alert gets the same boilerplate regardless of root cause |

---

## Phase 2: AI Adds the Remaining ~30%

### What SRE Agent solves

| Capability | How |
|---|---|
| **Alert correlation** | SRE Agent receives both alerts, recognizes they hit the same VM at the same time, and merges them into one incident |
| **Context enrichment** | Queries GLPI CMDB for server role |
| **Root-cause analysis** | Correlates CPU spike + stopped service → "W32Time service stopped, possibly causing dependent service failures and elevated CPU" |
| **Rich ticket descriptions** | Writes a contextual description with probable root cause, affected services, and suggested remediation |
| **Intelligent severity** | Adjusts priority based on server role (app server = higher impact) and correlation (two symptoms = more likely real) |

### Step-by-step demo

#### Step 1: SRE Agent receives the alert automatically

The alert ingestion script detects a critical/high-severity alert and forwards it to SRE Agent via webhook:

```python
# From src/alerting/ingestor.py — triggered automatically
payload = {
    "alert_id": "alert-high-cpu",
    "title": "High CPU on ArcBox-Win2K22",
    "severity": "high",
    "description": "CPU utilization exceeded threshold",
    "resource": "ArcBox-Win2K22",
    "timestamp": "2025-07-15T14:30:00Z",
}
# POST → SRE Agent webhook endpoint
```

No manual intervention required — the pipeline from Azure Monitor → script → SRE Agent is fully automated.

#### Step 2: Show the rich incident card in SRE Agent chat

Open the SRE Agent chat interface. The agent displays a correlated incident card:

```
🔴 Incident: ArcBox-Win2K22 — CPU Spike + Service Failure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Correlated alerts (2):
  • alert-high-cpu (Sev 2) — CPU at 98% for 5+ minutes
  • Service W32Time stopped unexpectedly

Server context:
  • Role: Application server (from GLPI CMDB)
  • OS: Windows Server 2022
  • Recent changes: None in last 7 days

Probable root cause:
  A runaway process is consuming 100% of one CPU core.
  The W32Time service was stopped (manually or by resource
  pressure), which may affect time-dependent services.

Suggested remediation:
  1. Identify the high-CPU process: Get-Process | Sort CPU -Desc
  2. Restart W32Time: Start-Service W32Time
  3. Verify dependent services are healthy
```

#### Step 3: SRE Agent correlates the CPU spike + service stop into one incident

Explain what the agent did behind the scenes:

1. **Received** the `alert-high-cpu` alert via webhook
2. **Queried Azure Monitor** for other recent alerts on `ArcBox-Win2K22`
3. **Found** the W32Time service was stopped (via Arc Run Command)
4. **Correlated** both symptoms into a single incident — instead of two separate tickets

#### Step 4: SRE Agent looks up server role and recent changes

The agent uses its custom tools:

```
Tool: glpi-query-cmdb
  Input: server_name = "ArcBox-Win2K22"
  Output: { role: "Application server", os: "Windows Server 2022",
            location: "Sweden Central", last_update: "2025-07-01" }
```

#### Step 5: SRE Agent creates GLPI ticket with contextual description + probable root cause

The agent calls `glpi-create-ticket` with an AI-generated description:

```
Tool: glpi-create-ticket
  Input:
    title: "ArcBox-Win2K22 — CPU spike + W32Time service stopped (correlated)"
    priority: "4"  (P2 — High)
    description: |
      ## Correlated Incident

      **Server:** ArcBox-Win2K22 (Application server, Windows Server 2022)
      **Time:** 2025-07-15 14:30 UTC
      **Source alerts:** alert-high-cpu (Sev 2), service-stopped (W32Time)

      ## Symptoms
      - CPU utilization at 98% sustained for 5+ minutes
      - Windows Time service (W32Time) found stopped

      ## Probable Root Cause
      A process is consuming 100% CPU on one core. The W32Time service
      was stopped — either manually or as a side-effect of resource pressure.
      No planned maintenance or suppression rules are active for this server.

      ## Recommended Actions
      1. Identify and terminate/throttle the high-CPU process
      2. Restart W32Time: `Start-Service W32Time`
      3. Verify time synchronization: `w32tm /query /status`
      4. Check dependent services and application health

      ## Context
      - Server role: Application server (source: GLPI CMDB)
      - Recent changes: None in the last 7 days
      - Maintenance window: None active
```

#### Step 6: Show side-by-side — templated ticket vs AI-enriched ticket

Open both tickets in GLPI and compare:

| Aspect | Phase 1 (Templated) | Phase 2 (AI-Enriched) |
|---|---|---|
| **Title** | `[HIGH] alert-high-cpu — ArcBox-Win2K22` | `ArcBox-Win2K22 — CPU spike + W32Time service stopped (correlated)` |
| **Alerts covered** | 1 (CPU only) | 2 (CPU + service stop, correlated) |
| **Description** | "Azure Monitor alert fired. Severity: 2. Investigate CPU." | Full root-cause analysis with symptoms, probable cause, and remediation steps |
| **Server context** | None | Role, OS, recent changes, maintenance status |
| **Remediation** | None | Step-by-step actions with exact commands |
| **Time to triage** | Engineer still needs to investigate | Engineer can act immediately |

> **Talking point:** "The first ticket tells you *what* happened. The second ticket tells you *why* it happened and *what to do about it*. That's the 30% AI adds."

### Clean up

Stop the CPU stress loop and restart the stopped service:

```bash
# Stop the CPU stress process
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "cleanup-cpu" \
  --script "Get-Process -Name powershell | Where-Object { \$_.CPU -gt 60 } | Stop-Process -Force; Write-Output 'CPU stress stopped'"
```

```bash
# Restart the Windows Time service
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "restart-w32time" \
  --script "Start-Service W32Time; Get-Service W32Time | Select-Object Name, Status"
```

Expected output:
```
Name    Status
----    ------
W32Time Running
```

```bash
# Verify CPU is back to normal
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "verify-cpu" \
  --script "Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 2 -MaxSamples 3"
```

> **Note:** Resolve the fired alerts in Azure Monitor and close the GLPI tickets to leave the environment clean for the next demo.

---

## Talking Points

| Point | Script |
|---|---|
| **The 70/30 split** | "Deterministic automation handles the predictable 70% — alert ingestion, severity mapping, ticket creation, escalation timers. AI handles the unpredictable 30% — correlation, context, root cause." |
| **Adapter pattern** | "This is GLPI — a production-grade ITSM. In your environment, we swap one adapter for ManageEngine. Same REST pattern, different URL." |
| **Real alerts, real tickets** | "Everything you just saw was live. Real Azure Monitor alerts, real Arc Run Commands, real GLPI tickets. Nothing mocked." |
| **Time savings** | "Manual triage: ~20 min per alert. With Phase 1: ~2 min (review templated ticket). With Phase 2: ~30 sec (read AI summary, confirm, act)." |
| **Memory system** | "If you tell the agent 'ignore CPU warnings on ArcBox-Win2K22 for 10 days', it stores a suppression memory and won't create tickets for that combination." |
| **Escalation** | "P1 tickets not acknowledged in 15 minutes automatically page the on-call engineer. No more 'I didn't see the email'." |

## Expected Output

By the end of this demo, the audience should see:

| Artifact | Location |
|---|---|
| Fired Azure Monitor alert (`alert-high-cpu`) | Azure Portal → Monitor → Alerts |
| Auto-created GLPI ticket (templated, Phase 1) | GLPI → Assistance → Tickets |
| AI-enriched GLPI ticket (correlated, Phase 2) | GLPI → Assistance → Tickets |
| SRE Agent incident card (chat) | SRE Agent chat interface |
| GLPI CMDB lookup result | SRE Agent tool output |
| Cleanup confirmation (CPU normal, W32Time running) | CLI output |
