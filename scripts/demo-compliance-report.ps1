<#
.SYNOPSIS
    Deterministic Compliance Reporting Automation (~95% automated)
.DESCRIPTION
    Demonstrates what automation can do WITHOUT AI for compliance reporting.
    Queries Defender for Cloud, Azure Policy, and secure score, then generates a formatted report.
.NOTES
    Environment: ArcBox-ITPro (rg-arcbox-itpro, swedencentral)
    Run from: Any machine with az CLI authenticated
#>

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

#region Configuration
$ResourceGroup = "rg-arcbox-itpro"
$SubscriptionScope = ""  # Will be set dynamically
#endregion

#region Banner
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DETERMINISTIC COMPLIANCE REPORTING                     ║" -ForegroundColor Cyan
Write-Host "║          Automation Coverage: ~95%                              ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Sources: Defender for Cloud, Azure Policy, Secure Score        ║" -ForegroundColor Cyan
Write-Host "║  Output:  Formatted compliance report with non-compliant items  ║" -ForegroundColor Cyan
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

#region Step 1: Regulatory Compliance Standards
Write-Host "━━━ Step 1: Defender for Cloud — Regulatory Compliance ━━━" -ForegroundColor White
try {
    $standards = az security regulatory-compliance-standards list 2>&1
    if ($LASTEXITCODE -eq 0) {
        $standardsData = $standards | ConvertFrom-Json
        Write-Status "Found $($standardsData.Count) regulatory compliance standards" -Level "Pass"
        Write-Host ""
        Write-Host "  ┌────────────────────────────────────────────┬──────────┬──────────┬──────────┐" -ForegroundColor White
        Write-Host "  │ Standard                                   │ State    │ Passed   │ Failed   │" -ForegroundColor White
        Write-Host "  ├────────────────────────────────────────────┼──────────┼──────────┼──────────┤" -ForegroundColor White

        foreach ($std in $standardsData) {
            $name = ($std.name).PadRight(42).Substring(0, 42)
            $state = ($std.state).PadRight(8).Substring(0, 8)
            $passed = "$($std.passedControls)".PadRight(8)
            $failed = "$($std.failedControls)".PadRight(8)
            $color = if ([int]$std.failedControls -gt 0) { "Yellow" } else { "Green" }
            Write-Host "  │ $name │ $state │ $passed │ $failed │" -ForegroundColor $color
        }
        Write-Host "  └────────────────────────────────────────────┴──────────┴──────────┴──────────┘" -ForegroundColor White
    }
    else {
        Write-Status "Regulatory compliance query not available (Defender plan may not be enabled)" -Level "Warn"
        Write-Status "Command: az security regulatory-compliance-standards list" -Level "Info"
    }
}
catch {
    Write-Status "Error querying regulatory compliance: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Step 2: Azure Policy Compliance Summary
Write-Host "━━━ Step 2: Azure Policy Compliance Summary ━━━" -ForegroundColor White
try {
    $policySummary = az policy state summarize --resource-group $ResourceGroup 2>&1
    if ($LASTEXITCODE -eq 0) {
        $policyData = $policySummary | ConvertFrom-Json

        $totalPolicies = 0
        $nonCompliantPolicies = 0
        if ($policyData.policyAssignments) {
            $totalPolicies = $policyData.policyAssignments.Count
            $nonCompliantPolicies = ($policyData.policyAssignments | Where-Object {
                $_.results.nonCompliantResources -gt 0
            }).Count
        }

        $nonCompliantResources = 0
        if ($policyData.results) {
            $nonCompliantResources = $policyData.results.nonCompliantResources
        }

        Write-Status "Policy assignments evaluated: $totalPolicies" -Level "Info"

        if ($nonCompliantResources -gt 0) {
            Write-Status "Non-compliant resources: $nonCompliantResources" -Level "Critical"
            Write-Status "Non-compliant policies: $nonCompliantPolicies" -Level "Warn"
        }
        else {
            Write-Status "All resources compliant!" -Level "Pass"
        }

        # Show top non-compliant policies
        if ($policyData.policyAssignments) {
            $nonCompliant = $policyData.policyAssignments |
                Where-Object { $_.results.nonCompliantResources -gt 0 } |
                Sort-Object { $_.results.nonCompliantResources } -Descending |
                Select-Object -First 10

            if ($nonCompliant) {
                Write-Host ""
                Write-Host "  Top non-compliant policy assignments:" -ForegroundColor Yellow
                Write-Host "  ┌────────────────────────────────────────────────┬───────────────┐" -ForegroundColor White
                Write-Host "  │ Policy Assignment                              │ Non-Compliant │" -ForegroundColor White
                Write-Host "  ├────────────────────────────────────────────────┼───────────────┤" -ForegroundColor White

                foreach ($nc in $nonCompliant) {
                    $displayName = if ($nc.policyAssignmentId.Length -gt 46) {
                        $nc.policyAssignmentId.Split("/")[-1].PadRight(46).Substring(0, 46)
                    } else {
                        $nc.policyAssignmentId.Split("/")[-1].PadRight(46)
                    }
                    $count = "$($nc.results.nonCompliantResources)".PadRight(13)
                    Write-Host "  │ $displayName │ $count │" -ForegroundColor Yellow
                }
                Write-Host "  └────────────────────────────────────────────────┴───────────────┘" -ForegroundColor White
            }
        }
    }
    else {
        Write-Status "Policy state query failed — ensure az CLI is authenticated" -Level "Warn"
    }
}
catch {
    Write-Status "Error querying policy compliance: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Step 3: Non-Compliant Resources Detail
Write-Host "━━━ Step 3: Non-Compliant Resources Detail ━━━" -ForegroundColor White
try {
    $ncResources = az policy state list --resource-group $ResourceGroup `
        --filter "complianceState eq 'NonCompliant'" --query "[].{Resource:resourceId, Policy:policyDefinitionName, State:complianceState}" 2>&1

    if ($LASTEXITCODE -eq 0) {
        $ncData = $ncResources | ConvertFrom-Json

        if ($ncData -and $ncData.Count -gt 0) {
            Write-Status "Found $($ncData.Count) non-compliant resource evaluations" -Level "Warn"
            Write-Host ""
            Write-Host "  ┌────────────────────────────────────┬────────────────────────────────────┐" -ForegroundColor White
            Write-Host "  │ Resource                           │ Policy                             │" -ForegroundColor White
            Write-Host "  ├────────────────────────────────────┼────────────────────────────────────┤" -ForegroundColor White

            $displayed = @{}
            foreach ($res in $ncData | Select-Object -First 15) {
                $resourceName = $res.Resource.Split("/")[-1]
                $policyName = $res.Policy
                $key = "$resourceName|$policyName"
                if ($displayed.ContainsKey($key)) { continue }
                $displayed[$key] = $true

                $resPad = $resourceName.PadRight(34).Substring(0, 34)
                $polPad = $policyName.PadRight(34).Substring(0, 34)
                Write-Host "  │ $resPad │ $polPad │" -ForegroundColor Red
            }
            Write-Host "  └────────────────────────────────────┴────────────────────────────────────┘" -ForegroundColor White
        }
        else {
            Write-Status "No non-compliant resources found — excellent!" -Level "Pass"
        }
    }
    else {
        Write-Status "Non-compliant resource query failed" -Level "Warn"
    }
}
catch {
    Write-Status "Error listing non-compliant resources: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Step 4: Defender Secure Score
Write-Host "━━━ Step 4: Defender for Cloud — Secure Score ━━━" -ForegroundColor White
try {
    $secureScore = az security secure-score-controls list 2>&1
    if ($LASTEXITCODE -eq 0) {
        $scoreData = $secureScore | ConvertFrom-Json

        if ($scoreData -and $scoreData.Count -gt 0) {
            $totalCurrent = ($scoreData | Measure-Object -Property currentScore -Sum).Sum
            $totalMax = ($scoreData | Measure-Object -Property maxScore -Sum).Sum
            $scorePct = if ($totalMax -gt 0) { [math]::Round(($totalCurrent / $totalMax) * 100, 1) } else { 0 }

            $scoreColor = if ($scorePct -ge 80) { "Pass" } elseif ($scorePct -ge 60) { "Warn" } else { "Critical" }
            Write-Status "Secure Score: $totalCurrent / $totalMax ($scorePct%)" -Level $scoreColor
            Write-Host ""

            Write-Host "  Secure Score Controls:" -ForegroundColor White
            Write-Host "  ┌──────────────────────────────────────────────┬─────────┬─────────┐" -ForegroundColor White
            Write-Host "  │ Control                                      │ Current │ Max     │" -ForegroundColor White
            Write-Host "  ├──────────────────────────────────────────────┼─────────┼─────────┤" -ForegroundColor White

            foreach ($ctrl in $scoreData | Sort-Object { $_.maxScore - $_.currentScore } -Descending | Select-Object -First 15) {
                $name = ($ctrl.displayName ?? $ctrl.name).PadRight(44).Substring(0, 44)
                $current = "$($ctrl.currentScore)".PadRight(7)
                $max = "$($ctrl.maxScore)".PadRight(7)
                $color = if ($ctrl.currentScore -eq $ctrl.maxScore) { "Green" } elseif ($ctrl.currentScore -gt 0) { "Yellow" } else { "Red" }
                Write-Host "  │ $name │ $current │ $max │" -ForegroundColor $color
            }
            Write-Host "  └──────────────────────────────────────────────┴─────────┴─────────┘" -ForegroundColor White
        }
        else {
            Write-Status "No secure score data available" -Level "Warn"
        }
    }
    else {
        Write-Status "Secure score query not available (Defender plan may not be enabled)" -Level "Warn"
    }
}
catch {
    Write-Status "Error querying secure score: $_" -Level "Warn"
}
Write-Host ""
#endregion

#region Timing & Limitations
$elapsed = (Get-Date) - $startTime
$elapsedStr = "{0:mm\:ss}" -f $elapsed

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Report generated in $($elapsed.TotalSeconds.ToString('F0').PadLeft(3)) seconds — manual process takes ~1 hour  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  WHAT AUTOMATION CANNOT DO (the remaining ~5%)                  ║" -ForegroundColor Yellow
Write-Host "╠══════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║  • Cannot explain WHY servers are non-compliant                 ║" -ForegroundColor Yellow
Write-Host "║  • Cannot prioritize findings by business impact                ║" -ForegroundColor Yellow
Write-Host "║  • Cannot write executive narrative for leadership              ║" -ForegroundColor Yellow
Write-Host "║  • Cannot recommend remediation order based on risk             ║" -ForegroundColor Yellow
Write-Host "║  • Cannot correlate compliance gaps to recent changes           ║" -ForegroundColor Yellow
Write-Host "║  → SRE Agent adds executive narrative + prioritization          ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
#endregion
