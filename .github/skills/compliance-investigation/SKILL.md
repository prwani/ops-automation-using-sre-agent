---
name: compliance-investigation
description: Investigates non-compliant controls found by Microsoft Defender for Cloud AND Azure Policy, correlates findings across both sources, and prioritizes remediation.
---

# Compliance Investigation

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Scope

This skill works across ALL subscriptions and resource groups in your tenant by default.

- To check all compliance: just ask "check compliance posture"
- To narrow scope: specify a resource group or subscription, e.g. "check compliance for subscription X" or "check policy compliance in rg-production"
- The skill auto-discovers servers and Log Analytics workspaces — nothing is hardcoded

## Step 1 — Query Defender for Cloud compliance (1 command for all standards)

This already works tenant-wide:

```shell
az security regulatory-compliance-standards list --query "[].{Standard:name, State:state, PassedControls:passedControls, FailedControls:failedControls, SkippedControls:skippedControls}" -o table
```

For any standard with FailedControls > 0, drill into the failing controls:

```shell
az security regulatory-compliance-controls list --standard-name STANDARD_NAME --query "[?state=='Failed'].{Control:name, State:state, FailedAssessments:failedAssessments, Description:description}" -o table
```

Replace `STANDARD_NAME` with the standard name from the previous output (e.g., `CIS-Microsoft-Azure-Foundations-Benchmark-v2.0.0`).

## Step 2 — Query Azure Policy compliance (tenant-wide by default)

If the user specified a resource group, add `--resource-group USER_RG`. If the user specified a subscription, add `--subscription USER_SUB`. Otherwise, omit scope flags to query the default subscription, or run per subscription for full tenant coverage.

**Summary of non-compliant policies (default subscription):**

```shell
az policy state summarize -o table
```

**Scoped to a specific subscription:**

```shell
az policy state summarize --subscription USER_SUB -o table
```

**Non-compliant resources across the tenant via Resource Graph:**

```shell
az graph query -q "policyresources | where type == 'microsoft.policyinsights/policystates' | where properties.complianceState == 'NonCompliant' | project resourceId=tostring(properties.resourceId), policyDefinition=tostring(properties.policyDefinitionName), resourceGroup, subscriptionId | order by subscriptionId, resourceGroup" --first 1000 -o table
```

**Active policy assignments (default subscription, or scoped):**

```shell
az policy assignment list --query "[].{Name:displayName, PolicyId:policyDefinitionId, Enforcement:enforcementMode}" -o table
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

First, discover the affected Arc-enrolled servers:

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

For each affected Windows server, run ONE combined diagnostic command using the server's actual resource group and location from discovery:

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name compCheck --location SERVER_LOCATION --async-execution true --script 'Write-Output "=== AUDIT POLICY ==="; auditpol /get /category:* | Select-String "No Auditing"; Write-Output "=== FIREWALL ==="; Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table -AutoSize; Write-Output "=== PASSWORD POLICY ==="; net accounts'
```

After dispatching commands for all affected servers, batch-read results:

```shell
az connectedmachine run-command show --resource-group SERVER_RG --machine-name SERVER_NAME --name compCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
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

For each P1 or P2 finding (or group related findings into one ticket).

If GLPI is configured in your environment, initialize a session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'YOUR_GLPI_URL/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Compliance] SOURCE: CONTROL_NAME — N servers affected", "content": "Priority: P_LEVEL\nSource: Defender/Policy/Both\nAffected servers: SERVER_LIST\nFinding: DESCRIPTION\nRemediation: STEPS", "type": 1, "urgency": URGENCY_LEVEL, "priority": PRIORITY_LEVEL}}' 'YOUR_GLPI_URL/apirest.php/Ticket'
```

Priority mapping: P1 → urgency=5,priority=5 | P2 → urgency=4,priority=4 | P3 → urgency=3,priority=3

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
