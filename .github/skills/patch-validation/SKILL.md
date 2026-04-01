---
name: patch-validation
description: Validates server health before and after Windows patch deployment. Assesses rollback need. Use when asked about patching, updates, KB status, or pre/post patch checks.
---

# Patch Validation

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Environment

- Subscription: `31adb513-7077-47bb-9567-8e9d2a462bcf`
- Resource Group: `rg-arcbox-itpro`
- Region: `swedencentral`
- Log Analytics Workspace ID: `f98fca75-7479-45e5-bf0c-87b56a9f9e8c`
- Windows servers: `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL`
- GLPI URL: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

## Step 1 — Query Azure Update Manager for patch status

Use Azure Resource Graph to get the current patch assessment:

```shell
az graph query -q "patchassessmentresources | where type == 'microsoft.hybridcompute/machines/patchassessmentresults' | where resourceGroup == 'rg-arcbox-itpro' | extend machineId = tostring(split(id, '/patchAssessmentResults')[0]) | extend machineName = tostring(split(machineId, '/')[8]) | extend status = tostring(properties.status) | extend criticalCount = toint(properties.availablePatchCountByClassification.critical) | extend securityCount = toint(properties.availablePatchCountByClassification.security) | extend lastAssessment = tostring(properties.lastModifiedDateTime) | project machineName, status, criticalCount, securityCount, lastAssessment" --subscriptions 31adb513-7077-47bb-9567-8e9d2a462bcf -o table
```

Also check recent patch installation results:

```shell
az graph query -q "patchinstallationresources | where type == 'microsoft.hybridcompute/machines/patchinstallationresults' | where resourceGroup == 'rg-arcbox-itpro' | extend machineName = tostring(split(id, '/')[8]) | extend status = tostring(properties.status) | extend installedCount = toint(properties.installedPatchCount) | extend failedCount = toint(properties.failedPatchCount) | extend lastModified = tostring(properties.lastModifiedDateTime) | project machineName, status, installedCount, failedCount, lastModified" --subscriptions 31adb513-7077-47bb-9567-8e9d2a462bcf -o table
```

## Pre-Patch Validation

Run these checks BEFORE any patch deployment. All must pass to proceed.

### Step 2 — Check disk space (minimum 20% free on C:)

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchDisk --location swedencentral --script "Get-PSDrive -Name C | ForEach-Object { \$pct=[math]::Round((\$_.Free/(\$_.Used+\$_.Free))*100,1); Write-Output \"C: \$pct% free (\$([math]::Round(\$_.Free/1GB,1))GB)\" }; if ((Get-PSDrive -Name C).Free / ((Get-PSDrive -Name C).Used + (Get-PSDrive -Name C).Free) -lt 0.2) { Write-Output 'FAIL: Less than 20% free' } else { Write-Output 'PASS' }" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchDisk --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

If output contains "FAIL" → **BLOCK patching** on this server.

### Step 3 — Check for pending reboot

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchReboot --location swedencentral --script "\$reboot = Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending'; \$wu = Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'; Write-Output \"CBS RebootPending: \$reboot\"; Write-Output \"WU RebootRequired: \$wu\"; if (\$reboot -or \$wu) { Write-Output 'WARNING: Reboot pending before patching' } else { Write-Output 'PASS: No pending reboot' }" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchReboot --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Pending reboot before patching → WARNING (reboot first, then patch).

### Step 4 — Record pre-patch services baseline

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchServices --location swedencentral --script "Get-Service | Where-Object { \$_.StartType -eq 'Automatic' -and \$_.Status -eq 'Running' } | Select-Object Name,Status | Sort-Object Name | Format-Table -AutoSize" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name prePatchServices --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Save this output as the baseline to compare against post-patch.

### Pre-Patch Summary

