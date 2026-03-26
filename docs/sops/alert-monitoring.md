# Alert Monitoring SOP

## 1. Alert Sources

| Source | Description | Integration |
|---|---|---|
| **Azure Monitor Metrics** | CPU, memory, disk, and network threshold alerts on Arc-enrolled servers | Azure Monitor action group → Alert Ingestor function (every 5 min) |
| **Microsoft Defender for Cloud** | Security alerts (malware, brute-force, anomalous login, vulnerability findings) | Defender API polling via `src.alerting.ingestor` |
| **Heartbeat Loss** | Azure Arc connected-machine agent stops reporting (heartbeat gap > 10 min) | Log Analytics heartbeat query evaluated every 5 minutes |

## 2. Severity Mapping

| Condition | Priority | Rationale |
|---|---|---|
| Heartbeat loss > 10 minutes | **P1** | Server may be down or unreachable — immediate investigation required |
| Security alert — High severity | **P1** | Active threat or critical vulnerability exploitation |
| Security alert — Medium severity | **P2** | Potential threat requiring prompt investigation |
| CPU > 85 % sustained for 30 min | **P2** | Performance degradation affecting workloads |
| Disk free space < 10 % | **P2** | Risk of service outage due to disk exhaustion |
| Memory > 90 % sustained for 30 min | **P2** | Application instability risk |
| Disk free space < 20 % | **P3** | Proactive capacity warning |
| CPU > 70 % sustained for 2 hours | **P3** | Capacity review needed |
| Security alert — Low severity | **P3** | Informational security finding |
| Event Log critical errors > 20 in 6 hours | **P3** | Investigate application or OS stability |
| Patch compliance drift > 5 % | **P4** | Scheduled remediation during next patch window |

## 3. SLA Targets

| Priority | Acknowledge | Begin Investigation | Resolution Target |
|---|---|---|---|
| **P1** | 15 minutes | 30 minutes | 4 hours |
| **P2** | 1 hour | 2 hours | 8 hours (next business day) |
| **P3** | 4 hours | Next business day | 5 business days |
| **P4** | 1 business day | Planned sprint | Best effort |

## 4. Escalation Matrix

| Condition | Action |
|---|---|
| P1 not acknowledged within 15 min | **Page on-call engineer** via PagerDuty/Teams urgent notification |
| P1 not resolved within 2 hours | Escalate to **Infrastructure Manager** |
| P2 not acknowledged within 1 hour | **Email team lead** with alert summary |
| P2 not resolved within 8 hours | Escalate to **on-call engineer** |
| P3 not acknowledged within 4 hours | Auto-assign to **next available SRE** |
| Any P1 security alert | Simultaneously notify **Security Operations** team |

## 5. Ticket Creation Rules

Every actionable alert must result in a GLPI ticket. Include the following information:

### Required Ticket Fields

| Field | Value |
|---|---|
| **Title** | `[Alert] <server_name>: <alert summary>` |
| **Priority** | Mapped from severity table above (P1–P4) |
| **Category** | See category mapping below |
| **Description** | Alert source, timestamp, metric value / alert details, affected server FQDN, Azure resource ID |
| **Assigned Group** | `SRE-Operations` (P1/P2) or `SRE-Monitoring` (P3/P4) |
| **Server (CI)** | Link to CMDB configuration item for the affected server |

### GLPI Category Mapping

| Alert Type | GLPI Category |
|---|---|
| Heartbeat loss | `Infrastructure > Availability` |
| Security alert | `Security > Incident Response` |
| CPU / Memory threshold | `Infrastructure > Performance` |
| Disk threshold | `Infrastructure > Capacity` |
| Patch compliance | `Infrastructure > Patch Management` |
| Service health (stopped service) | `Infrastructure > Service Availability` |

## 6. De-duplication Rules

To prevent ticket flooding:

1. **Same alert + same server within 30 minutes** → Do **not** create a new ticket. Instead, append the new occurrence as a follow-up comment on the existing open ticket with the updated timestamp and metric value.
2. **Matching logic**: Alerts are considered duplicates when all of the following match:
   - Same `server_id`
   - Same `alert_type` (e.g., `cpu_threshold`, `heartbeat_loss`, `security_high`)
   - Existing ticket is still **Open** or **In Progress**
   - Previous alert occurred within the last **30 minutes**
3. **Escalation on repeat**: If the same alert fires **3 or more times** within 2 hours, automatically escalate the ticket priority by one level (e.g., P3 → P2).
4. **Resolution reset**: Once a ticket is resolved, subsequent alerts for the same server/type create a new ticket (the 30-minute window resets).

## 7. SRE Agent Integration

The **SRE Agent** provides AI-augmented triage for incoming alerts:

- The Alert Ingestor function (`functions/alert_ingestor`) polls for new alerts every 5 minutes and forwards high-priority alerts to the SRE Agent webhook.
- The SRE Agent automatically invokes the relevant **skill** (e.g., `wintel-health-check-investigation`, `security-agent-troubleshooting`) based on alert type.
- The agent runs diagnostics using `RunAzCliReadCommands`, checks for suppression memories, and determines whether a ticket is needed.
- For auto-remediable issues (e.g., restart a stopped service), the agent uses `RunAzCliWriteCommands` and logs the action.
- All agent decisions and diagnostic output are stored in Cosmos DB for audit and continuous improvement.

Refer to the [SRE Agent Setup Guide](../sre-agent-setup.md) and individual [SRE Skills](../sre-skills.md) for details on automated investigation workflows.
