---
name: compliance-investigation
version: 1.1.0
description: Investigates non-compliant controls found by Microsoft Defender for Cloud AND Azure Policy, correlates findings across both sources, and prioritizes remediation.
triggers:
  - Compliance score drops >5% in 24 hours
  - New high-severity compliance finding detected
  - Azure Policy reports non-compliant resources
  - User asks about compliance status
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - query-compliance-state
  - glpi-create-ticket
  - generate-compliance-report
sop_source: docs/sops/compliance-reporting.md
---

# Compliance Investigation

## Context

Investigates compliance across **two sources**:
1. **Microsoft Defender for Cloud** — regulatory compliance (CIS, NIST, ISO 27001, PCI DSS)
2. **Azure Policy** — custom and built-in policy assignments on Arc-enrolled servers

Both sources are queried and findings are correlated to provide a unified compliance view.

## Investigation Steps

### Step 1 — Get Defender for Cloud compliance state
```
az security regulatory-compliance-standards list --query "[].{Standard:name, State:state, PassedControls:passedControls, FailedControls:failedControls}" -o table
```

For specific failing controls:
```
query-compliance-state(subscription_id=<subscription_id>, standard="CIS")
```

Identify failing controls with highest impact (most affected servers × severity).

### Step 2 — Get Azure Policy compliance state
```
az policy state summarize --resource-group rg-arcbox-itpro --query "value[].{Policy:policyDefinitionName, NonCompliant:results.nonCompliantResources, Total:results.totalResources}" -o table
```

For detailed non-compliant resources:
```
az policy state list --resource-group rg-arcbox-itpro --filter "complianceState eq 'NonCompliant'" --query "[].{Resource:resourceId, Policy:policyDefinitionName, State:complianceState}" -o table
```

Check policy assignments and their definitions:
```
az policy assignment list --resource-group rg-arcbox-itpro --query "[].{Name:displayName, PolicyId:policyDefinitionId, Enforcement:enforcementMode}" -o table
```

### Step 3 — Correlate findings across both sources

Compare Defender for Cloud findings with Azure Policy findings:
- **Overlap**: Some Defender recommendations map to Azure Policy (e.g., CIS benchmarks use Guest Configuration policies). Note these to avoid duplicate remediation tickets.
- **Defender-only**: Findings from Defender vulnerability assessment, endpoint protection, etc.
- **Policy-only**: Custom organizational policies (naming conventions, tagging, allowed SKUs, required extensions).

Categorize:
| Source | Finding Type | Example |
|---|---|---|
| Defender + Policy | CIS/regulatory benchmarks | "Audit policy not configured" — found by both |
| Defender only | Threat protection, vulnerability | "Endpoint protection not installed" |
| Policy only | Organizational governance | "Required tag 'CostCenter' missing", "Allowed VM SKUs" |

### Step 4 — Spot-check on a server
```
RunAzCliReadCommands(server_id=<affected_server_id>, script=<control-specific check>)
```

Common checks:
- Audit policy: `auditpol /get /category:*`
- Windows Firewall: `Get-NetFirewallProfile | Select Name, Enabled | ConvertTo-Json`
- Password policy: `net accounts`
- Auto-update: `Get-ItemProperty HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU`
- Guest Configuration results: `az policy state list --resource <arc_server_id> --filter "policyDefinitionAction eq 'AuditIfNotExists'" -o table`
- Installed extensions: `az connectedmachine extension list --machine-name <name> --resource-group rg-arcbox-itpro -o table`

### Step 5 — Classify and prioritize

| Priority | Criteria | Action |
|---|---|---|
| **P1 Critical** | Defender Sev High + Policy NonCompliant on Tier 0 server | Immediate ticket + Teams alert |
| **P2 High** | CIS control failure affecting >3 servers | Ticket within 24h |
| **P3 Medium** | Policy non-compliance (tagging, naming) | Ticket for next sprint |
| **P4 Low** | Known exceptions (check `references/cis-exceptions.json`) | Document and skip |

### Step 6 — Create remediation tickets

For each finding (or grouped findings):
```
glpi-create-ticket(
  title="[Compliance] <Source>: <Control/Policy> — <N> servers affected",
  priority="<P1-P4>",
  description=<include: control ID, affected servers, remediation steps, risk, whether it's Defender or Policy finding>
)
```

### Step 7 — Generate unified compliance report
```
generate-compliance-report(subscription_id=<subscription_id>, format="html")
```

The report should include:
1. **Defender for Cloud**: Regulatory compliance % per standard (CIS, NIST, etc.)
2. **Azure Policy**: Non-compliant resource count per policy assignment
3. **Combined**: Total unique findings, deduplicated across both sources
4. **Trend**: Compare with previous report (if available from Cosmos DB)
5. **Top 10 actions**: Prioritized remediation items
