---
name: wintel-health-check-investigation
description: Investigates Windows server health check failures. Use when asked about server health, disk, CPU, memory, services, or event logs on Arc-enrolled servers.
---

# Health Check Investigation

Execute these steps IN ORDER. Use SINGLE commands that cover ALL servers at once — do NOT loop per server.

## Environment

- Resource Group: `rg-arcbox-itpro`
- Log Analytics Workspace: `f98fca75-7479-45e5-bf0c-87b56a9f9e8c`
- Windows servers: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL

## Step 1 — List all Arc servers

```shell
az connectedmachine list -g rg-arcbox-itpro --query "[].{Name:name, Status:status, OS:osName}" -o table
```

If any show Disconnected, report that and stop.

## Step 2 — Check CPU, Memory, and Disk via Log Analytics (ONE query for ALL servers)

This single query returns CPU, memory, AND disk for all servers in one call:

```shell
az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(1h) | where Computer in~ ('ArcBox-Win2K22','ArcBox-Win2K25','ArcBox-SQL') | where (ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use') or (ObjectName == 'LogicalDisk' and CounterName == '% Free Space' and InstanceName != '_Total') | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1) by Computer, ObjectName, CounterName, InstanceName | order by Computer, ObjectName" -o table
```

Evaluate thresholds from the output:
- CPU (% Processor Time) avg > 85 → CRITICAL, > 75 → WARNING
- Memory (% Committed Bytes In Use) avg > 85 → CRITICAL, > 75 → WARNING
- Disk (% Free Space) avg < 10 → CRITICAL, < 20 → WARNING

## Step 3 — Check Services and Event Logs (ONE command per server, batched)

Only run this step if Step 2 showed warnings or if the user specifically asked about services/events. Use `--script-uri` or inline script with SINGLE QUOTES to avoid escaping issues:

For ONE server at a time (replace SERVER_NAME):

```shell
az connectedmachine run-command create -g rg-arcbox-itpro --machine-name SERVER_NAME --name healthCheck --location swedencentral --async-execution true --script 'Get-Service wuauserv,WinRM,EventLog,WinDefend -EA SilentlyContinue | Select Name,Status; Write-Output "---EVENTS---"; Get-WinEvent -FilterHashtable @{LogName="System";Level=1,2;StartTime=(Get-Date).AddHours(-6)} -MaxEvents 5 -EA SilentlyContinue | Select TimeCreated,Id,LevelDisplayName | Format-Table'
```

Wait 30 seconds, then read results:

```shell
az connectedmachine run-command show -g rg-arcbox-itpro --machine-name SERVER_NAME --name healthCheck --query "instanceView" -o json
```

IMPORTANT: Use single quotes around the --script value. Do NOT escape $ signs. Do NOT use double quotes for the script.

## Step 4 — Summarize

Present a summary table:

| Server | CPU | Memory | Disk C: | Services | Events | Status |
|--------|-----|--------|---------|----------|--------|--------|

Status = worst finding across all checks (OK / WARNING / CRITICAL).

If any server is CRITICAL, recommend creating a GLPI ticket. If GLPI credentials are available, use the OAuth2 API:

```shell
TOKEN=$(curl -s -X POST -d "grant_type=password&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET&username=glpi&password=glpi&scope=api" http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"[Health Check] SERVER: ISSUE","content":"DETAILS","type":1,"priority":2}' http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2.2/Assistance/Ticket
```
