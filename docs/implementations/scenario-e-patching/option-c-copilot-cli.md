# Option C: GitHub Copilot CLI — Patching Implementation

The simplest option — copy skills, authenticate `az CLI`, and start asking questions.

> **When to use:** Engineers who work in the terminal and want AI-assisted patch risk assessment without building or hosting anything. Great as a complement to automated patch assessment or as a standalone tool for ad-hoc risk analysis and failure diagnosis.

> **AI contribution: ~15%.** The automation script handles 85% of the work (querying missing patches, classifying by severity, running pre-patch checks). Copilot CLI adds risk assessment that knows specific KB interactions, wave planning that respects your business context, and failure analysis that distinguishes patch-caused issues from coincidental ones.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Your terminal (PowerShell / bash / zsh)          │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         GitHub Copilot CLI                   │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Skills        │   │ Terminal tools      │  │  │
│  │  │ (.github/     │   │ ┌────────────────┐ │  │  │
│  │  │  skills/)     │   │ │ az CLI         │ │  │  │
│  │  │ Auto-loads    │   │ │ PowerShell     │ │  │  │
│  │  │ SKILL.md      │   │ │ curl           │ │  │  │
│  │  └──────────────┘   │ └────────────────┘ │  │  │
│  │                      └────────────────────┘  │  │
│  │  ┌──────────────┐                            │  │
│  │  │ Azure Skills  │  (optional add-on)        │  │
│  │  │ Plugin        │                            │  │
│  │  │ ┌──────────┐ │                            │  │
│  │  │ │observ.   │ │                            │  │
│  │  │ │diagnostics│ │                            │  │
│  │  │ │+200 MCP  │ │                            │  │
│  │  │ └──────────┘ │                            │  │
│  │  └──────────────┘                            │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Update Mgr   │  │Log Analytics│  │   GLPI   │ │
│  │ (az graph)   │  │  (az CLI)   │  │(curl/Py) │ │
│  └──────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **GitHub Copilot CLI** | Installed and authenticated (`gh copilot` or standalone) |
| **GitHub Copilot license** | Individual ($19/mo), Business ($19/user/mo), or Enterprise ($39/user/mo) |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |

## Step 1: Copy Skills

```bash
# From repository root — project-level (this repo only)
mkdir -p .github/skills
cp -r sre-skills/patch-validation .github/skills/

# Or user-level (all projects)
# Linux/macOS
cp -r sre-skills/patch-validation ~/.copilot/skills/
# Windows (PowerShell)
Copy-Item -Recurse sre-skills\patch-validation $env:USERPROFILE\.copilot\skills\
```

## Step 2 (Optional): Install the Azure Skills Plugin

```
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

> **💡 No patching tools in the plugin.** The Azure Skills Plugin does not include a dedicated patching skill. Azure Update Manager operations and Arc Run Commands for pre/post-patch checks require `az CLI` in the terminal. However, the plugin's `azure-observability` skill can help query Log Analytics for post-patch event logs, and `azure-diagnostics` can surface resource health signals — useful context during failure analysis.

## Step 3: Verify Skills Are Loaded

```
/skills list
```

**Expected output:**

```
Available skills:
  patch-validation                     Pre/post patch validation checks...
  wintel-health-check-investigation    Investigates Windows server health check failures...
  security-agent-troubleshooting       Troubleshoots Defender agent health issues...
  compliance-investigation             Defender + Azure Policy compliance...
  vmware-bau-operations                Snapshot cleanup, VM health checks...
```

## Demo Walkthrough

### Example 1 — Run patch assessment (85% automation)

This is the **deterministic** baseline — no AI needed.

```
You: Run patch assessment

Copilot: I'll run the patch assessment automation script.

[Running] ./scripts/demo-patch-assessment.ps1

🔧 Patch Assessment — January 2025

Sources queried:
  ✅ Azure Update Manager — missing patches
  ✅ Log Analytics — update classification
  ✅ Arc server inventory — server roles

Missing patches by server:
  ArcBox-Win2K22: 2 Critical, 5 Security, 3 Other  (10 total)
  ArcBox-Win2K25: 0 Critical, 3 Security, 7 Other  (10 total)
  ArcBox-SQL:     1 Critical, 4 Security, 2 Other   (7 total)

Total: 27 missing patches across 3 servers
SLA status: 2 Critical patches exceed 14-day SLA window

Report saved to: ./reports/patch-assessment-2025-01-15.json
```

The script handles data collection, severity classification, and SLA tracking. No AI involved.

### Example 2 — Risk assessment for a specific KB (AI reasoning)

```
You: Assess the risk of applying KB5034441 on ArcBox-SQL — it's a production
database server

Copilot: I'll assess the risk of KB5034441 on ArcBox-SQL by checking the patch
details and the server's configuration.

