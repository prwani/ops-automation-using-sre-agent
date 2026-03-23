---
name: compliance-investigation
version: 1.0.0
description: Investigates non-compliant controls found by Microsoft Defender for Cloud and prioritizes remediation.
triggers:
  - Compliance score drops >5% in 24 hours
  - New high-severity compliance finding detected
  - User asks about compliance status
tools:
  - query-compliance-state
  - defender-get-security-alerts
  - arc-run-command
  - glpi-create-ticket
  - generate-compliance-report
sop_source: docs/sops/compliance-reporting.md
---

# Compliance Investigation

## Context

Uses Defender for Cloud regulatory compliance data to investigate specific non-compliant controls and prioritize remediation.

## Investigation Steps

### Step 1 — Get current compliance state
```
query-compliance-state(subscription_id=<subscription_id>, standard="CIS")
```

Identify failing controls with highest impact (most affected servers × severity).

### Step 2 — Understand the control requirement

For each top failing control, the description from Defender for Cloud includes the specific configuration requirement.

### Step 3 — Spot-check on a server
```
arc-run-command(server_id=<affected_server_id>, script=<control-specific remediation check>)
```

Common CIS checks:
- Audit policy settings: `auditpol /get /category:*`
- Windows Firewall: `Get-NetFirewallProfile | Select Name, Enabled | ConvertTo-Json`
- Password policy: `net accounts`
- Auto-update: `Get-ItemProperty HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU`

### Step 4 — Remediation guidance

Create remediation ticket with:
1. Control ID and description
2. Affected servers (count + names)
3. Specific remediation steps (PowerShell or GPO)
4. Estimated effort
5. Risk if not remediated

```
glpi-create-ticket(
  title="[Compliance] CIS Control <ID>: <control_name> — <N> servers affected",
  priority="P3",
  description=<full remediation guidance>
)
```

### Step 5 — Generate executive summary
```
generate-compliance-report(subscription_id=<subscription_id>, format="html")
```
