# Scenario C: Security Agent Troubleshooting

## Overview

A Microsoft Defender for Cloud agent on an Azure Arc-enabled VM becomes unhealthy.
This scenario demonstrates a two-phase approach: deterministic automation handles the
common restart-and-verify path (~60% of cases), while the SRE Agent diagnoses and
resolves the remaining ~40% that require contextual reasoning.

| Item | Value |
|---|---|
| **Resource Group** | `rg-arcbox-itpro` |
| **Region** | Sweden Central |
| **VMs** | ArcBox-Win2K22 (Azure Arc-connected) |
| **Prerequisite** | Defender for Cloud enabled on the subscription |

---

## What the team does today

Manual process — typically ~30 minutes per incident:

1. Receive alert that Defender agent is unhealthy.
2. RDP into the affected VM.
3. Open `services.msc`, locate **Windows Defender Antivirus Service** (`WinDefend`).
4. Check the service status and attempt a restart.
5. If restart fails, review Event Viewer logs manually.
6. Escalate to the security team with a free-text description of what was tried.

**Pain points:** slow RDP access, no structured diagnostics, inconsistent escalation quality, repeated toil across servers.

---

## Phase 1: Deterministic Automation (~60%)

### What it solves

- Detects unhealthy Defender agent via Azure Policy compliance or Log Analytics heartbeat gaps.
- Executes a scripted restart through Azure Arc Run Commands (no RDP required).
- Auto-creates a GLPI ticket and escalates if the restart does not resolve the issue.

### Step-by-step demo

#### Step 1: Intentionally break Defender

Stop the Defender service on the Arc-enabled VM to simulate a failure:

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "BreakDefender" \
  --script "Stop-Service -Name WinDefend -Force" \
  --timeout-in-seconds 120
```

#### Step 2: Show Defender for Cloud detecting unhealthy agent

Open the Azure portal → **Defender for Cloud → Recommendations** and locate the
unhealthy agent assessment, or query programmatically:

```bash
az security assessment list \
  --resource-group rg-arcbox-itpro \
  --query "[?contains(displayName,'Defender')]"
```

#### Step 3: Show scripted remediation attempt

The automation workflow attempts to restart the service via Arc Run Command:

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "RestartDefender" \
  --script "Restart-Service -Name WinDefend" \
  --timeout-in-seconds 120
```

#### Step 4: Show auto-ticket created in GLPI if restart fails

If the restart does not restore a healthy status within the verification window,
the workflow automatically creates a GLPI ticket containing:

- VM name, resource group, and subscription
- Service status before and after restart attempt
- Timestamp and correlation ID

#### Step 5: Show auto-escalation workflow

The escalation workflow:

1. Re-checks service health after a configurable cooldown (default: 5 minutes).
2. If still unhealthy → updates the GLPI ticket severity to **High**.
3. Triggers the SRE Agent for Phase 2 diagnosis (see below).

### What automation CANNOT do

| Limitation | Why it matters |
|---|---|
| "Restart and hope" only fixes ~60% of failures | The other 40% have deeper root causes. |
| Cannot diagnose service dependency conflicts | e.g., a dependent service (`SecurityHealthService`) crashed first. |
| Cannot detect firewall or network changes | Outbound connectivity to `*.protection.outlook.com` may be blocked. |
| Cannot interpret Group Policy (GPO) conflicts | A new GPO may be disabling the service on startup. |
| Cannot read and correlate event logs | Event ID 7034 + recent KB update = likely cause, but scripts don't reason. |
| Same symptom → different root cause on different servers | A static runbook cannot branch on context it doesn't understand. |

---

## Phase 2: AI Adds the Remaining ~40%

### What SRE Agent solves

The SRE Agent brings **contextual reasoning** to the troubleshooting process. Instead
of a fixed script, it performs a structured diagnosis — gathering evidence, correlating
signals, and producing an actionable root-cause analysis.

### Step-by-step demo

#### 1. SRE Agent receives the "agent unhealthy" alert

The escalation workflow from Phase 1 triggers the SRE Agent with the alert payload:

```
VM: ArcBox-Win2K22
Alert: Defender agent unhealthy
Prior action: Restart-Service failed
GLPI Ticket: #12345
```

#### 2. SRE Agent loads security-agent-troubleshooting skill automatically

The agent matches the alert type to the `security-agent-troubleshooting` skill from
the skill library. This skill provides:

