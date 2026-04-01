---
name: vmware-bau-operations
description: Performs VMware/Hyper-V BAU tasks including snapshot cleanup, resource monitoring, and VM health checks.
---

# Hyper-V BAU Operations

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Scope

This skill works across ALL Azure VMs and Arc-enrolled servers in your tenant by default.

- To check all VMs: just ask "check VM health" or "clean up snapshots"
- To narrow scope: specify a VM name, resource group, or subscription, e.g. "check snapshots on MyHyperVHost in rg-production"
- The skill auto-discovers Hyper-V hosts, Arc servers, and Log Analytics workspaces — nothing is hardcoded

**IMPORTANT**: Hyper-V hosts are Azure VMs — always use `az vm run-command invoke` for them, NOT `az connectedmachine run-command create`.

## Step 1 — Discover Azure VMs (potential Hyper-V hosts)

If the user specified a VM name, use that directly. Otherwise, discover Azure VMs in the tenant.

If the user specified a resource group, add `| where resourceGroup =~ 'USER_RG'`. If the user specified a subscription, add `| where subscriptionId == 'USER_SUB'`.

**All Azure VMs (default):**

```shell
az graph query -q "Resources | where type == 'microsoft.compute/virtualmachines' | project name, resourceGroup, subscriptionId, location, powerState=tostring(properties.extended.instanceView.powerState.displayStatus) | order by name" --first 1000 -o table
```

If the user specified a specific Hyper-V host by name, use it directly in the commands below. Otherwise, ask the user which VM is the Hyper-V host.

## Step 2 — Discover Arc-enrolled servers

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

Record the server names, resource groups, and locations for use in health checks below.

## Step 3 — Discover Log Analytics workspace

```shell
az graph query -q "Resources | where type == 'microsoft.operationalinsights/workspaces' | project name, resourceGroup, subscriptionId, workspaceId=tostring(properties.customerId), location" --first 1000 -o table
```

Use the workspace ID (`WORKSPACE_ID`) from above in KQL queries below. If multiple workspaces exist, query each until you find one with Perf data for the target servers.

## Task 1 — Snapshot/Checkpoint Cleanup

### Step 4 — List all checkpoints with age classification

Replace `HYPERV_RG` and `HYPERV_HOST` with the Hyper-V host's resource group and name from Step 1:

```shell
az vm run-command invoke --resource-group HYPERV_RG --name HYPERV_HOST --command-id RunPowerShellScript --scripts 'Get-VM | ForEach-Object { $vm = $_; Get-VMCheckpoint -VMName $vm.Name -ErrorAction SilentlyContinue | ForEach-Object { $age = [int]((Get-Date) - $_.CreationTime).TotalDays; $action = if ($age -gt 30) { "CRITICAL-DELETE" } elseif ($age -ge 7) { "WARNING-REVIEW" } else { "KEEP" }; [PSCustomObject]@{ VMName = $vm.Name; CheckpointName = $_.Name; CreationTime = $_.CreationTime.ToString("yyyy-MM-dd HH:mm:ss"); AgeDays = $age; Action = $action } } } | Format-Table -AutoSize' -o json
```

The output is in `.value[0].message`. Parse the stdout section.

### Step 5 — Present cleanup plan

Show the user a table built from the Step 4 output:

| VM Name | Checkpoint Name | Created | Age (days) | Action |
|---------|----------------|---------|------------|--------|
| _name_ | _checkpoint_ | _date_ | _days_ | KEEP / DELETE (confirm) / DELETE (recommended) |

Rules:
- **< 7 days** → KEEP — report only
- **7–30 days** → WARNING — prompt user for confirmation before deletion
- **> 30 days** → CRITICAL — recommend immediate deletion, create ticket

Ask the user for confirmation before proceeding with any deletions.

### Step 6 — Delete approved checkpoints

For each checkpoint the user approves for deletion:

```shell
az vm run-command invoke --resource-group HYPERV_RG --name HYPERV_HOST --command-id RunPowerShellScript --scripts 'Remove-VMCheckpoint -VMName "VM_NAME" -Name "CHECKPOINT_NAME" -Confirm:$false; Write-Output "Deleted: VM_NAME / CHECKPOINT_NAME"' -o json
```

After all deletions, verify with one command:

