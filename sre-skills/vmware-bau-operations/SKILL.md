---
name: vmware-bau-operations
description: Performs Hyper-V BAU tasks including snapshot/checkpoint cleanup, resource monitoring, and VM health checks. Use when asked about VM snapshots, checkpoints, VM resource utilization, or VM health.
---

# Hyper-V BAU Operations

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Environment

- Subscription: `31adb513-7077-47bb-9567-8e9d2a462bcf`
- Resource Group: `rg-arcbox-itpro`
- Region: `swedencentral`
- Log Analytics Workspace ID: `f98fca75-7479-45e5-bf0c-87b56a9f9e8c`
- Hyper-V Host: `ArcBox-Client` (this is an Azure VM, NOT an Arc machine — use `az vm run-command invoke`)
- Arc Windows servers: `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL`
- Arc Linux servers: `Arcbox-Ubuntu-01`, `Arcbox-Ubuntu-02`
- GLPI URL: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

**IMPORTANT**: `ArcBox-Client` is the Hyper-V host and is an Azure VM. Always use `az vm run-command invoke` for it, NOT `az connectedmachine run-command create`.

## Task 1 — Snapshot/Checkpoint Cleanup

### Step 1 — List all checkpoints with age classification

ONE command to list all checkpoints and flag them by age:

```shell
az vm run-command invoke --resource-group rg-arcbox-itpro --name ArcBox-Client --command-id RunPowerShellScript --scripts 'Get-VM | ForEach-Object { $vm = $_; Get-VMCheckpoint -VMName $vm.Name -ErrorAction SilentlyContinue | ForEach-Object { $age = [int]((Get-Date) - $_.CreationTime).TotalDays; $action = if ($age -gt 30) { "CRITICAL-DELETE" } elseif ($age -ge 7) { "WARNING-REVIEW" } else { "KEEP" }; [PSCustomObject]@{ VMName = $vm.Name; CheckpointName = $_.Name; CreationTime = $_.CreationTime.ToString("yyyy-MM-dd HH:mm:ss"); AgeDays = $age; Action = $action } } } | Format-Table -AutoSize' -o json
```

The output is in `.value[0].message`. Parse the stdout section.

### Step 2 — Present cleanup plan

Show the user a table built from the Step 1 output:

| VM Name | Checkpoint Name | Created | Age (days) | Action |
|---------|----------------|---------|------------|--------|
| _name_ | _checkpoint_ | _date_ | _days_ | KEEP / DELETE (confirm) / DELETE (recommended) |

Rules:
- **< 7 days** → KEEP — report only
- **7–30 days** → WARNING — prompt user for confirmation before deletion
- **> 30 days** → CRITICAL — recommend immediate deletion, create ticket

Ask the user for confirmation before proceeding with any deletions.

### Step 3 — Delete approved checkpoints

For each checkpoint the user approves for deletion:

```shell
az vm run-command invoke --resource-group rg-arcbox-itpro --name ArcBox-Client --command-id RunPowerShellScript --scripts 'Remove-VMCheckpoint -VMName "VM_NAME" -Name "CHECKPOINT_NAME" -Confirm:$false; Write-Output "Deleted: VM_NAME / CHECKPOINT_NAME"' -o json
```

After all deletions, verify with one command:

```shell
az vm run-command invoke --resource-group rg-arcbox-itpro --name ArcBox-Client --command-id RunPowerShellScript --scripts 'Get-VM | ForEach-Object { Get-VMCheckpoint -VMName $_.Name -ErrorAction SilentlyContinue } | Select-Object VMName,Name,CreationTime | Format-Table -AutoSize' -o json
```

## Task 2 — VM Resource Utilization Report

### Step 4 — Query CPU and memory utilization (last 7 days)

ONE Log Analytics query for both CPU and memory:

```shell
az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(7d) | where (ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use') | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1), P95Value=round(percentile(CounterValue,95),1) by Computer, ObjectName | order by Computer asc, ObjectName asc" -o table
```

