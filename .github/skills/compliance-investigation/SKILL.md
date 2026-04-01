---
name: compliance-investigation
description: Investigates non-compliant controls found by Microsoft Defender for Cloud AND Azure Policy, correlates findings across both sources, and prioritizes remediation. Use when asked about compliance, policy violations, CIS benchmarks, or regulatory standards.
---

# Compliance Investigation

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Environment

- Subscription: `31adb513-7077-47bb-9567-8e9d2a462bcf`
- Resource Group: `rg-arcbox-itpro`
- Region: `swedencentral`
- Log Analytics Workspace ID: `f98fca75-7479-45e5-bf0c-87b56a9f9e8c`
- Windows servers: `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL`
- Linux servers: `Arcbox-Ubuntu-01`, `Arcbox-Ubuntu-02`
- GLPI URL: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

## Step 1 — Query Defender for Cloud compliance (1 command for all standards)

```shell
az security regulatory-compliance-standards list --query "[].{Standard:name, State:state, PassedControls:passedControls, FailedControls:failedControls, SkippedControls:skippedControls}" -o table
```

For any standard with FailedControls > 0, drill into the failing controls:

```shell
az security regulatory-compliance-controls list --standard-name STANDARD_NAME --query "[?state=='Failed'].{Control:name, State:state, FailedAssessments:failedAssessments, Description:description}" -o table
```

Replace `STANDARD_NAME` with the standard name from the previous output (e.g., `CIS-Microsoft-Azure-Foundations-Benchmark-v2.0.0`).

## Step 2 — Query Azure Policy compliance (batched commands)

Run these three commands to get the full policy picture — they cover summary, details, and assignments in one pass:

**Summary of non-compliant policies:**

```shell
az policy state summarize --resource-group rg-arcbox-itpro -o table
```

**Non-compliant resources (1 query for all):**

```shell
az policy state list --resource-group rg-arcbox-itpro --filter "complianceState eq 'NonCompliant'" --query "[].{Resource:resourceId, Policy:policyDefinitionName}" -o table
```

**Active policy assignments:**

```shell
az policy assignment list --resource-group rg-arcbox-itpro --query "[].{Name:displayName, PolicyId:policyDefinitionId, Enforcement:enforcementMode}" -o table
```

## Step 3 — Correlate findings across both sources

After collecting results from Steps 1 and 2, categorize each finding:

| Category | Source | Example |
|----------|--------|---------|
| **Overlap** (Defender + Policy) | Both | CIS benchmark controls that map to Guest Configuration policies — deduplicate these |
| **Defender-only** | Defender for Cloud | Threat protection, vulnerability assessments, endpoint protection coverage |
| **Policy-only** | Azure Policy | Tagging requirements, allowed VM SKUs, naming conventions, required extensions |

Deduplicate: If the same issue appears in both Defender and Policy, count it once and note both sources.

**Only proceed to Step 4 if** the correlation reveals server-specific compliance failures that need on-machine verification. If all findings are Azure-level policy issues (tagging, SKUs, etc.), skip to Step 5.

## Step 4 — Spot-check compliance on affected servers (only if needed)

Only run this step for specific servers flagged in Steps 1–3. For each affected Windows server, run ONE combined diagnostic command that checks audit policy, firewall, and password policy together. Use `--async-execution true` so commands run in parallel across servers:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name compCheck --location swedencentral --async-execution true --script 'Write-Output "=== AUDIT POLICY ==="; auditpol /get /category:* | Select-String "No Auditing"; Write-Output "=== FIREWALL ==="; Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table -AutoSize; Write-Output "=== PASSWORD POLICY ==="; net accounts'
```

After dispatching commands for all affected servers, batch-read results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name compCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

## Step 5 — Classify and prioritize findings

Assign each finding a priority:

| Priority | Criteria | SLA |
|----------|----------|-----|
| **P1 Critical** | Defender severity High + Policy NonCompliant on production server; security controls disabled | Ticket immediately |
| **P2 High** | CIS control failure affecting 3+ servers; missing security extensions | Ticket within 24 hours |
| **P3 Medium** | Policy non-compliance for tagging, naming, or non-security config | Ticket for next sprint |
| **P4 Low** | Informational findings, known exceptions, low-severity Defender recommendations | Document only, no ticket |

## Step 6 — Summarize compliance posture

Present a compliance summary table:

| Source | Total Controls | Passed | Failed | Compliance % |
|--------|---------------|--------|--------|-------------|
| Defender for Cloud - CIS | _total_ | _pass_ | _fail_ | _pct_% |
| Defender for Cloud - NIST | _total_ | _pass_ | _fail_ | _pct_% |
| Azure Policy | _total_ | _compliant_ | _non-compliant_ | _pct_% |

Then list the top 10 findings by priority:

| # | Priority | Source | Finding | Affected Servers | Remediation |
|---|----------|--------|---------|-----------------|-------------|
| 1 | P1 | Defender+Policy | _description_ | _server list_ | _action_ |
| 2 | P2 | Defender | _description_ | _server list_ | _action_ |

## Step 7 — Create GLPI tickets for P1 and P2 findings

For each P1 or P2 finding (or group related findings into one ticket):

First, initialize a GLPI session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Compliance] SOURCE: CONTROL_NAME — N servers affected", "content": "Priority: P_LEVEL\nSource: Defender/Policy/Both\nAffected servers: SERVER_LIST\nFinding: DESCRIPTION\nRemediation: STEPS", "type": 1, "urgency": URGENCY_LEVEL, "priority": PRIORITY_LEVEL}}' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket'
```

Priority mapping: P1 → urgency=5,priority=5 | P2 → urgency=4,priority=4 | P3 → urgency=3,priority=3

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
