---
name: patch-validation
description: Validates server health before and after Windows patch deployment. Assesses rollback need.
---

# Patch Validation

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Scope

This skill works across ALL Arc-enrolled Windows servers in your tenant by default.

- To check all servers: just ask "validate patching for all servers"
- To narrow scope: specify a resource group or subscription, e.g. "pre-patch check for servers in rg-production"
- The skill auto-discovers servers and Log Analytics workspaces — nothing is hardcoded

## Step 1 — Discover Arc-enrolled Windows servers

If the user specified a resource group, add `| where resourceGroup =~ 'USER_RG'`. If the user specified a subscription, add `| where subscriptionId == 'USER_SUB'`.

**All servers (default):**

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | where properties.osName has 'Windows' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location | order by name" --first 1000 -o table
```

Record the server names, resource groups, and locations from the output — you will use them in all subsequent steps.

## Step 2 — Discover Log Analytics workspace

```shell
az graph query -q "Resources | where type == 'microsoft.operationalinsights/workspaces' | project name, resourceGroup, subscriptionId, workspaceId=tostring(properties.customerId), location" --first 1000 -o table
```

Use the workspace ID(s) from above in KQL queries below. If multiple workspaces exist, query each until you find one with Update data for the target servers, or ask the user.

## Step 3 — Query Azure Update Manager for ALL discovered servers

ONE query to get patch assessment status across all subscriptions. If the user specified a resource group, add `| where resourceGroup =~ 'USER_RG'`:

```shell
az graph query -q "patchassessmentresources | where type == 'microsoft.hybridcompute/machines/patchassessmentresults' | extend machineName = tostring(split(id, '/')[8]) | extend status = tostring(properties.status) | extend lastAssessment = tostring(properties.lastModifiedDateTime) | extend criticalCount = toint(properties.availablePatchCountByClassification.critical) | extend securityCount = toint(properties.availablePatchCountByClassification.security) | extend totalCount = toint(properties.availablePatchCountByClassification.total) | project machineName, resourceGroup, subscriptionId, status, criticalCount, securityCount, totalCount, lastAssessment" --first 1000 -o table
```

If installation history is needed:

```shell
az graph query -q "patchinstallationresources | where type == 'microsoft.hybridcompute/machines/patchinstallationresults' | extend machineName = tostring(split(id, '/')[8]) | extend status = tostring(properties.status) | extend installedCount = toint(properties.installedPatchCount) | extend failedCount = toint(properties.failedPatchCount) | extend lastModified = tostring(properties.lastModifiedDateTime) | project machineName, resourceGroup, subscriptionId, status, installedCount, failedCount, lastModified" --first 1000 -o table
```

## Step 4 — Pre-patch checks (ONE combined command per server)

Run ONE run-command per server that checks disk space, pending reboot, and critical services in a single script. Use `--no-wait` to launch servers in parallel, then poll for results.

For each server discovered in Step 1, replace `SERVER_RG`, `SERVER_NAME`, and `SERVER_LOCATION`:

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name prePatchCheck --location SERVER_LOCATION --script 'Write-Output "=== DISK ==="; $d = Get-PSDrive C; $pct = [math]::Round(($d.Free / ($d.Used + $d.Free)) * 100, 1); Write-Output "C: $pct% free ($([math]::Round($d.Free/1GB,1))GB)"; if ($pct -lt 20) { Write-Output "DISK: FAIL" } else { Write-Output "DISK: PASS" }; Write-Output "=== REBOOT ==="; $cbs = Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"; $wu = Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"; Write-Output "CBS RebootPending: $cbs  WU RebootRequired: $wu"; if ($cbs -or $wu) { Write-Output "REBOOT: WARNING" } else { Write-Output "REBOOT: PASS" }; Write-Output "=== SERVICES ==="; Get-Service wuauserv,WinRM,WinDefend,EventLog,W32Time -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table -AutoSize; Write-Output "=== BASELINE ==="; Get-Service | Where-Object { $_.StartType -eq "Automatic" -and $_.Status -eq "Running" } | Select-Object Name,Status | Sort-Object Name | Format-Table -AutoSize' --no-wait
```

Then poll results (run for each server):