```shell
az vm run-command invoke --resource-group HYPERV_RG --name HYPERV_HOST --command-id RunPowerShellScript --scripts 'Get-VM | ForEach-Object { Get-VMCheckpoint -VMName $_.Name -ErrorAction SilentlyContinue } | Select-Object VMName,Name,CreationTime | Format-Table -AutoSize' -o json
```

## Task 2 — VM Resource Utilization Report

### Step 7 — Query CPU and memory utilization (last 7 days)

ONE Log Analytics query for both CPU and memory. Replace `WORKSPACE_ID` from Step 3:

```shell
az monitor log-analytics query --workspace WORKSPACE_ID --analytics-query "Perf | where TimeGenerated > ago(7d) | where (ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use') | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1), P95Value=round(percentile(CounterValue,95),1) by Computer, ObjectName | order by Computer asc, ObjectName asc" -o table
```

### Step 8 — Evaluate resource thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| Avg CPU > 70% (7 day) | Capacity review needed | WARNING |
| Avg CPU > 85% (7 day) | Immediate capacity action | CRITICAL |
| Avg Memory > 80% (7 day) | Memory upgrade assessment | WARNING |
| Avg Memory > 90% (7 day) | Immediate memory action | CRITICAL |

Present results as a table with one row per discovered server:

| Server | Avg CPU | Max CPU | Avg Mem | Max Mem | CPU Status | Mem Status |
|--------|---------|---------|---------|---------|------------|------------|

## Task 3 — VM Health Check

### Step 9 — Check Arc connectivity and Defender status for all servers

ONE tenant-wide query for Arc connectivity (uses servers from Step 2):

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), lastStatusChange=tostring(properties.lastStatusChange), os=tostring(properties.osName) | order by name" --first 1000 -o table
```

ONE tenant-wide query for Defender (MDE) extension status:

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines/extensions' | where properties.type contains 'MDE' or name contains 'Defender' | extend machineName = tostring(split(id, '/')[8]), rg = resourceGroup | extend provisioningState = tostring(properties.provisioningState) | project machineName, rg, provisioningState" --first 1000 -o table
```

If the Resource Graph query returns no results for MDE extensions, fall back to checking each server individually using names from Step 2:

```shell
az connectedmachine extension list --machine-name SERVER_NAME --resource-group SERVER_RG --query "[?contains(type,'MDE')].{Name:name, Status:provisioningState}" -o table
```

Any server with Status != Connected → CRITICAL. Missing MDE extension or Status != Succeeded → WARNING.

### Step 10 — Check Hyper-V VM power state

Replace `HYPERV_RG` and `HYPERV_HOST` with actual values from Step 1:

```shell
az vm run-command invoke --resource-group HYPERV_RG --name HYPERV_HOST --command-id RunPowerShellScript --scripts 'Get-VM | Select-Object Name,State,CPUUsage,@{N="MemoryAssignedGB";E={[math]::Round($_.MemoryAssigned/1GB,1)}},Uptime,Status | Format-Table -AutoSize' -o json
```

Any VM with State != Running → WARNING.

### Step 11 — Check pending patches

Tenant-wide query (no hardcoded scope):

```shell
az graph query -q "patchassessmentresources | where type == 'microsoft.hybridcompute/machines/patchassessmentresults' | extend machineName = tostring(split(id, '/')[8]) | extend criticalCount = toint(properties.availablePatchCountByClassification.critical) | extend securityCount = toint(properties.availablePatchCountByClassification.security) | extend totalCount = toint(properties.availablePatchCountByClassification.total) | project machineName, resourceGroup, subscriptionId, criticalCount, securityCount, totalCount" --first 1000 -o table
```

Critical patches pending > 0 → WARNING.

### Step 12 — VM health summary

Present a table with one row per discovered server:

| Server | Resource Group | Power State | Arc Status | Defender | Pending Patches | Overall |
|--------|---------------|------------|------------|----------|-----------------|---------|

## Step 13 — Create GLPI ticket if CRITICAL findings

Only create a ticket for CRITICAL findings (old snapshots >30 days, sustained high resource usage, disconnected servers).

If no CRITICAL findings → skip this step, report summary only.

If GLPI is configured in your environment, initialize a session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'YOUR_GLPI_URL/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[BAU] ISSUE_SUMMARY", "content": "DETAILED_FINDINGS", "type": 1, "urgency": 4, "priority": 4}}' 'YOUR_GLPI_URL/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