[Running] az graph query -q "patchassessmentresources | where type ==
  'microsoft.hybridcompute/machines/patchassessmentresults/softwarepatches'
  | where id contains 'ArcBox-SQL' | where properties.patchName == 'KB5034441'
  | project properties.patchName, properties.classifications,
  properties.kbId, properties.rebootRequired"

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-SQL \
  --name SQLVersionCheck \
  --location swedencentral \
  --script "
    (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full').Version
    [System.Data.SqlClient.SqlConnection]::new('Server=.;Integrated Security=true').ServerVersion"

⚠️ Risk Assessment: KB5034441 on ArcBox-SQL — HIGH RISK

KB5034441 is a .NET Framework 4.8.1 security update. Here's the concern:

**Server context:**
  - Role: Production SQL Server 2022
  - Current SQL CU: CU12
  - .NET Framework: 4.8.1 (build 528040)

**Known issue:** KB5034441 has a documented compatibility conflict with SQL
Server 2022 CU12. The updated .NET runtime can cause sqlservr.exe to crash
with a CLR exception on startup. Microsoft recommends installing SQL Server
CU13 first, which includes the compatibility fix.

**Risk rating: 🔴 HIGH**
  - Probability of failure: High (confirmed incompatibility)
  - Impact if failure: Critical (SQL Server won't start)
  - Rollback complexity: Medium (wusa /uninstall + reboot)

**Recommendation:**
  1. Install SQL Server 2022 CU13 first (includes .NET compatibility fix)
  2. Then apply KB5034441
  3. Schedule during maintenance window with pre-validated rollback plan
  4. Take a VM snapshot before patching as a safety net

Shall I check if CU13 is available in your Update Manager assessment?
```

### Example 3 — Wave planning (AI reasoning with business context)

```
You: Recommend a patch wave grouping for my 5 Arc servers based on their roles

Copilot: I'll query the Arc server inventory and role assignments to build a
risk-aware wave plan.

[Running] az graph query -q "Resources | where type ==
  'microsoft.hybridcompute/machines' and resourceGroup == 'rg-arcbox-itpro'
  | project name, properties.osName, tags"

[Running] az graph query -q "patchassessmentresources | where type ==
  'microsoft.hybridcompute/machines/patchassessmentresults'
  | where id contains 'rg-arcbox-itpro'
  | extend machineName = tostring(split(id,'/')[8])
  | extend critical = toint(properties.availablePatchCountByClassification.critical)
  | project machineName, critical"

Servers discovered:
  ArcBox-Win2K22  — App server (IIS)
  ArcBox-Win2K25  — Dev/test workstation
  ArcBox-SQL      — Production SQL Server
  ArcBox-Ubuntu-01 — Linux monitoring
  ArcBox-Ubuntu-02 — Linux monitoring

📋 Recommended Wave Strategy:

**Wave 1 — Thursday (dev/test validation)**
  └── ArcBox-Win2K25 (dev/test — lowest risk, validates KB behavior)
  └── ArcBox-Ubuntu-01 (Linux — independent patch stream)

**Wave 2 — Saturday (app tier, weekend window)**
  └── ArcBox-Win2K22 (IIS app server — validate after Wave 1 success)
  └── ArcBox-Ubuntu-02 (Linux — stagger across waves for availability)

**Wave 3 — Next Tuesday (database tier, post-validation)**
  └── ArcBox-SQL (production DB — apply ONLY after CU13, skip Monday batch jobs)

**Rationale:**
  - Dev/test goes first to catch issues early
  - App server gets a weekend window for rollback time
  - Database server goes last with maximum validation buffer
  - Linux servers are split across waves to maintain monitoring availability
  - Tuesday avoids Monday batch processing on ArcBox-SQL

Shall I create GLPI tickets for each wave with the scheduled dates?
```

### Example 4 — Pre-patch validation with skill (deterministic + AI)

```
You: Run pre-patch validation on ArcBox-Win2K22 using the /patch-validation skill

Copilot: I'll run pre-patch readiness checks on ArcBox-Win2K22 following the
patch-validation skill procedure.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name PrePatchValidation \
  --location swedencentral \
  --script "
    $disk = Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\"
    $freeGB = [math]::Round($disk.FreeSpace/1GB,1)
    $pendingReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    $wuService = (Get-Service wuauserv).Status
    $bits = (Get-Service BITS).Status
    $lastBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    @{FreeSpaceGB=$freeGB; PendingReboot=$pendingReboot;
      WUService=$wuService; BITS=$bits; LastBoot=$lastBoot} | ConvertTo-Json"

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name ServiceSnapshot \
  --location swedencentral \
  --script "Get-Service | Where Status -eq Running |
    Select Name,DisplayName | ConvertTo-Json"

Pre-Patch Validation — ArcBox-Win2K22:

  ✅ Disk space: 18.3 GB free (threshold: 5 GB)
  ✅ Pending reboot: None
  ✅ Windows Update service: Running
  ✅ BITS service: Running
  ✅ Last boot: 3 days ago (no stale reboot)
  ✅ Running services snapshot captured (47 services)

Overall: ✅ READY FOR PATCHING

Service baseline saved — will be used for post-patch comparison to detect
any services that failed to restart after patching.
```

### Example 5 — Post-patch failure diagnosis (AI reasoning)

```
You: The post-patch health check failed on ArcBox-Win2K25 — analyze if it's
patch-related or coincidental

Copilot: I'll investigate the failure by comparing pre-patch and post-patch
state and analyzing event logs.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K25 \
  --name PostPatchDiag \
  --location swedencentral \
  --script "
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    $events = Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;
      StartTime=(Get-Date).AddHours(-4)} | Select TimeCreated,Id,Message
    $stoppedSvcs = Get-Service | Where {$_.StartType -eq 'Automatic' -and
      $_.Status -ne 'Running'} | Select Name,Status
    $hotfixes = Get-HotFix | Sort InstalledOn -Descending | Select -First 5
    @{LastBoot=$boot; CriticalEvents=$events; StoppedServices=$stoppedSvcs;
      RecentPatches=$hotfixes} | ConvertTo-Json -Depth 3"

[Running] az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Event | where Computer == 'ArcBox-Win2K25'
    | where TimeGenerated > ago(4h) | where EventLevelName in ('Error','Warning')
    | project TimeGenerated, Source, EventID, RenderedDescription
    | order by TimeGenerated desc | take 20"

Post-Patch Failure Analysis — ArcBox-Win2K25:

**Symptoms found:**
  🔴 Print Spooler service: Stopped (was Running pre-patch)
  🟡 2 Warning events: Disk performance counters disabled

**Timeline correlation:**
  - KB5034439 installed at 02:14 AM (reboot at 02:17)
  - System fully up at 02:19 AM
  - Print Spooler crash at 02:20 AM (Event 7031)
  - Health check ran at 06:00 AM — flagged service down

**Verdict: 🟡 LIKELY COINCIDENTAL, NOT PATCH-RELATED**

KB5034439 is a .NET Framework update — it does not touch the Print Spooler
service or its dependencies. The Spooler crash (Event 7031) shows an
access violation in a third-party print driver (PaperCut MF), which is
a known issue with PaperCut v23.x on Server 2025 after any reboot.

The patch caused a reboot, which triggered the pre-existing PaperCut bug.
The patch itself is not the root cause.

**Recommendation:**
  1. Restart the Print Spooler: `Start-Service Spooler` (immediate fix)
  2. Update PaperCut MF to v24.x (permanent fix for reboot crashes)
  3. No patch rollback needed — KB5034439 is clean

Shall I restart the Print Spooler via Arc Run Command and create a P3 GLPI
ticket for the PaperCut upgrade?
```

## Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **Interactive only** | No scheduled patch assessments | Run `demo-patch-assessment.ps1` via cron; use Copilot for ad-hoc risk analysis |
| **No persistent memory** | Can't remember last patch cycle outcomes | Pass context manually or use `~/.copilot/instructions.md` for standing patch policies |
| **No auto-trigger** | Can't auto-analyze when patches fail | Use Azure Monitor alerts + SRE Agent for auto-response |
| **Session-based** | Knowledge lost between sessions | Use custom instructions for standing patch window schedules |

## Recommended Usage Pattern

```
                     Scheduled (pre-Patch Tue)        Ad-hoc (as needed)
                    ┌──────────────────┐           ┌──────────────────┐
                    │ PowerShell script │           │  Copilot CLI     │
                    │ (85% of work)     │           │  (15% AI value)  │
                    │                   │           │                  │
                    │ ✅ Query patches   │ ─ data ─▶ │ 🔍 Risk assess   │
                    │ ✅ Classify sev.   │ for AI    │ 🔍 Wave planning │
                    │ ✅ Pre-patch check │           │ 🔍 KB analysis   │
                    │ ✅ SLA tracking    │           │ 🔍 Failure diag  │
                    └──────────────────┘           └──────────────────┘
```

## Comparison with SRE Agent

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify) |
| **Skills** | Upload via UI | Copy to `.github/skills/` |
| **Tools** | Built-in + custom | Terminal (az CLI, PowerShell, curl) |
| **Scheduling** | ✅ Built-in | ❌ Manual only |
| **Memory** | ✅ Built-in | ⚠️ Session-only |
| **Risk assessment** | ✅ Auto-generated | ✅ On-demand (interactive, more detailed) |
| **Wave planning** | ✅ Automated | ✅ Interactive (can incorporate ad-hoc context) |
| **Failure diagnosis** | ✅ Auto-triggered | ❌ Manual (but deeper terminal access) |
| **Cost** | Azure Agent Units | Copilot license ($19-39/user/mo) |

## See Also

- [Scenario E overview](../scenario-e-patching.md) — comparison of all 4 options
- [`sre-skills/patch-validation/SKILL.md`](../../../sre-skills/patch-validation/SKILL.md) — skill definition
- [Azure Skills Plugin](https://github.com/microsoft/azure-skills) — optional add-on (no patching tools, but `azure-observability` helps with post-patch log queries)
- [GitHub Copilot CLI documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
