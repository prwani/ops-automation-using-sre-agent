# Scenario E: Monthly Patching

## Overview

Monthly OS patching is a critical maintenance task that every ops team must perform reliably. This scenario uses **Azure Update Manager** to assess, deploy, and validate patches across ArcBox VMs — with an AI-powered Patch Risk Agent that recommends wave grouping and flags risky KBs.

- **Automation handles ~85%**: Assessment, scheduled deployment, pre/post validation, auto-rollback
- **AI adds ~15%**: Patch risk scoring, wave grouping recommendations, post-patch failure analysis

## What the team does today

1. Manually check each VM for pending updates (RDP in, open Windows Update)
2. Schedule a maintenance window in a shared calendar
3. Patch servers one-by-one, hoping nothing breaks
4. Manually verify services are running after reboot
5. When something breaks, scramble to figure out which KB caused it
6. Roll back by restoring from a checkpoint (if they remembered to create one)

**Pain points**: No risk assessment before patching, no automated pre/post validation, rollback is manual and error-prone.

## Phase 1: Deterministic Automation (~85%)

### What it solves

- Automated patch assessment across all ArcBox VMs
- Pre-patch validation (disk space, pending reboots, service state)
- Scheduled deployment with maintenance windows
- Post-patch validation (services running, event log errors)
- Auto-rollback when post-checks fail

### Step-by-step demo (exact commands)

**Step 1: Assess pending updates**

```bash
# List pending updates for all Arc-enabled VMs
az update-management list-updates \
  --resource-group "ArcBox-RG" \
  --name "ArcBox-Win2K22"

# Or query across all machines via Resource Graph
az graph query -q "
  patchassessmentresources
  | where type == 'microsoft.hybridcompute/machines/patchassessmentresults/softwarepatches'
  | where properties.patchName contains 'KB'
  | summarize PendingCount=count() by tostring(properties.version), tostring(properties.classifications)
"
```

**Step 2: Pre-checks via Arc Run Command**

```bash
# Check disk space on target VM
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "PrePatchDiskCheck" \
  --script "Get-Volume | Where-Object {$_.SizeRemaining -lt 1GB} | Select DriveLetter, @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,2)}}"

# Check for pending reboots
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "PrePatchRebootCheck" \
  --script "Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'"

# Capture current service state baseline
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "PrePatchServiceBaseline" \
  --script "Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -eq 'Running'} | Select Name, Status | ConvertTo-Json"
```

**Step 3: Schedule patch deployment**

```bash
# Create a maintenance configuration
az maintenance configuration create \
  --resource-group "ArcBox-RG" \
  --name "MonthlyPatching" \
  --maintenanceScope "InGuestPatch" \
  --install-patches-linux-parameters packageNameMasksToInclude="*" classificationsToInclude="Critical,Security" \
  --install-patches-windows-parameters classificationsToInclude="Critical,Security" kbNumbersToExclude="" \
  --reboot-setting "IfRequired" \
  --schedule-start-date-time "2025-02-15 02:00" \
  --schedule-time-zone "Eastern Standard Time" \
  --schedule-recur-every "Month"

# Assign VMs to the maintenance configuration
az maintenance assignment create \
  --resource-group "ArcBox-RG" \
  --maintenance-configuration-id "/subscriptions/{sub}/resourceGroups/ArcBox-RG/providers/Microsoft.Maintenance/maintenanceConfigurations/MonthlyPatching" \
  --name "ArcBox-Win2K22-Assignment" \
  --provider-name "Microsoft.HybridCompute" \
  --resource-name "ArcBox-Win2K22" \
  --resource-type "machines"
```

**Step 4: Post-patch validation**

```bash
# Check services are running (compare to baseline)
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "PostPatchServiceCheck" \
  --script "
    \$failed = Get-Service | Where-Object {\$_.StartType -eq 'Automatic' -and \$_.Status -ne 'Running'}
    if (\$failed) {
      Write-Output 'FAILED SERVICES:'
      \$failed | Select Name, Status | Format-Table
      exit 1
    } else {
      Write-Output 'All automatic services running OK'
    }
  "

# Check event log for post-patch errors
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "PostPatchEventLogCheck" \
  --script "Get-EventLog -LogName System -EntryType Error -After (Get-Date).AddHours(-2) | Select TimeGenerated, Source, Message | Format-Table -Wrap"
```

