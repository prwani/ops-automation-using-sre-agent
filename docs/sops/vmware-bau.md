# VMware / Hyper-V BAU Operations SOP

## Overview

| Field | Value |
|---|---|
| **Trigger** | Scheduled (weekly snapshots, monthly resource reports) or manual |
| **Scope** | All VMs visible via Azure Arc (VMware vSphere and Hyper-V) |
| **Automation tier** | Tier 1 (Arc + Log Analytics) + Tier 2 (Infra Analyst Agent) |
| **Owner** | Wintel SRE team |

---

## Tasks

### Task 1 — Snapshot / Checkpoint Cleanup (Weekly)

**Schedule:** Every Monday 03:00 UTC.

1. Query all Arc-enrolled VMs for attached snapshots/checkpoints via Azure Resource Graph.
2. Flag snapshots older than **7 days** in the weekly report.
3. **Auto-delete** snapshots older than **30 days** after confirmation:
   - Confirmation required via ITSM change record for production VMs.
   - Dev/Test snapshots auto-deleted without confirmation.
4. Log deletions to console output.

| Age | Action |
|---|---|
| 7–30 days | Report only (WARNING) |
| > 30 days | Auto-delete (with confirmation for prod) |

### Task 2 — VM Resource Utilization Report (Monthly)

**Schedule:** First Monday of the month, 04:00 UTC.

KQL queries run against Log Analytics workspace:

```kusto
Perf
| where TimeGenerated > ago(30d)
| where ObjectName == "Processor" and CounterName == "% Processor Time"
| summarize AvgCPU = avg(CounterValue) by Computer, bin(TimeGenerated, 1d)
| where AvgCPU > 70
| order by AvgCPU desc
```

Report includes:
- VMs consistently > 70% CPU (flagged for right-sizing).
- VMs with memory pressure (> 85% committed bytes).
- Disk throughput outliers.

### Task 3 — VM Health Check (Weekly)

**Schedule:** Every Sunday 02:00 UTC.

For each Arc-enrolled VM:

| Check | Method |
|---|---|
| Power state | Arc machine `status` field |
| Arc connectivity | Last heartbeat < 10 minutes |
| Defender agent status | Defender for Endpoint device API |
| Pending patches | Azure Update Manager — pending patch count |

VMs failing multiple checks flagged for review.

### Task 4 — Orphaned Resource Cleanup (Monthly)

**Schedule:** First Sunday of the month.

Identify via Azure Resource Graph:
- **Managed disks** not attached to a running VM.
- **NICs** not attached to a running VM.
- **Public IPs** not associated with any resource.

> ⚠️ **Report only — no auto-delete.** Orphaned resources are reported to the team via ITSM ticket for manual review and approval before any deletion.

---

## Output

- **Console** — task results logged to console output.
- **Weekly email summary** — sent to the Wintel SRE distribution list.
- **ITSM ticket** — created for any orphaned resources or snapshots requiring manual action.