| Server | Disk Space | Pending Reboot | Services Baseline | Ready to Patch? |
|--------|-----------|----------------|-------------------|-----------------|
| ArcBox-Win2K22 | PASS/FAIL | PASS/WARN | Captured | YES/NO |
| ArcBox-Win2K25 | PASS/FAIL | PASS/WARN | Captured | YES/NO |
| ArcBox-SQL | PASS/FAIL | PASS/WARN | Captured | YES/NO |

## Post-Patch Validation

Run these checks AFTER patch deployment completes.

### Step 5 — Verify reboot completed

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchReboot --location swedencentral --script "\$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; Write-Output \"Last boot: \$boot\"; \$uptime = (Get-Date) - \$boot; Write-Output \"Uptime: \$([math]::Round(\$uptime.TotalMinutes,0)) minutes\"" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchReboot --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Verify the LastBootUpTime is AFTER the patch window start time.

### Step 6 — Compare services against pre-patch baseline

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchServices --location swedencentral --script "Get-Service | Where-Object { \$_.StartType -eq 'Automatic' -and \$_.Status -ne 'Running' } | Select-Object Name,Status,StartType | Format-Table -AutoSize" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchServices --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Any Auto-start service that was Running pre-patch and is now Stopped → **FAIL**.
- Critical services (WinRM, WinDefend, EventLog, W32Time) stopped → CRITICAL
- Other services stopped → WARNING

### Step 7 — Check event logs for post-patch errors

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchEvents --location swedencentral --script "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddHours(-2)} -MaxEvents 20 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name postPatchEvents --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

- Any Critical event post-patch → WARNING (assess for rollback)
- Crash dump events (Event ID 1001, BugCheck) → **FAIL — recommend rollback**

### Step 8 — Verify patches installed via Log Analytics

```shell
az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "Update | where TimeGenerated >= ago(7d) | where UpdateState == 'Needed' | where Computer in ('ArcBox-Win2K22','ArcBox-Win2K25','ArcBox-SQL') | summarize MissingPatches=count(), CriticalCount=countif(MSRCSeverity == 'Critical'), SecurityCount=countif(MSRCSeverity == 'Important') by Computer | order by CriticalCount desc" -o table
```

If patches are still showing as Needed after the patch window → WARNING (patches may not have installed).

### Post-Patch Summary

| Server | Rebooted | Services OK | Event Errors | Patches Cleared | Status |
|--------|----------|-------------|--------------|-----------------|--------|
| ArcBox-Win2K22 | YES/NO | PASS/FAIL | count | YES/NO | PASS / FAIL |
| ArcBox-Win2K25 | YES/NO | PASS/FAIL | count | YES/NO | PASS / FAIL |
| ArcBox-SQL | YES/NO | PASS/FAIL | count | YES/NO | PASS / FAIL |

## Step 9 — Rollback decision matrix

Do NOT auto-rollback. Present this assessment to the user:

| Condition | Recommendation | Priority |
|-----------|---------------|----------|
| Critical service down, won't start after 15 min | **Recommend rollback** | P1 — create ticket immediately |
| Blue screen / crash dump events | **Recommend rollback** | P1 — create ticket immediately |
| Non-critical service down | **Do NOT rollback** — restart the service | P3 |
| Event log warnings only | **Do NOT rollback** — monitor | P4 |
| All checks pass | **No rollback needed** | No ticket needed |

## Step 10 — Create GLPI ticket if FAIL

Only create a ticket if post-patch validation has any FAIL results.

First, initialize a GLPI session:

```shell
curl -s -X GET -H "Content-Type: application/json" -H "Authorization: user_token YOUR_TOKEN" -H "App-Token: YOUR_APP_TOKEN" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H "Content-Type: application/json" -H "Session-Token: SESSION_TOKEN" -H "App-Token: YOUR_APP_TOKEN" -d "{\"input\": {\"name\": \"[Patching] Post-patch validation FAIL: SERVER_NAME\", \"content\": \"DETAILED_FINDINGS_AND_ROLLBACK_RECOMMENDATION\", \"type\": 1, \"urgency\": 5, \"priority\": 5}}" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket"
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