**Step 5: Auto-rollback on failure**

```bash
# If post-checks fail, trigger rollback
# (In practice, this would be orchestrated by a workflow)
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Win2K22" \
  --name "RollbackPatch" \
  --script "
    # Restore from pre-patch checkpoint (on Hyper-V host)
    Restore-VMSnapshot -Name 'pre-patch' -VMName 'ArcBox-Win2K22' -Confirm:\$false
    Write-Output 'Rolled back to pre-patch checkpoint'
  "
```

### What automation CANNOT do

- **Predict** which patches are risky for your specific environment
- **Decide** the optimal wave grouping (which servers to patch first)
- **Correlate** a post-patch failure with a specific KB across historical data
- **Recommend** whether to proceed, delay, or skip a specific update

## Phase 2: AI Adds the Remaining ~15%

The **SRE Agent** brings intelligence to what is otherwise a mechanical process.

### What AI adds

| Capability | How it works |
|---|---|
| **Patch risk scoring** | Analyzes KB history, vendor advisories, and your environment config to score risk |
| **Wave grouping** | Recommends which VMs to patch first (dev → staging → prod) based on dependencies |
| **Risky KB flagging** | Flags KBs with known issues or incompatibilities for your installed software |
| **Post-patch failure analysis** | Correlates failed services/errors with specific KBs that were installed |

### Demo: Ask the SRE Agent

```
User: "Assess patch risk for ArcBox-Win2K22"

SRE Agent Response:
┌─────────────────────────────────────────────────────────┐
│ Patch Risk Assessment: ArcBox-Win2K22                   │
├─────────────────────────────────────────────────────────┤
│ Pending Updates: 12 (6 Critical, 4 Security, 2 Other)  │
│ Overall Risk: MEDIUM                                     │
│                                                          │
│ ⚠ Flagged KBs:                                          │
│   KB5034441 - Known issue with WinRE partition < 250MB  │
│   KB5034439 - Requires .NET 4.8.1, not detected on VM   │
│                                                          │
│ Recommended Wave Order:                                  │
│   Wave 1: ArcBox-Ubuntu (low risk, non-critical)        │
│   Wave 2: ArcBox-Win2K22 (medium risk, apply after W1)  │
│   Wave 3: ArcBox-SQL (high risk, SQL dependency)         │
│                                                          │
│ Pre-patch Actions Required:                              │
│   1. Extend WinRE partition on ArcBox-Win2K22            │
│   2. Install .NET 4.8.1 before applying KB5034439        │
└─────────────────────────────────────────────────────────┘
```

## Talking Points

1. **"Patching is not just installing updates"** — it's assessment, risk analysis, validation, and rollback. Automation handles the mechanical parts; AI handles the judgment calls.
2. **"Wave grouping saves outages"** — patching everything at once is how you get P1 incidents at 3am. The AI recommends a safe order.
3. **"KB flagging prevents known-bad patches"** — Microsoft occasionally releases patches with known issues. The AI catches these before you deploy.
4. **"Post-patch correlation is the killer feature"** — when SQL Server stops after patching, the AI can tell you it was KB5034439 that requires .NET 4.8.1, not a random failure.
5. **"Auto-rollback is your safety net"** — if post-checks fail, automation rolls back immediately. No waiting for someone to wake up and RDP in.

## Expected Output

```
=== Monthly Patching Report: ArcBox-Win2K22 ===

Assessment:
  Pending updates: 12
  Critical: 6 | Security: 4 | Other: 2
  AI Risk Score: MEDIUM (2 flagged KBs)

Pre-Checks:
  ✅ Disk space: 45GB free on C:
  ✅ No pending reboots
  ✅ 47 automatic services running (baseline captured)
  ⚠  KB5034441 flagged — WinRE partition only 200MB

Deployment:
  Maintenance window: 2025-02-15 02:00-06:00 EST
  Wave: 2 of 3 (after Ubuntu validation)
  Patches applied: 11/12 (KB5034441 deferred per AI recommendation)
  Reboot: Yes (completed in 3m 22s)

Post-Checks:
  ✅ All 47 automatic services running
  ✅ No critical event log errors in last 2 hours
  ✅ RDP connectivity verified
  ✅ Application health checks passed

Result: SUCCESS — 11 patches applied, 1 deferred
Next action: Review KB5034441 after WinRE partition resize
```