```shell
az connectedmachine run-command show --resource-group SERVER_RG --machine-name SERVER_NAME --name prePatchCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

**Decision rules:**
- `DISK: FAIL` → **BLOCK patching** on that server
- `REBOOT: WARNING` → Reboot first, then patch
- Any critical service (WinRM, WinDefend, EventLog, W32Time) not Running → investigate before patching

## Step 5 — Pre-patch summary

Present a summary table with one row per discovered server:

| Server | Resource Group | Disk Space | Pending Reboot | Services Baseline | Ready to Patch? |
|--------|---------------|-----------|----------------|-------------------|-----------------|

If all servers PASS, patching can proceed. If any server has FAIL, explain why and recommend remediation.

## Step 6 — Post-patch checks (ONE combined command per server)

Run AFTER patching completes. Same pattern — ONE run-command per server combining all post-patch checks. Launch with `--no-wait`, then poll.

For each discovered server, replace `SERVER_RG`, `SERVER_NAME`, and `SERVER_LOCATION`:

```shell
az connectedmachine run-command create --resource-group SERVER_RG --machine-name SERVER_NAME --name postPatchCheck --location SERVER_LOCATION --script 'Write-Output "=== REBOOT ==="; $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $uptime = (Get-Date) - $boot; Write-Output "Last boot: $boot  Uptime: $([math]::Round($uptime.TotalMinutes,0)) minutes"; Write-Output "=== SERVICES ==="; $stopped = Get-Service | Where-Object { $_.StartType -eq "Automatic" -and $_.Status -ne "Running" }; if ($stopped) { $stopped | Select-Object Name,Status,StartType | Format-Table -AutoSize; $critical = $stopped | Where-Object { $_.Name -in @("WinRM","WinDefend","EventLog","W32Time") }; if ($critical) { Write-Output "SERVICES: CRITICAL — $($critical.Name -join ", ") not running" } else { Write-Output "SERVICES: WARNING — non-critical services stopped" } } else { Write-Output "SERVICES: PASS" }; Write-Output "=== EVENTS ==="; $events = Get-WinEvent -FilterHashtable @{LogName="System";Level=1,2;StartTime=(Get-Date).AddHours(-2)} -MaxEvents 20 -ErrorAction SilentlyContinue; if ($events) { $events | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap; $crash = $events | Where-Object { $_.Id -eq 1001 -or $_.Message -match "BugCheck" }; if ($crash) { Write-Output "EVENTS: FAIL — crash dump detected, recommend rollback" } else { Write-Output "EVENTS: WARNING — errors found, assess for rollback" } } else { Write-Output "EVENTS: PASS" }' --no-wait
```

Then poll results (run for each server):

```shell
az connectedmachine run-command show --resource-group SERVER_RG --machine-name SERVER_NAME --name postPatchCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Also verify patches are no longer listed as Needed via Log Analytics. Replace `WORKSPACE_ID` from Step 2 and build the `in()` list from discovered server names:

```shell
az monitor log-analytics query --workspace WORKSPACE_ID --analytics-query "Update | where TimeGenerated >= ago(7d) | where UpdateState == 'Needed' | where Computer in ('SERVER1','SERVER2','SERVER3') | summarize MissingPatches=count(), CriticalCount=countif(MSRCSeverity == 'Critical'), SecurityCount=countif(MSRCSeverity == 'Important') by Computer | order by CriticalCount desc" -o table
```

### Post-patch summary

Present a table with one row per discovered server:

| Server | Resource Group | Rebooted | Services OK | Event Errors | Patches Cleared | Status |
|--------|---------------|----------|-------------|--------------|-----------------|--------|

## Step 7 — Rollback decision matrix

Do NOT auto-rollback. Present this assessment to the user:

| Condition | Recommendation | Priority |
|-----------|---------------|----------|
| Critical service down, won't start after 15 min | **Recommend rollback** | P1 — create ticket immediately |
| Blue screen / crash dump events (EVENTS: FAIL) | **Recommend rollback** | P1 — create ticket immediately |
| Non-critical service down | **Do NOT rollback** — restart the service | P3 |
| Event log warnings only | **Do NOT rollback** — monitor | P4 |
| All checks pass | **No rollback needed** | No ticket needed |

If all servers show PASS in post-patch summary → skip Step 8, report success.

## Step 8 — Create GLPI ticket if FAIL

Only if post-patch validation has FAIL or CRITICAL results requiring a ticket.

If GLPI is configured in your environment, initialize a session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'YOUR_GLPI_URL/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Patching] Post-patch validation FAIL: SERVER_NAME", "content": "DETAILED_FINDINGS_AND_ROLLBACK_RECOMMENDATION", "type": 1, "urgency": 5, "priority": 5}}' 'YOUR_GLPI_URL/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
