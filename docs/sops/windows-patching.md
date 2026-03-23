# Monthly Windows Patching SOP

## Overview

| Field | Value |
|---|---|
| **Frequency** | Monthly — 2nd Tuesday (Patch Tuesday) + 72 hours staging |
| **Scope** | All Arc-enrolled Windows servers |
| **Automation tier** | Tier 1 (Update Manager) + Tier 2 (Patch Risk Agent) |
| **Owner** | Wintel SRE team |

---

## Phases

### Phase 1 — Pre-Patch Assessment (Patch Tuesday)

**Trigger:** Scheduled on the 2nd Tuesday of each month.

1. Query Azure Update Manager for all missing patches across enrolled servers.
2. Send patch list to **Patch Risk Agent** (Tier 2) for AI risk scoring:
   - Flags patches with known compatibility issues.
   - Identifies servers with custom applications requiring extra validation.
3. Generate approval request document and post to the change management channel.
4. Store assessment results in Cosmos DB `patch-assessments` container.

### Phase 2 — Wave 1: Dev/Test (Patch Tuesday + 24 hours)

**Scope:** All servers tagged `Environment: Dev` or `Environment: Test`.

1. Apply all Critical + Security patches via Azure Update Manager scheduled deployment.
2. Wait for deployment to complete (max 4 hours).
3. Run automated post-patch health check (see [Post-Patch Checks](#post-patch-checks)).
4. Update CMDB with new patch level.
5. Log wave results to Cosmos DB.

**Failure criteria:** If > 20% of dev/test servers fail health check, pause Wave 2 and raise P2 incident.

### Phase 3 — Wave 2: Non-Critical Production (Day 2–3)

**Scope:** Production servers tagged `Criticality: Standard`.

1. Apply patches in rolling batches of ≤ 10 servers at a time.
2. Validate each batch with health check before proceeding.
3. Create ITSM change tickets for audit trail (one per batch).
4. Update CMDB records post-patch.

**Failure criteria:** Any batch failure halts the wave; SRE Agent triggered.

### Phase 4 — Wave 3: Critical Production (Day 7+)

**Scope:** Servers tagged `Criticality: High` or `Criticality: Critical`.

**Prerequisites:**
- Wave 2 completed with < 5% failure rate.
- Minimum 5-day soak period since Wave 2.
- **Human approval required** via ITSM change record.

1. Coordinator confirms maintenance window with application owners.
2. Apply patches (single server at a time for Tier 0 systems).
3. Run full post-patch validation suite.
4. Rollback if criteria met (see [Rollback Criteria](#rollback-criteria)).

---

## Pre-Patch Checks

All checks must pass before patching any server:

| Check | Requirement |
|---|---|
| Backup / VM snapshot | Snapshot taken within 24 hours |
| Disk space | ≥ 20% free on C: drive |
| Active incidents | No open P1/P2 incidents for the server |
| Maintenance window | Confirmed and recorded in CMDB |
| Arc connectivity | Server heartbeat < 5 minutes old |

---

## Post-Patch Checks

Run automatically after each server patch:

| Check | Pass Criteria |
|---|---|
| Reboot completed | Server online and responding via Arc |
| All critical services running | `wuauserv`, `WinRM`, `EventLog`, `MpsSvc`, `MdCoreSvc` all Running |
| Event log clean | No new Critical events in System/Application log |
| Agent health | Defender agent online and reporting |
| Patch verification | Queried patch now shows as Installed in Update Manager |

---

## Rollback Criteria

Initiate rollback (VM snapshot restore) if any of the following occur within 15 minutes of patch completion:

- Any critical service is down for > 15 minutes.
- New Critical event IDs appear in System or Application event log.
- Application owner raises a P1 incident.
- Server fails to respond to Arc heartbeat for > 10 minutes.
