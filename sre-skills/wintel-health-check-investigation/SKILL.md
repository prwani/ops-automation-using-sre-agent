---
name: wintel-health-check-investigation
description: Investigates Windows server health check failures. Use when asked about server health, disk, CPU, memory, services, or event logs on Arc-enrolled servers.
---

# Health Check Investigation

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Environment

- Subscription: `31adb513-7077-47bb-9567-8e9d2a462bcf`
- Resource Group: `rg-arcbox-itpro`
- Region: `swedencentral`
- Log Analytics Workspace ID: `f98fca75-7479-45e5-bf0c-87b56a9f9e8c`
- Windows servers: `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL`
- GLPI URL: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

## Step 1 — List all Arc servers and their status

```shell
az connectedmachine list -g rg-arcbox-itpro --query "[].{Name:name, Status:status, OS:osName}" -o table
```

All servers should show Status=Connected. If any are Disconnected, report that first.

## Step 2 — Check CPU and Memory (last 1 hour)

Run this KQL query for each Windows server (ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL):

```shell
az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(1h) | where Computer == 'SERVER_NAME' | where (ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use') | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1) by Computer, ObjectName, CounterName" -o table
```

Replace `SERVER_NAME` with each server name and run the command three times.

Thresholds:
- CPU avg > 85% → CRITICAL
- CPU avg > 75% → WARNING
- Memory avg > 85% → CRITICAL
- Memory avg > 75% → WARNING

## Step 3 — Check Disk Usage

For each Windows server, create a run command:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name diskCheck --location swedencentral --script "Get-PSDrive -PSProvider FileSystem | Where-Object {\$_.Used -gt 0} | ForEach-Object { \$pct=[math]::Round((\$_.Used/(\$_.Used+\$_.Free))*100,1); Write-Output \"Drive \$(\$_.Name): \$pct% used (\$([math]::Round(\$_.Free/1GB,1))GB free)\" }" --no-wait
```

Then check results (poll until executionState is Succeeded):

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name diskCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Thresholds:
- Disk > 90% → CRITICAL
- Disk > 80% → WARNING

## Step 4 — Check Critical Services

For each Windows server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name svcCheck --location swedencentral --script "Get-Service -Name wuauserv,WinRM,EventLog,WinDefend -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table -AutoSize" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name svcCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Any service with Status != Running → WARNING

## Step 5 — Check Event Logs (last 6 hours)

For each Windows server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name evtCheck --location swedencentral --script "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddHours(-6)} -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,Message | Format-Table -Wrap" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name evtCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

More than 5 Error/Critical events → WARNING

## Step 6 — Summarize findings

Present results as a table:

| Server | CPU | Memory | Disk | Services | Events | Status |
|--------|-----|--------|------|----------|--------|--------|
| ArcBox-Win2K22 | _avg%_ | _avg%_ | _C: used%_ | _OK/WARN_ | _count_ | OK / WARNING / CRITICAL |
| ArcBox-Win2K25 | _avg%_ | _avg%_ | _C: used%_ | _OK/WARN_ | _count_ | OK / WARNING / CRITICAL |
| ArcBox-SQL | _avg%_ | _avg%_ | _C: used%_ | _OK/WARN_ | _count_ | OK / WARNING / CRITICAL |

The overall status for each server is the worst status across all checks.

## Step 7 — Create GLPI ticket if any CRITICAL findings

Only create a ticket if at least one server has a CRITICAL finding.

First, initialize a GLPI session:

```shell
curl -s -X GET -H "Content-Type: application/json" -H "Authorization: user_token YOUR_TOKEN" -H "App-Token: YOUR_APP_TOKEN" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H "Content-Type: application/json" -H "Session-Token: SESSION_TOKEN" -H "App-Token: YOUR_APP_TOKEN" -d "{\"input\": {\"name\": \"[Health Check] SERVER_NAME: ISSUE_SUMMARY\", \"content\": \"DETAILED_FINDINGS\", \"type\": 1, \"urgency\": 5, \"priority\": 5}}" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket"
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
