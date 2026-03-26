<#
.SYNOPSIS
    Master script — runs all 6 deterministic automation demos in sequence.
.DESCRIPTION
    Executes each KPI demo script, tracks timing, and prints a final summary
    showing what automation solved and what's left for AI.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Run from: ArcBox-Client VM (full functionality) or any machine with az CLI
#>

$ErrorActionPreference = 'Continue'
$masterStart = Get-Date
$scriptDir = $PSScriptRoot

#region Banner
Clear-Host
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║                                                                          ║" -ForegroundColor Magenta
Write-Host "║      DETERMINISTIC AUTOMATION DEMO — ALL OPERATIONAL KPIs                ║" -ForegroundColor Magenta
Write-Host "║                                                                          ║" -ForegroundColor Magenta
Write-Host "║      Demonstrating what automation solves WITHOUT AI                     ║" -ForegroundColor Magenta
Write-Host "║      Then showing where SRE Agent adds the remaining value               ║" -ForegroundColor Magenta
Write-Host "║                                                                          ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)" -ForegroundColor Gray
Write-Host "  Running on:  $(hostname)" -ForegroundColor Gray
Write-Host "  Started at:  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""
#endregion

#region Define scripts
$demos = @(
    @{
        Name       = "Health Check"
        Script     = "demo-health-check.ps1"
        Coverage   = "90%"
        AiGap      = "Interpretation, trends, correlation"
        Duration   = $null
    },
    @{
        Name       = "Compliance Report"
        Script     = "demo-compliance-report.ps1"
        Coverage   = "95%"
        AiGap      = "Executive narrative, prioritization"
        Duration   = $null
    },
    @{
        Name       = "Alert Monitoring"
        Script     = "demo-alert-monitoring.ps1"
        Coverage   = "70%"
        AiGap      = "Correlation, root cause, remediation"
        Duration   = $null
    },
    @{
        Name       = "CMDB Sync"
        Script     = "demo-cmdb-sync.ps1"
        Coverage   = "85%"
        AiGap      = "None — fully deterministic"
        Duration   = $null
    },
    @{
        Name       = "Patch Assessment"
        Script     = "demo-patch-assessment.ps1"
        Coverage   = "85%"
        AiGap      = "Risk assessment, wave grouping"
        Duration   = $null
    },
    @{
        Name       = "Snapshot Cleanup"
        Script     = "demo-snapshot-cleanup.ps1"
        Coverage   = "90%"
        AiGap      = "None — fully deterministic"
        Duration   = $null
    }
)
#endregion

#region Run each demo
$results = @()
$demoIndex = 0

foreach ($demo in $demos) {
    $demoIndex++
    $scriptPath = Join-Path $scriptDir $demo.Script

    Write-Host ""
    Write-Host "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓" -ForegroundColor White
    Write-Host "┃  DEMO $demoIndex of $($demos.Count): $($demo.Name.ToUpper().PadRight(54)) ┃" -ForegroundColor White
    Write-Host "┃  Script: $($demo.Script.PadRight(59)) ┃" -ForegroundColor White
    Write-Host "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛" -ForegroundColor White
    Write-Host ""

    if (Test-Path $scriptPath) {
        $demoStart = Get-Date
        try {
            & $scriptPath
            $demoEnd = Get-Date
            $duration = $demoEnd - $demoStart
            $demo.Duration = $duration

            $results += [PSCustomObject]@{
                Name     = $demo.Name
                Status   = "Completed"
                Duration = "{0:mm\:ss}" -f $duration
                Coverage = $demo.Coverage
                AiGap    = $demo.AiGap
            }
        }
        catch {
            $demoEnd = Get-Date
            $duration = $demoEnd - $demoStart
            $demo.Duration = $duration

            Write-Host "  ERROR running $($demo.Script): $_" -ForegroundColor Red
            $results += [PSCustomObject]@{
                Name     = $demo.Name
                Status   = "Failed"
                Duration = "{0:mm\:ss}" -f $duration
                Coverage = $demo.Coverage
                AiGap    = $demo.AiGap
            }
        }
    }
    else {
        Write-Host "  Script not found: $scriptPath" -ForegroundColor Red
        $results += [PSCustomObject]@{
            Name     = $demo.Name
            Status   = "Not Found"
            Duration = "—"
            Coverage = $demo.Coverage
            AiGap    = $demo.AiGap
        }
    }

    if ($demoIndex -lt $demos.Count) {
        Write-Host ""
        Write-Host "  ─────────────────────────── Next demo in 2 seconds ───────────────────────────" -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }
}
#endregion

#region Final Summary
$masterEnd = Get-Date
$masterDuration = $masterEnd - $masterStart

Write-Host ""
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║                     FINAL SUMMARY — ALL DEMOS                            ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

Write-Host "  ┌──────────────────────┬───────────┬──────────┬──────────┬─────────────────────────────────────────┐" -ForegroundColor White
Write-Host "  │ KPI                  │ Status    │ Time     │ Coverage │ What AI Adds                            │" -ForegroundColor White
Write-Host "  ├──────────────────────┼───────────┼──────────┼──────────┼─────────────────────────────────────────┤" -ForegroundColor White

foreach ($r in $results) {
    $namePad = $r.Name.PadRight(20).Substring(0, 20)
    $statusPad = $r.Status.PadRight(9).Substring(0, 9)
    $timePad = $r.Duration.PadRight(8).Substring(0, 8)
    $covPad = $r.Coverage.PadRight(8).Substring(0, 8)
    $gapPad = $r.AiGap.PadRight(39).Substring(0, 39)
    $statusColor = switch ($r.Status) {
        "Completed" { "Green" }
        "Failed"    { "Red" }
        default     { "Yellow" }
    }
    Write-Host "  │ $namePad │ $statusPad │ $timePad │ $covPad │ $gapPad │" -ForegroundColor $statusColor
}

Write-Host "  └──────────────────────┴───────────┴──────────┴──────────┴─────────────────────────────────────────┘" -ForegroundColor White
Write-Host ""

Write-Host "  Total automation time: $("{0:mm\:ss}" -f $masterDuration)" -ForegroundColor Green
Write-Host "  Manual equivalent:     ~5+ hours" -ForegroundColor Red
Write-Host "  Time saved:            ~98% reduction" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  KEY TAKEAWAY                                                            ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║                                                                          ║" -ForegroundColor Cyan
Write-Host "║  Deterministic automation handles ~85% of operational tasks.             ║" -ForegroundColor Cyan
Write-Host "║  It excels at: data collection, threshold checks, API calls,             ║" -ForegroundColor Cyan
Write-Host "║  CMDB sync, report generation, and rule-based actions.                   ║" -ForegroundColor Cyan
Write-Host "║                                                                          ║" -ForegroundColor Cyan
Write-Host "║  The SRE Agent adds value for the remaining ~15%:                        ║" -ForegroundColor Cyan
Write-Host "║  • Interpreting WHY issues occur (root cause analysis)                   ║" -ForegroundColor Cyan
Write-Host "║  • Correlating multiple signals into a single narrative                  ║" -ForegroundColor Cyan
Write-Host "║  • Recommending specific, context-aware remediation                      ║" -ForegroundColor Cyan
Write-Host "║  • Writing executive summaries and CAB justifications                    ║" -ForegroundColor Cyan
Write-Host "║  • Assessing business risk and impact                                    ║" -ForegroundColor Cyan
Write-Host "║                                                                          ║" -ForegroundColor Cyan
Write-Host "║  Together: Automation + AI = 100% operational coverage                   ║" -ForegroundColor Cyan
Write-Host "║                                                                          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
#endregion