### Step 5 — Evaluate resource thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| Avg CPU > 70% (7 day) | Capacity review needed | WARNING |
| Avg CPU > 85% (7 day) | Immediate capacity action | CRITICAL |
| Avg Memory > 80% (7 day) | Memory upgrade assessment | WARNING |
| Avg Memory > 90% (7 day) | Immediate memory action | CRITICAL |

Present results as:

| Server | Avg CPU | Max CPU | Avg Mem | Max Mem | CPU Status | Mem Status |
|--------|---------|---------|---------|---------|------------|------------|
| _name_ | _pct_ | _pct_ | _pct_ | _pct_ | OK/WARN/CRIT | OK/WARN/CRIT |

## Task 3 — VM Health Check

### Step 6 — Check Arc connectivity and Defender status for all servers

ONE command for Arc connectivity:

```shell
az connectedmachine list -g rg-arcbox-itpro --query "[].{Name:name, Status:status, LastStatusChange:lastStatusChange, OS:osName}" -o table
```

ONE command for Defender (MDE) extension status across all Windows Arc servers:

```shell
az graph query -q "extendedlocationresources | where type == 'microsoft.hybridcompute/machines/extensions' | where resourceGroup == 'rg-arcbox-itpro' | where properties.type contains 'MDE' | extend machineName = tostring(split(id, '/')[8]) | extend provisioningState = tostring(properties.provisioningState) | project machineName, provisioningState" --subscriptions 31adb513-7077-47bb-9567-8e9d2a462bcf -o table
```

If the Resource Graph query returns no results for MDE extensions, fall back to checking each server individually:

```shell
az connectedmachine extension list --machine-name SERVER_NAME --resource-group rg-arcbox-itpro --query "[?contains(type,'MDE')].{Name:name, Status:provisioningState}" -o table
```

Any server with Status != Connected → CRITICAL. Missing MDE extension or Status != Succeeded → WARNING.

### Step 7 — Check Hyper-V VM power state

```shell
az vm run-command invoke --resource-group rg-arcbox-itpro --name ArcBox-Client --command-id RunPowerShellScript --scripts 'Get-VM | Select-Object Name,State,CPUUsage,@{N="MemoryAssignedGB";E={[math]::Round($_.MemoryAssigned/1GB,1)}},Uptime,Status | Format-Table -AutoSize' -o json
```

Any VM with State != Running → WARNING.

### Step 8 — Check pending patches

```shell
az graph query -q "patchassessmentresources | where type == 'microsoft.hybridcompute/machines/patchassessmentresults' | where resourceGroup == 'rg-arcbox-itpro' | extend machineName = tostring(split(id, '/')[8]) | extend criticalCount = toint(properties.availablePatchCountByClassification.critical) | extend securityCount = toint(properties.availablePatchCountByClassification.security) | extend totalCount = toint(properties.availablePatchCountByClassification.total) | project machineName, criticalCount, securityCount, totalCount" --subscriptions 31adb513-7077-47bb-9567-8e9d2a462bcf -o table
```

Critical patches pending > 0 → WARNING.

### Step 9 — VM health summary

| Server | Power State | Arc Status | Defender | Pending Patches | Overall |
|--------|------------|------------|----------|-----------------|---------|
| ArcBox-Win2K22 | Running/Off | Connected/Disconnected | OK/WARN | _count_ | OK / WARNING / CRITICAL |
| ArcBox-Win2K25 | ... | ... | ... | ... | ... |
| ArcBox-SQL | ... | ... | ... | ... | ... |
| Arcbox-Ubuntu-01 | ... | ... | N/A | ... | ... |
| Arcbox-Ubuntu-02 | ... | ... | N/A | ... | ... |

## Step 10 — Create GLPI ticket if CRITICAL findings

Only create a ticket for CRITICAL findings (old snapshots >30 days, sustained high resource usage, disconnected servers).

If no CRITICAL findings → skip this step, report summary only.

Get a GLPI session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[BAU] ISSUE_SUMMARY", "content": "DETAILED_FINDINGS", "type": 1, "urgency": 4, "priority": 4}}' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