- A structured diagnostic checklist (service status, dependencies, logs, connectivity).
- Known failure patterns and their resolutions.
- Escalation criteria for cases requiring human intervention.

#### 3. SRE Agent checks service status, event logs, connectivity, disk space, recent changes

All checks are executed via **Arc Run Commands** — no RDP required:

```bash
# Service status and dependencies
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "DiagServiceStatus" \
  --script "Get-Service WinDefend, SecurityHealthService | Format-Table -AutoSize"

# Recent event log entries for the service
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "DiagEventLogs" \
  --script "Get-WinEvent -FilterHashtable @{LogName='System'; Id=7034,7036,7040; StartTime=(Get-Date).AddHours(-6)} | Format-List"

# Outbound connectivity to Defender endpoints
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "DiagConnectivity" \
  --script "Test-NetConnection -ComputerName wdcp.microsoft.com -Port 443"

# Disk space check
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "DiagDiskSpace" \
  --script "Get-PSDrive -PSProvider FileSystem | Format-Table Name, Used, Free -AutoSize"

# Recent Windows Updates
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "DiagRecentUpdates" \
  --script "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5"
```

#### 4. Show the agent interpreting event logs

The SRE Agent correlates the gathered evidence:

> **Agent analysis:**
> "Event ID 7034 — The Windows Defender Antivirus Service terminated unexpectedly.
> This occurred at 14:32 UTC, which correlates with KB5034441 installed 2 hours
> prior at 12:28 UTC. The update modified a shared DLL dependency used by
> WinDefend. SecurityHealthService also shows a restart at the same timestamp."

#### 5. SRE Agent proposes remediation or escalates with full context

Based on the diagnosis, the agent proposes a targeted fix:

> **Recommended remediation:**
> 1. Restart `WinDefend` and `SecurityHealthService` together (dependency ordering).
> 2. Force a Defender definition update: `Update-MpSignature -UpdateSource MicrosoftUpdateServer`.
> 3. If the issue recurs, rollback KB5034441 and notify the patching team.

If the agent determines the issue is beyond automated resolution (e.g., a GPO conflict
requiring policy changes), it escalates to the security team with:

- Full diagnostic summary
- Correlated timeline of events
- Recommended next steps for human review

### Clean up

Restart the Defender service to restore normal operation:

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "CleanupRestartDefender" \
  --script "Start-Service -Name WinDefend; Get-Service WinDefend"
```

Verify the service is running:

```bash
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --run-command-name "VerifyDefender" \
  --script "Get-Service WinDefend | Select-Object Status"
```

---

## Talking Points

- **"Why not just script everything?"** — Scripts handle known patterns. The 40% of
  failures that vary by context (event log correlation, dependency conflicts, recent
  changes) require reasoning, not branching.
- **"Is the AI making changes on its own?"** — The SRE Agent proposes remediation
  through a structured plan. Execution requires approval (human-in-the-loop) or
  policy-based auto-approval for low-risk actions.
- **"How does this integrate with existing ITSM?"** — GLPI tickets are created and
  updated automatically. The agent attaches diagnostics to the ticket so the
  escalation engineer has full context from the start.
- **Security posture:** Defender for Cloud compliance is continuously monitored.
  The automation reduces mean-time-to-remediation from ~30 minutes to < 5 minutes
  for the 60% case and provides structured diagnosis for the remaining 40%.

---

## Expected Output

| Phase | Output |
|---|---|
| **Phase 1 — Step 1** | Defender service stopped on ArcBox-Win2K22. |
| **Phase 1 — Step 2** | Defender for Cloud shows unhealthy assessment for the VM. |
| **Phase 1 — Step 3** | Arc Run Command executes `Restart-Service`. Service may or may not recover. |
| **Phase 1 — Step 4** | GLPI ticket created with VM details and restart attempt log. |
| **Phase 1 — Step 5** | Escalation triggers SRE Agent if service remains unhealthy. |
| **Phase 2 — Diagnosis** | SRE Agent collects service status, event logs, connectivity, disk, and recent changes. |
| **Phase 2 — Correlation** | Agent identifies: "Event ID 7034 correlates with KB update installed 2 hours ago." |
| **Phase 2 — Remediation** | Agent proposes targeted fix (restart + definition update) or escalates with full context. |
| **Clean up** | Defender service restarted and verified healthy. |
