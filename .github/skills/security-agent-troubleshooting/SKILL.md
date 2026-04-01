---
name: security-agent-troubleshooting
description: Diagnoses and remediates Microsoft Defender for Endpoint agent issues on Windows servers.
---

# Security Agent Troubleshooting

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Scope

This skill works across ALL Arc-enrolled Windows servers in your tenant by default.

- To check all servers: just ask "check Defender health on all servers"
- To narrow scope: specify a resource group or subscription, e.g. "check MDE agent in rg-production"
- The skill auto-discovers servers and Log Analytics workspaces — nothing is hardcoded

## Step 1 — Discover Arc-enrolled Windows servers

If the user specified a resource group, add `| where resourceGroup =~ 'USER_RG'`. If the user specified a subscription, add `| where subscriptionId == 'USER_SUB'`.

**All servers (default):**

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | where properties.osName has 'Windows' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

**Scoped to a resource group:**

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | where properties.osName has 'Windows' | where resourceGroup =~ 'USER_RG' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

Record the server names, resource groups, and locations from the output. Confirm servers are Connected. If any server shows Disconnected, note it — remaining steps will not work for that machine.

## Step 2 — Check Defender extension status for ALL discovered servers

Use Resource Graph for a single tenant-wide query of MDE/Defender extensions:

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines/extensions' | where properties.type contains 'MDE' or name contains 'Defender' | extend machineName = tostring(split(id, '/')[8]), rg = resourceGroup | extend provisioningState = tostring(properties.provisioningState), version = tostring(properties.typeHandlerVersion) | project machineName, rg, provisioningState, version" --first 1000 -o table
```

If the Resource Graph query returns no results, fall back to checking each server individually using the names from Step 1:

```shell
az connectedmachine extension list --machine-name SERVER_NAME --resource-group SERVER_RG --query "[?contains(name,'MDE') || contains(name,'Defender')].{name:name,state:provisioningState,version:typeHandlerVersion}" -o table
```

If the MDE extension is missing or state != Succeeded on any server, note it as CRITICAL.

## Step 3 — Discover Log Analytics workspace and check heartbeat

Find all Log Analytics workspaces in the tenant:

```shell
az graph query -q "Resources | where type == 'microsoft.operationalinsights/workspaces' | project name, resourceGroup, subscriptionId, workspaceId=tostring(properties.customerId), location" --first 1000 -o table
```

Use the discovered workspace ID (`WORKSPACE_ID`) below. Build the `in~()` list dynamically from server names in Step 1:

```shell
az monitor log-analytics query --workspace WORKSPACE_ID --analytics-query 'Heartbeat | where Computer in~ ("SERVER1","SERVER2","SERVER3") | summarize LastHeartbeat=max(TimeGenerated) by Computer | extend StaleMinutes=datetime_diff("minute",now(),LastHeartbeat)' -o table
```

If multiple workspaces exist, query each until you find the one with heartbeat data for the target servers.

If any server shows StaleMinutes > 30, flag it as WARNING. If StaleMinutes > 120, flag as CRITICAL.

**Only proceed to Step 4 if** Step 2 shows missing/failed extensions OR Step 3 shows stale heartbeats. If all servers are healthy, skip to Step 6 (Summarize).

## Step 4 — Diagnose unhealthy servers via Arc run-command

For each server flagged in Steps 2–3, run ONE combined diagnostic command. Use the server's resource group and location from Step 1:

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name mdeDiag --location SERVER_LOCATION --async-execution true --script 'Write-Output "=== SERVICES ==="; Get-Service WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType | Format-Table -AutoSize; Write-Output "=== DEFENDER STATUS ==="; Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,AntivirusSignatureLastUpdated | Format-List; Write-Output "=== RECENT EVENTS ==="; Get-WinEvent -LogName "Microsoft-Windows-Windows Defender/Operational" -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap; Write-Output "=== CONNECTIVITY ==="; Test-NetConnection winatp-gw-weu.microsoft.com -Port 443 -WarningAction SilentlyContinue | Select-Object ComputerName,TcpTestSucceeded; Test-NetConnection us-v20.events.data.microsoft.com -Port 443 -WarningAction SilentlyContinue | Select-Object ComputerName,TcpTestSucceeded'
```

After dispatching commands for all unhealthy servers, batch-read results:

```shell
az connectedmachine run-command show --resource-group SERVER_RG --machine-name SERVER_NAME --name mdeDiag --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Evaluate each section of the output:

**Services:** WinDefend or Sense stopped → CRITICAL. MdCoreSvc stopped → WARNING.

**Defender status:** AntivirusEnabled=False or RealTimeProtectionEnabled=False → CRITICAL. AntivirusSignatureAge > 3 → WARNING, > 7 → CRITICAL.

**Events:** ID 5001 (real-time disabled) → CRITICAL. ID 5010/5012 (update failed) → WARNING. ID 1116/1117 (malware) → log for awareness.

**Connectivity:** TcpTestSucceeded=False → CRITICAL (firewall issue, do NOT auto-remediate).

## Step 5 — Remediation (only if Step 4 shows fixable issues)

Skip this step entirely if Step 4 found no issues or only connectivity failures (those require firewall changes).

**Service stopped → Restart it:**

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name mdeRestart --location SERVER_LOCATION --async-execution true --script 'Restart-Service WinDefend -Force -ErrorAction SilentlyContinue; Start-Service Sense -ErrorAction SilentlyContinue; Start-Service MdCoreSvc -ErrorAction SilentlyContinue; Start-Sleep -Seconds 10; Get-Service WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table -AutoSize'
```

**Definitions stale → Force update:**

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name mdeUpdate --location SERVER_LOCATION --async-execution true --script 'Update-MpSignature -UpdateSource MicrosoftUpdateServer -ErrorAction SilentlyContinue; Start-Sleep -Seconds 30; Get-MpComputerStatus | Select-Object AntivirusSignatureAge,AntivirusSignatureLastUpdated | Format-List'
```

After remediation, re-read the run-command results to verify the fix took effect. Do NOT attempt remediation for connectivity issues — those require firewall changes.

## Step 6 — Summarize findings

Present results as a table with one row per discovered server:

| Server | Resource Group | WinDefend | Sense | MdCoreSvc | Definitions Age | RealTime | Connectivity | Status |
|--------|---------------|-----------|-------|-----------|-----------------|----------|--------------|--------|

## Step 7 — Create GLPI ticket if escalation needed

Create a ticket only if:
- Any service won't restart after remediation
- Connectivity is blocked (firewall change needed)
- Definitions won't update
- Real-time protection cannot be re-enabled

If GLPI is configured in your environment, initialize a session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'YOUR_GLPI_URL/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Security] Defender agent issue: SERVER_NAME - ISSUE_SUMMARY", "content": "DETAILED_FINDINGS_AND_REMEDIATION_ATTEMPTED", "type": 1, "urgency": 4, "priority": 4}}' 'YOUR_GLPI_URL/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
