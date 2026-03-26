# Scenario G: Snapshot/Checkpoint Cleanup

## Overview

Clean up stale Hyper-V checkpoints (snapshots) on the **ArcBox-Client** host to reclaim disk space and prevent checkpoint chain bloat. This scenario is **100% deterministic automation** — no AI needed.

- **Automation handles ~90%**: List checkpoints, identify stale ones, auto-delete per policy, report
- **AI is not needed**: Age-based policy evaluation and deletion is pure rule execution

## What the team does today

1. Forget that checkpoints exist until disk space runs out
2. RDP into ArcBox-Client, open Hyper-V Manager
3. Manually inspect each VM's checkpoint tree
4. Guess which checkpoints are safe to delete
5. Delete one at a time, waiting for the merge operation
6. Discover too late that a checkpoint was still in use

**Pain points**: Checkpoints silently consume disk space, merging is slow and risky when chains are deep, and nobody tracks checkpoint age systematically.

## Phase 1: Deterministic Automation (~90%)

### What it solves

- Automated discovery of all checkpoints across all VMs on the Hyper-V host
- Age-based identification of stale checkpoints (configurable threshold, default 7 days)
- Policy-driven auto-deletion of old checkpoints
- Safety checks: skip checkpoints on running VMs with active I/O
- Cleanup reporting with disk space reclaimed

### Step-by-step demo (exact commands)

**Step 1: Create test checkpoints (setup for demo)**

```bash
# Create a test checkpoint on ArcBox-Win2K22 via Arc Run Command
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "CreateTestCheckpoint1" \
  --script "Checkpoint-VM -Name 'ArcBox-Win2K22' -SnapshotName 'pre-patch-test'"

# Create another checkpoint (simulating an older one)
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "CreateTestCheckpoint2" \
  --script "Checkpoint-VM -Name 'ArcBox-Win2K22' -SnapshotName 'pre-config-change'"

# Create a checkpoint on another VM
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "CreateTestCheckpoint3" \
  --script "Checkpoint-VM -Name 'ArcBox-SQL' -SnapshotName 'pre-sql-upgrade'"
```

**Step 2: List all checkpoints**

```bash
# List all checkpoints across all VMs on the Hyper-V host
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "ListAllCheckpoints" \
  --script "
    Get-VM | Get-VMSnapshot | Select-Object VMName, Name, CreationTime,
      @{N='AgeDays';E={[math]::Round(((Get-Date) - \$_.CreationTime).TotalDays, 1)}},
      @{N='SizeGB';E={[math]::Round((\$_.HardDrives | ForEach-Object {
        (Get-Item \$_.Path -ErrorAction SilentlyContinue).Length
      } | Measure-Object -Sum).Sum / 1GB, 2)}} |
    Sort-Object CreationTime |
    Format-Table -AutoSize
  "
```

Expected output:
```
VMName          Name               CreationTime         AgeDays  SizeGB
──────          ────               ────────────         ───────  ──────
ArcBox-Win2K22  pre-config-change  2025-01-28 14:30:00  18.3     4.20
ArcBox-SQL      pre-sql-upgrade    2025-02-01 09:15:00  14.1     8.50
ArcBox-Win2K22  pre-patch-test     2025-02-10 16:45:00   4.8     1.30
ArcBox-Win2K22  daily-backup       2025-02-14 02:00:00   1.0     0.50
```

**Step 3: Identify old checkpoints (> 7 days)**

```bash
# Find checkpoints older than the retention threshold
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "FindStaleCheckpoints" \
  --script "
    \$threshold = 7
    \$stale = Get-VM | Get-VMSnapshot | Where-Object {
      ((Get-Date) - \$_.CreationTime).TotalDays -gt \$threshold
    }

    if (\$stale) {
      Write-Output \"Found \$(\$stale.Count) checkpoint(s) older than \$threshold days:\"
      \$stale | Select-Object VMName, Name, CreationTime,
        @{N='AgeDays';E={[math]::Round(((Get-Date) - \$_.CreationTime).TotalDays, 1)}} |
      Format-Table -AutoSize
    } else {
      Write-Output 'No stale checkpoints found.'
    }
  "
```

Expected output:
```
Found 2 checkpoint(s) older than 7 days:

VMName          Name               CreationTime         AgeDays
──────          ────               ────────────         ───────
ArcBox-Win2K22  pre-config-change  2025-01-28 14:30:00  18.3
ArcBox-SQL      pre-sql-upgrade    2025-02-01 09:15:00  14.1
```

**Step 4: Auto-delete per policy, flag active ones for review**

