---
name: vmware-bau-operations
version: 1.0.0
description: Performs VMware/Hyper-V BAU tasks including snapshot cleanup, resource monitoring, and VM health checks.
triggers:
  - Weekly scheduled run (snapshots)
  - Monthly scheduled run (resource report)
  - Alert: VM snapshot count >5 or snapshot age >7 days
  - User requests VM health status
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - glpi-create-ticket
  - cosmos-query-runs
sop_source: docs/sops/vmware-bau.md
---

# VMware BAU Operations

## Task 1 — Snapshot/Checkpoint Cleanup

### List all checkpoints
```
RunAzCliReadCommands(server_id=<hyperv_host_id>, script="""
Get-VM | ForEach-Object {
  $vm = $_
  Get-VMCheckpoint -VMName $vm.Name | ForEach-Object {
    [PSCustomObject]@{
      VMName = $vm.Name
      CheckpointName = $_.Name
      CreationTime = $_.CreationTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
      AgeDays = [int]((Get-Date) - $_.CreationTime).TotalDays
      ParentCheckpointId = $_.ParentCheckpointId
    }
  }
} | ConvertTo-Json
""")
```

### Decision logic
- Age < 7 days: KEEP (report only)
- Age 7–30 days: WARN — include in report, prompt for confirmation
- Age > 30 days: AUTO-DELETE (log and proceed) OR create ticket if production VM

### Remove old checkpoint
```
RunAzCliWriteCommands(server_id=<hyperv_host_id>, script="""
Remove-VMCheckpoint -VMName "<vm_name>" -Name "<checkpoint_name>" -Confirm:$false
""")
```

## Task 2 — VM Resource Utilization Report

```
RunAzCliReadCommands: az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(7d) | where ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total' | summarize AvgCPU=round(avg(CounterValue),1), MaxCPU=round(max(CounterValue),1) by Computer" -o json
```

```
RunAzCliReadCommands: az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(7d) | where ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use' | summarize AvgMem=round(avg(CounterValue),1), MaxMem=round(max(CounterValue),1) by Computer" -o json
```

Flag VMs with:
- Average CPU > 70% over 7 days → capacity review needed
- Average memory > 85% sustained → memory upgrade assessment

## Task 3 — VM Health Check

For each Arc-enrolled VM:
1. Check Arc connectivity (last heartbeat < 10 min)
2. Check power state via Arc
3. Check Defender agent status
4. Check pending patches count

Report as table: VM | Power | Arc | Defender | Pending Patches | Status
