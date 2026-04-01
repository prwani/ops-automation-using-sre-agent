---
name: wintel-health-check-investigation
description: Investigates Windows server health check failures and warnings reported by the automated health check system.
---

# Health Check Investigation

Execute these steps IN ORDER. Use SINGLE commands that cover ALL servers at once — do NOT loop per server.

## Scope

This skill works across ALL Arc-enrolled Windows servers in your tenant by default.

- To check all servers: just ask "check health of all my servers"
- To narrow scope: specify a resource group or subscription, e.g. "check health of servers in rg-production"
- The skill auto-discovers Log Analytics workspaces and uses the one collecting data for the target servers

## Step 1 — Discover Arc-enrolled Windows servers

If the user specified a resource group, add `| where resourceGroup =~ 'USER_RG'` to the query. If the user specified a subscription, add `| where subscriptionId == 'USER_SUB'`.

**All servers (default):**

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | where properties.osName has 'Windows' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

**Scoped to a resource group:**

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | where properties.osName has 'Windows' | where resourceGroup =~ 'USER_RG' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

Record the server names, resource groups, and locations from the output — you will use them in all subsequent steps.

If any show a status other than `Connected`, report that and note those servers may not respond to run-commands.

## Step 2 — Discover Log Analytics workspace

Find all Log Analytics workspaces in the tenant:

```shell
az graph query -q "Resources | where type == 'microsoft.operationalinsights/workspaces' | project name, resourceGroup, subscriptionId, workspaceId=tostring(properties.customerId), location" --first 1000 -o table
```

Use the workspace ID(s) from above in KQL queries below. If multiple workspaces exist, query each until you find one that has Perf data for the discovered servers, or ask the user which one to use.

## Step 3 — Check CPU, Memory, and Disk via Log Analytics (ONE query for ALL servers)

Build the `in~()` list dynamically from the server names discovered in Step 1. Replace `WORKSPACE_ID` with the workspace ID from Step 2.

```shell
az monitor log-analytics query --workspace WORKSPACE_ID --analytics-query "Perf | where TimeGenerated > ago(1h) | where Computer in~ ('SERVER1','SERVER2','SERVER3') | where (ObjectName == 'Processor Information' and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use') or (ObjectName == 'LogicalDisk' and CounterName == '% Free Space' and InstanceName == 'C:') | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1) by Computer, ObjectName, CounterName | order by Computer, ObjectName" -o table
```

Evaluate thresholds from the output:
- CPU (% Processor Time) avg > 85 → CRITICAL, > 75 → WARNING
- Memory (% Committed Bytes In Use) avg > 85 → CRITICAL, > 75 → WARNING
- Disk (% Free Space) avg < 10 → CRITICAL (less than 10% free), < 20 → WARNING

## Step 4 — Check Services and Event Logs (ONE command per server, batched)

Only run this step if Step 3 showed warnings or if the user specifically asked about services/events. Use `--script-uri` or inline script with SINGLE QUOTES to avoid escaping issues.

For each server discovered in Step 1, replace `SERVER_RG`, `SERVER_NAME`, and `SERVER_LOCATION` with the actual values from discovery:

```shell
az connectedmachine run-command create -g SERVER_RG --machine-name SERVER_NAME --name healthCheck --location SERVER_LOCATION --async-execution true --script 'Get-Service wuauserv,WinRM,EventLog,WinDefend -EA SilentlyContinue | Select Name,Status; Write-Output "---EVENTS---"; Get-WinEvent -FilterHashtable @{LogName="System";Level=1,2;StartTime=(Get-Date).AddHours(-6)} -MaxEvents 5 -EA SilentlyContinue | Select TimeCreated,Id,LevelDisplayName | Format-Table'
```

Wait 30 seconds, then read results:

```shell
az connectedmachine run-command show -g SERVER_RG --machine-name SERVER_NAME --name healthCheck --query "instanceView" -o json
```

IMPORTANT: Use single quotes around the --script value. Do NOT escape $ signs. Do NOT use double quotes for the script.

## Step 5 — Summarize

Present a summary table with one row per discovered server:

| Server | Resource Group | CPU | Memory | Disk C: | Services | Events | Status |
|--------|---------------|-----|--------|---------|----------|--------|--------|

Status = worst finding across all checks (OK / WARNING / CRITICAL).

If any server is CRITICAL, recommend creating a GLPI ticket. If GLPI is configured in your environment, use the API:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'YOUR_GLPI_URL/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Health Check] SERVER: ISSUE", "content": "DETAILS", "type": 1, "urgency": 4, "priority": 4}}' 'YOUR_GLPI_URL/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
