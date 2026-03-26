<#
.SYNOPSIS
    Deterministic Snapshot/Checkpoint Cleanup Automation (~90% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for VMware BAU tasks.
    Uses Hyper-V checkpoints (ArcBox uses Hyper-V nested VMs) to demonstrate
    snapshot lifecycle management: discovery, age analysis, cleanup recommendations.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Run from: ArcBox-Client VM (Hyper-V host) — Invoke-Command to nested VMs
    Note: If not on ArcBox-Client, shows simulated output
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$MaxCheckpointAgeDays = 7
$NestedUser = "arcdemo"
$NestedPass = ConvertTo-SecureString "JS123!!" -AsPlainText -Force
$NestedCred = New-Object System.Management.Automation.PSCredential($NestedUser, $NestedPass)
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC SNAPSHOT/CHECKPOINT CLEANUP              ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~90%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Checks: Hyper-V checkpoints, age analysis, disk impact        ║" -ForegroundColor Cyan
Write-Host "║  Action: Auto-delete old checkpoints, flag recent for review    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
#endregion

#region Helper
function Write-Status {
    param(
        [string]$Message,
        [ValidateSet("Pass", "Warn", "Critical", "Info")]
        [string]$Level = "Info"
    )
    switch ($Level) {
        "Pass"     { Write-Host "  [PASS]     $Message" -ForegroundColor Green }
        "Warn"     { Write-Host "  [WARN]     $Message" -ForegroundColor Yellow }
        "Critical" { Write-Host "  [CRITICAL] $Message" -ForegroundColor Red }
        "Info"     { Write-Host "  [INFO]     $Message" -ForegroundColor Gray }
    }
}
#endregion

#region Step 1: Discover Hyper-V VMs and checkpoints
Write-Host "━━━ Step 1: Discovering Hyper-V VMs and checkpoints ━━━" -ForegroundColor White

$isArcBoxClient = (hostname) -match "ArcBox-Client"
$checkpoints = @()

if ($isArcBoxClient) {
    try {
        # Get all Hyper-V VMs
        $vms = Get-VM -ErrorAction Stop
        Write-Status "Found $($vms.Count) Hyper-V VMs on this host" -Level "Pass"
        Write-Host ""

        foreach ($vm in $vms) {
            Write-Status "VM: $($vm.Name) | State: $($vm.State) | Uptime: $($vm.Uptime)" -Level "Info"

            $vmCheckpoints = Get-VMCheckpoint -VMName $vm.Name -ErrorAction SilentlyContinue
            if ($vmCheckpoints) {
                foreach ($cp in $vmCheckpoints) {
                    $ageDays = ((Get-Date) - $cp.CreationTime).Days
                    $checkpoints += [PSCustomObject]@{
                        VMName        = $vm.Name
                        CheckpointName = $cp.Name
                        CreationTime  = $cp.CreationTime
                        AgeDays       = $ageDays
                        ParentPath    = $cp.Path
                    }
                }
            }
        }

        Write-Host ""
        Write-Status "Found $($checkpoints.Count) total checkpoints across all VMs" -Level $(if ($checkpoints.Count -gt 0) { "Info" } else { "Pass" })
    }
    catch {
        Write-Status "Error accessing Hyper-V: $_" -Level "Warn"
        Write-Status "Falling back to simulated data" -Level "Info"
        $isArcBoxClient = $false
    }
}

if (-not $isArcBoxClient -or $checkpoints.Count -eq 0) {
    Write-Status "Not on ArcBox-Client or no checkpoints found — using simulated data" -Level "Info"
    Write-Host ""

    # Simulated checkpoint data for demo purposes
    $checkpoints = @(
        [PSCustomObject]@{
            VMName         = "ArcBox-Win2K22"
            CheckpointName = "Pre-patch 2024-12-01"
            CreationTime   = (Get-Date).AddDays(-15)
            AgeDays        = 15
            ParentPath     = "C:\VMs\ArcBox-Win2K22\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-Win2K22"
            CheckpointName = "Config change backup"
            CreationTime   = (Get-Date).AddDays(-3)
            AgeDays        = 3
            ParentPath     = "C:\VMs\ArcBox-Win2K22\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-Win2K19"
            CheckpointName = "Before SQL update"
            CreationTime   = (Get-Date).AddDays(-22)
            AgeDays        = 22
            ParentPath     = "C:\VMs\ArcBox-Win2K19\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-Win2K19"
            CheckpointName = "Monthly backup"
            CreationTime   = (Get-Date).AddDays(-8)
            AgeDays        = 8
            ParentPath     = "C:\VMs\ArcBox-Win2K19\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-SQL"
            CheckpointName = "Pre-migration snapshot"
            CreationTime   = (Get-Date).AddDays(-45)
            AgeDays        = 45
            ParentPath     = "C:\VMs\ArcBox-SQL\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-SQL"
            CheckpointName = "Post-config test"
            CreationTime   = (Get-Date).AddDays(-2)
            AgeDays        = 2
            ParentPath     = "C:\VMs\ArcBox-SQL\Snapshots"
        }
        [PSCustomObject]@{
            VMName         = "ArcBox-Ubuntu-01"
            CheckpointName = "Kernel update fallback"
            CreationTime   = (Get-Date).AddDays(-10)
            AgeDays        = 10
            ParentPath     = "C:\VMs\ArcBox-Ubuntu-01\Snapshots"
        }
    )
    Write-Status "Using $($checkpoints.Count) simulated checkpoints for demo" -Level "Info"
}
Write-Host ""
#endregion

#region Step 2: Analyze checkpoint age
Write-Host "━━━ Step 2: Checkpoint Age Analysis ━━━" -ForegroundColor White
Write-Host ""

Write-Host "  ┌──────────────────────┬──────────────────────────────┬────────┬──────────┐" -ForegroundColor White
Write-Host "  │ VM                   │ Checkpoint                   │ Age    │ Action   │" -ForegroundColor White
Write-Host "  ├──────────────────────┼──────────────────────────────┼────────┼──────────┤" -ForegroundColor White

$toDelete = @()
$toReview = @()
$toKeep = @()

foreach ($cp in $checkpoints | Sort-Object AgeDays -Descending) {
    $vmPad = $cp.VMName.PadRight(20).Substring(0, 20)
    $cpPad = $cp.CheckpointName.PadRight(28).Substring(0, 28)
    $agePad = "$($cp.AgeDays)d".PadRight(6)

    if ($cp.AgeDays -gt ($MaxCheckpointAgeDays * 3)) {
        # Very old — auto-delete
        $action = "DELETE"
        $color = "Red"
        $toDelete += $cp
    }
    elseif ($cp.AgeDays -gt $MaxCheckpointAgeDays) {
        # Old — flag for review but recommend deletion
        $action = "REVIEW"
        $color = "Yellow"
        $toReview += $cp
    }
    else {
        # Recent — keep
        $action = "KEEP"
        $color = "Green"
        $toKeep += $cp
    }

    $actionPad = $action.PadRight(8)
    Write-Host "  │ $vmPad │ $cpPad │ $agePad │ $actionPad │" -ForegroundColor $color
}

Write-Host "  └──────────────────────┴──────────────────────────────┴────────┴──────────┘" -ForegroundColor White
Write-Host ""

Write-Host "  Policy: Max checkpoint age = $MaxCheckpointAgeDays days" -ForegroundColor Gray
Write-Host "  • DELETE: Older than $($MaxCheckpointAgeDays * 3) days — auto-remove" -ForegroundColor Red
Write-Host "  • REVIEW: $MaxCheckpointAgeDays-$($MaxCheckpointAgeDays * 3) days — flag for human review" -ForegroundColor Yellow
Write-Host "  • KEEP:   Under $MaxCheckpointAgeDays days — retain" -ForegroundColor Green
Write-Host ""
#endregion

#region Step 3: Simulate cleanup actions
Write-Host "━━━ Step 3: Cleanup Actions ━━━" -ForegroundColor White
Write-Host ""

if ($toDelete.Count -gt 0) {
    Write-Host "  Checkpoints that WOULD be auto-deleted:" -ForegroundColor Red
    foreach ($d in $toDelete) {
        if ($isArcBoxClient -and (hostname) -match "ArcBox-Client") {
            Write-Status "Would run: Remove-VMCheckpoint -VMName '$($d.VMName)' -Name '$($d.CheckpointName)'" -Level "Info"
            # Uncomment below to actually delete:
            # Remove-VMCheckpoint -VMName $d.VMName -Name $d.CheckpointName -Confirm:$false
            Write-Status "SIMULATED: Deleted checkpoint '$($d.CheckpointName)' on $($d.VMName) ($($d.AgeDays) days old)" -Level "Critical"
        }
        else {
            Write-Status "AUTO-DELETE: '$($d.CheckpointName)' on $($d.VMName) — $($d.AgeDays) days old" -Level "Critical"
        }
    }
    Write-Host ""
}
else {
    Write-Status "No checkpoints old enough for auto-deletion" -Level "Pass"
    Write-Host ""
}

if ($toReview.Count -gt 0) {
    Write-Host "  Checkpoints flagged for HUMAN REVIEW:" -ForegroundColor Yellow
    foreach ($r in $toReview) {
        Write-Status "REVIEW: '$($r.CheckpointName)' on $($r.VMName) — $($r.AgeDays) days old" -Level "Warn"
        Write-Status "  → Automation cannot determine if this checkpoint is still needed" -Level "Info"
    }
    Write-Host ""
}

if ($toKeep.Count -gt 0) {
    Write-Host "  Checkpoints being RETAINED (under $MaxCheckpointAgeDays days):" -ForegroundColor Green
    foreach ($k in $toKeep) {
        Write-Status "KEEP: '$($k.CheckpointName)' on $($k.VMName) — $($k.AgeDays) days old" -Level "Pass"
    }
    Write-Host ""
}
#endregion

#region Step 4: Cleanup Summary
Write-Host "━━━ Step 4: Cleanup Summary Report ━━━" -ForegroundColor White
Write-Host ""
Write-Host "  ┌──────────────────────────────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ CHECKPOINT CLEANUP SUMMARY                                  │" -ForegroundColor White
Write-Host "  ├──────────────────────────────────────────────────────────────┤" -ForegroundColor White
Write-Host "  │ Total checkpoints found:    $("$($checkpoints.Count)".PadRight(33)) │" -ForegroundColor White
Write-Host "  │ Auto-deleted (>$($MaxCheckpointAgeDays * 3) days):     $("$($toDelete.Count)".PadRight(33)) │" -ForegroundColor $(if ($toDelete.Count -gt 0) { "Red" } else { "Green" })
Write-Host "  │ Flagged for review:         $("$($toReview.Count)".PadRight(33)) │" -ForegroundColor $(if ($toReview.Count -gt 0) { "Yellow" } else { "Green" })
Write-Host "  │ Retained (recent):          $("$($toKeep.Count)".PadRight(33)) │" -ForegroundColor Green
Write-Host "  └──────────────────────────────────────────────────────────────┘" -ForegroundColor White
Write-Host ""
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Cleanup completed in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds — manual takes ~30 minutes     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  No AI needed — deterministic automation handles this fully     ║" -ForegroundColor Green
Write-Host "║                                                                 ║" -ForegroundColor Green
Write-Host "║  Snapshot/checkpoint cleanup is rule-based: age threshold →     ║" -ForegroundColor Green
Write-Host "║  delete or keep. No interpretation or business context needed.  ║" -ForegroundColor Green
Write-Host "║  This is a perfect candidate for pure automation.               ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
#endregion