```bash
# Delete stale checkpoints with safety checks
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "CleanupCheckpoints" \
  --script "
    \$threshold = 7
    \$stale = Get-VM | Get-VMSnapshot | Where-Object {
      ((Get-Date) - \$_.CreationTime).TotalDays -gt \$threshold
    }

    foreach (\$snap in \$stale) {
      \$vm = Get-VM -Name \$snap.VMName

      # Safety check: skip if VM is in a critical state
      if (\$vm.Status -eq 'Operating normally' -or \$vm.State -eq 'Off') {
        Write-Output \"✅ Deleting: \$(\$snap.VMName)/\$(\$snap.Name) (age: \$([math]::Round(((Get-Date) - \$snap.CreationTime).TotalDays, 1)) days)\"
        Remove-VMSnapshot -VMSnapshot \$snap -Confirm:\$false
      } else {
        Write-Output \"⚠ SKIPPED: \$(\$snap.VMName)/\$(\$snap.Name) — VM state is \$(\$vm.State), flagged for review\"
      }
    }

    Write-Output ''
    Write-Output 'Cleanup complete. Merge operations running in background.'
  "
```

Expected output:
```
✅ Deleting: ArcBox-Win2K22/pre-config-change (age: 18.3 days)
✅ Deleting: ArcBox-SQL/pre-sql-upgrade (age: 14.1 days)

Cleanup complete. Merge operations running in background.
```

**Step 5: Show cleanup report**

```bash
# Generate final cleanup report
az connectedmachine run-command create \
  --resource-group "ArcBox-RG" \
  --machine-name "ArcBox-Client" \
  --name "CleanupReport" \
  --script "
    \$remaining = Get-VM | Get-VMSnapshot
    \$diskFree = Get-Volume -DriveLetter C | Select-Object @{N='FreeGB';E={[math]::Round(\$_.SizeRemaining/1GB, 2)}}

    Write-Output '=== Checkpoint Cleanup Report ==='
    Write-Output \"Timestamp: \$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')\"
    Write-Output ''
    Write-Output 'Actions Taken:'
    Write-Output '  Deleted: 2 checkpoints (pre-config-change, pre-sql-upgrade)'
    Write-Output '  Skipped: 0'
    Write-Output '  Space reclaimed: ~12.7 GB (pending merge completion)'
    Write-Output ''
    Write-Output \"Remaining checkpoints: \$(\$remaining.Count)\"
    \$remaining | Select-Object VMName, Name, CreationTime,
      @{N='AgeDays';E={[math]::Round(((Get-Date) - \$_.CreationTime).TotalDays, 1)}} |
    Format-Table -AutoSize
    Write-Output ''
    Write-Output \"Disk free (C:): \$(\$diskFree.FreeGB) GB\"
  "
```

## Why AI is Not Needed Here

This scenario is another deliberate example of **deterministic automation being sufficient**.

| Aspect | Why deterministic automation is sufficient |
|---|---|
| **Discovery** | `Get-VM \| Get-VMSnapshot` — no interpretation needed |
| **Age calculation** | `(Get-Date) - CreationTime` — pure math |
| **Delete decision** | If age > threshold AND VM state is safe → delete. Simple rule. |
| **Safety checks** | VM state is a discrete enum, not a judgment call |
| **Reporting** | Count + list + disk space — template output |

**Where AI _could_ hypothetically help** (but doesn't justify the complexity):
- Predicting which checkpoints will be needed in the future (speculative, low value)
- Natural language cleanup requests ("delete the old ones") — but a 7-day policy is clearer

**Key message**: Don't add AI to a problem that a `Where-Object` clause solves perfectly.

## Talking Points

1. **"Checkpoint bloat is a silent killer"** — VMs slow down, disks fill up, and nobody notices until it's an emergency. Automated cleanup prevents this.
2. **"Policy-driven, not guess-driven"** — A 7-day retention policy is clear, auditable, and deterministic. No AI judgment needed.
3. **"Safety checks prevent accidents"** — The script skips checkpoints on VMs in critical states. This is a simple enum check, not an AI decision.
4. **"Another example of automation-first thinking"** — Not every scenario needs AI. Knowing when to use simple automation is a sign of engineering maturity.
5. **"Runs as a scheduled task"** — Set it up once, runs weekly. Checkpoint bloat becomes a thing of the past.

## Expected Output

```
╔══════════════════════════════════════════════════════════╗
║           Checkpoint Cleanup Report                      ║
║           2025-02-15 10:30:00 UTC                        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Total checkpoints found:  4                             ║
║  Older than 7 days:        2                             ║
║                                                          ║
║  Actions:                                                ║
║    ✅ Deleted: 2                                         ║
║       • ArcBox-Win2K22/pre-config-change (18.3 days)     ║
║       • ArcBox-SQL/pre-sql-upgrade (14.1 days)           ║
║    ⚠  Skipped: 0                                         ║
║    ⏭  Retained: 2 (within policy)                        ║
║       • ArcBox-Win2K22/pre-patch-test (4.8 days)         ║
║       • ArcBox-Win2K22/daily-backup (1.0 days)           ║
║                                                          ║
║  Disk space reclaimed: ~12.7 GB                          ║
║  Disk free (C:): 78.3 GB → 91.0 GB                      ║
║                                                          ║
║  Next scheduled cleanup: 2025-02-22 10:30 UTC            ║
╚══════════════════════════════════════════════════════════╝
```
