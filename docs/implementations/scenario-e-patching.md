# Scenario E: Patch Assessment — Implementation Guide

Complete implementation comparison for **Scenario E (Patch Assessment)** across all four AI tier options. Patch assessment is **85% automation / 15% AI** — automation queries missing patches, classifies by severity, and runs pre/post checks. AI adds risk assessment, wave grouping, and post-patch failure analysis.

> **Start here:** If you're unsure which option to pick, see the [decision tree in ai-tier-options.md](../ai-tier-options.md#recommendation-decision-tree).

## Automation vs. AI Split

```
┌────────────────────────────────────────────────────────────────┐
│                        85% AUTOMATION                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ✅ Query Azure Update Manager for missing patches         │  │
│  │ ✅ Query Log Analytics for update compliance              │  │
│  │ ✅ Classify patches by severity (Critical/Security/Other) │  │
│  │ ✅ Run pre-patch readiness checks (disk, reboot, services)│  │
│  │ ✅ Run post-patch validation (reboot, services, events)   │  │
│  │ ✅ Apply static SLA rules (Critical=72h, Security=7d)     │  │
│  │ ✅ Generate patch assessment report with severity tables   │  │
│  │ ✅ Create GLPI tickets for failed post-patch checks       │  │
│  └──────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                        15% AI ADD-ON                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🤖 Risk assessment — cross-reference KBs with server     │  │
│  │    roles, flag risky patches for SQL/domain controllers   │  │
│  │ 🤖 Wave grouping — "patch dev first, then staging,       │  │
│  │    skip month-end batch servers"                          │  │
│  │ 🤖 Business calendar awareness — avoid patching during   │  │
│  │    month-end close, peak hours, change freezes            │  │
│  │ 🤖 Post-patch failure analysis — analyze event logs to   │  │
│  │    determine if issue is patch-related or pre-existing    │  │
│  │ 🤖 CAB justification — write change advisory board       │  │
│  │    narrative for patch deployment approval                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**The automation script (`scripts/demo-patch-assessment.ps1`) already delivers patch discovery, classification, and pre-patch checks.** The AI options below add risk-aware decision-making — the 15% that turns a patch list into a deployment strategy.

## Quick Links

| Option | Section | Effort |
|--------|---------|--------|
| **Option 0 — SRE Agent** (recommended) | [Jump ↓](#option-0-sre-agent-recommended) | ~1 hour |
| **Option A — Agent Framework** | [Jump ↓](#option-a-microsoft-agent-framework) | ~2–3 weeks |
| **Option B — Foundry Agent Service** | [Jump ↓](#option-b-foundry-agent-service) | ~1–2 weeks |
| **Option C — Copilot CLI** | [Jump ↓](#option-c-github-copilot-cli) | ~1 day |

## Capability Comparison

How each option delivers the 85% automation base and the 15% AI add-on:

| Capability | What's Needed | Automation (all options) | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|---|---|
| **Query missing patches** | Resource Graph / Log Analytics | ✅ `demo-patch-assessment.ps1` | Built-in (`RunAzCliReadCommands`) | `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az CLI` directly) |
| **Classify by severity** | Parse patch metadata | ✅ `demo-patch-assessment.ps1` | ✅ + context-aware | ✅ + context-aware | ✅ + context-aware | ✅ + context-aware |
| **Pre-patch readiness** | Disk, reboot, services checks | ✅ `demo-patch-assessment.ps1` | Built-in (Arc Run Command) | `FunctionTool` (Arc SDK) | Function tool (Arc) | Terminal (Arc CLI) |
| **Post-patch validation** | Services, events, patch verify | ✅ `patch-validation/SKILL.md` steps | Built-in | `FunctionTool` | Function tool | Terminal |
| **Static SLA rules** | Critical=72h, Security=7d | ✅ `demo-patch-assessment.ps1` | ✅ + risk override | ✅ + risk override | ✅ + risk override | ✅ + risk override |
| **Risk assessment** | LLM + KB cross-reference (15%) | ❌ Cannot | ✅ "KB5034441 known to break SQL" | ✅ Same reasoning | ✅ Same reasoning | ✅ Same reasoning |
| **Wave grouping** | LLM + server role awareness (15%) | ❌ Cannot | ✅ "dev→staging→prod, skip batch" | ✅ Same reasoning | ✅ Same reasoning | ✅ Same reasoning |
| **Post-patch failure analysis** | LLM log analysis (15%) | ❌ Cannot | ✅ "Event 7031 is patch-related" | ✅ Same reasoning | ✅ Same reasoning | ✅ Same reasoning |
| **CAB justification** | LLM narrative (15%) | ❌ Cannot | ✅ Generates approval text | ✅ Same reasoning | ✅ Same reasoning | ✅ Same reasoning |
| **Scheduled execution** | Timer / cron | ✅ Cron / Task Scheduler | ✅ Built-in scheduled task | ❌ External | ❌ External | ❌ Manual only |

## Shared Environment

All four implementations target the same demo environment:

| Component | Value |
|-----------|-------|
| **Resource group** | `rg-arcbox-itpro` |
| **Region** | `swedencentral` |
| **Windows VMs** | `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL` |
| **Linux VMs** | `ArcBox-Ubuntu-01`, `ArcBox-Ubuntu-02` |
| **Log Analytics workspace** | `f98fca75-7479-45e5-bf0c-87b56a9f9e8c` |
| **GLPI instance** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |

## The 85% — Automation Baseline

Before looking at AI options, here's what the automation script already delivers. **This runs without any AI.**

### Step 1 — Query Azure Update Manager

```powershell
# Resource Graph query for patch assessment results
$patchQuery = @"
patchassessmentresources
| where type == 'microsoft.hybridcompute/machines/patchassessmentresults'
| where id contains 'rg-arcbox-itpro'
| extend machineName = tostring(split(id, '/')[8])
| extend criticalCount = toint(properties.availablePatchCountByClassification.critical)
| extend securityCount = toint(properties.availablePatchCountByClassification.security)
| extend otherCount = toint(properties.availablePatchCountByClassification.other)
| project machineName, criticalCount, securityCount, otherCount
| order by machineName asc
"@

az graph query -q $patchQuery --first 100 -o json
```

### Step 2 — Log Analytics Fallback (Missing Patches)

```kql
// From sre-tools/kusto/query-update-compliance.kql
Update
| where TimeGenerated >= ago(7d)
| where UpdateState == "Needed"
| summarize
    MissingPatches = count(),
    CriticalCount = countif(MSRCSeverity == "Critical"),
    SecurityCount = countif(Classification == "Security Updates")
  by Computer, Classification
| order by CriticalCount desc, MissingPatches desc
```

### Step 3 — Patch Classification Report

```
┌──────────────────────┬──────────┬──────────┬──────────┬──────────┐
│ Machine              │ Critical │ Security │ Other    │ Total    │
├──────────────────────┼──────────┼──────────┼──────────┼──────────┤
│ ArcBox-Win2K22       │ 2        │ 5        │ 3        │ 10       │
│ ArcBox-Win2K25       │ 0        │ 3        │ 7        │ 10       │
│ ArcBox-SQL           │ 1        │ 4        │ 2        │ 7        │
├──────────────────────┼──────────┼──────────┼──────────┼──────────┤
│ TOTAL                │ 3        │ 12       │ 12       │ 27       │
└──────────────────────┴──────────┴──────────┴──────────┴──────────┘
```

### Step 4 — Pre-Patch Readiness Checks

```powershell
# Disk space check (>20% free required)
$diskFree = Invoke-Command -VMName $vmName -Credential $cred -ScriptBlock {
    $sysDrive = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
    [math]::Round($sysDrive.FreeSpace / 1GB, 1)
}

# Pending reboot check
$pendingReboot = Invoke-Command -VMName $vmName -Credential $cred -ScriptBlock {
    Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
}

# Critical services check
$critServices = Invoke-Command -VMName $vmName -Credential $cred -ScriptBlock {
    foreach ($svc in @("wuauserv", "TrustedInstaller", "BITS")) {
        Get-Service -Name $svc -ErrorAction SilentlyContinue | Select Name, Status
    }
}
```

### Step 5 — Static SLA Rules

```
┌──────────────────┬──────────────────┬────────────────────────────────────┐
│ Classification   │ SLA              │ Recommendation                     │
├──────────────────┼──────────────────┼────────────────────────────────────┤
│ Critical         │ 72 hours         │ Deploy in next maintenance window   │
│ Security         │ 7 days           │ Schedule for weekly patch cycle     │
│ Update Rollup    │ 14 days          │ Include in monthly rollup           │
│ Feature Pack     │ 30 days          │ Test in dev first, then production  │
│ Other            │ 30 days          │ Low priority — batch with rollups   │
└──────────────────┴──────────────────┴────────────────────────────────────┘
```

### What Automation Cannot Do (the 15% gap)

From `scripts/demo-patch-assessment.ps1`:

```
╔══════════════════════════════════════════════════════════════════╗
║  WHAT AUTOMATION CANNOT DO (the remaining ~15%)                 ║
╠══════════════════════════════════════════════════════════════════╣
║  • Cannot assess business risk of specific patches              ║
║  • Cannot recommend wave grouping based on dependencies         ║
║  • Cannot predict patch conflicts from historical data          ║
║  • Cannot adjust schedule based on business calendar            ║
║  • Cannot write change advisory board (CAB) justification       ║
╚══════════════════════════════════════════════════════════════════╝
```

**This is what the AI options below add.**

---

## Option 0: SRE Agent (Recommended)

> **Effort:** ~1 hour | **AI adds:** Risk assessment, wave grouping, failure analysis, CAB narrative

Azure SRE Agent is the recommended option. Upload the patch validation skill, and the agent adds risk-aware intelligence on top of the same queries the script uses.

### Setup

| Resource | Location |
|----------|----------|
| Full SRE Agent deployment guide | [`docs/sre-agent-setup.md`](../sre-agent-setup.md) |
| Patch validation skill | [`sre-skills/patch-validation/SKILL.md`](../../sre-skills/patch-validation/SKILL.md) |
| KQL update compliance query | [`sre-tools/kusto/query-update-compliance.kql`](../../sre-tools/kusto/query-update-compliance.kql) |
| GLPI ticket creation tool | [`sre-tools/python/glpi_tools.py`](../../sre-tools/python/glpi_tools.py) |
| Automation script (85% base) | [`scripts/demo-patch-assessment.ps1`](../../scripts/demo-patch-assessment.ps1) |

### Skill Auto-Activation

The `patch-validation` skill activates on these triggers:

```yaml
triggers:
  - Patch deployment completed (success or failure)
  - Pre-patch validation required before maintenance window
  - User requests post-patch verification
```

### Scheduled Task

Configure in **Builder → Scheduled Tasks**:

| Setting | Value |
|---------|-------|
| **Task name** | `weekly-patch-assessment` |
| **Schedule** | Weekly (Tuesday 06:00 UTC — before Patch Tuesday) |
| **Prompt** | `Assess missing patches on all Arc servers in rg-arcbox-itpro. Classify by severity, assess risk for each server role, and recommend a wave deployment strategy. Flag any patches with known issues.` |

### Example Interaction — Pre-Patch Risk Assessment

**Query:**

> **User:** Assess patches for this month and give me a deployment plan.

**Agent execution trace:**

```
Step 1 — Querying Azure Update Manager
  → RunAzCliReadCommands: az graph query -q "patchassessmentresources
    | where type == 'microsoft.hybridcompute/machines/patchassessmentresults'
    | where id contains 'rg-arcbox-itpro' ..."
  → Found 27 missing patches across 3 Windows servers

Step 2 — Querying Log Analytics for patch details
  → RunAzCliReadCommands: az monitor log-analytics query --workspace
    f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query
    "Update | where UpdateState == 'Needed' | summarize by Computer, KBID,
    Classification, MSRCSeverity"
  → 3 Critical (KB5034441, KB5034439, KB5034467), 12 Security, 12 Other

Step 3 — Running pre-patch readiness
  → RunAzCliReadCommands: Arc Run Command on each server (disk, reboot, services)
  → All 3 servers pass pre-patch checks

Step 4 — Risk assessment (AI reasoning)
  → Cross-referencing KBs with server roles from GLPI CMDB
  → Checking KB5034441 known issues (BitLocker recovery on some hardware)
```

**Agent output (the 15% AI adds):**

> **🔧 Patch Assessment — January 2025 Patch Tuesday**
>
> **27 patches across 3 servers** | 3 Critical, 12 Security, 12 Other
>
> ### Risk Assessment
>
> | KB | Classification | Risk | Notes |
> |---|---|---|---|
> | KB5034441 | Critical | ⚠️ **HIGH** | Known to trigger BitLocker recovery on some hardware. **ArcBox-SQL runs SQL Server** — test on dev first. Also caused Guest Configuration agent removal last month. |
> | KB5034439 | Critical | 🟢 Low | .NET Framework update — no known issues for server workloads |
> | KB5034467 | Critical | 🟡 Medium | Cumulative update — large (1.2 GB), ensure sufficient disk on ArcBox-Win2K22 (currently 18 GB free) |
>
> ### Recommended Wave Strategy
>
> | Wave | Servers | When | Rationale |
> |---|---|---|---|
> | **Wave 1 — Dev/Test** | ArcBox-Win2K25 | Thursday Jan 16, 22:00 UTC | No production workloads, safe to test KB5034441 |
> | **Wave 2 — App Servers** | ArcBox-Win2K22 | Saturday Jan 18, 02:00 UTC | After Wave 1 validates clean, weekend maintenance window |
> | **Wave 3 — Database** | ArcBox-SQL | ~~Monday Jan 20~~ → **Tuesday Jan 21, 02:00 UTC** | Skip month-end batch processing (runs Monday nights). SQL Server requires extended post-patch validation. |
>
> ### Business Calendar Conflicts
> - ❌ **Jan 20 (Mon)** — Month-end batch processing on ArcBox-SQL. Do not patch.
> - ❌ **Jan 27–31** — Month-end close period. Change freeze.
> - ✅ **Jan 16–19** — Clear window for Waves 1 & 2.
>
> ### CAB Justification (ready for approval)
>
> *"This deployment addresses 3 Critical CVEs (CVSS 8.1–9.8) affecting Windows Server 2022/2025. Risk is mitigated by a 3-wave deployment starting with non-production servers. KB5034441 has a known BitLocker side-effect — Wave 1 validates before SQL server deployment. Estimated downtime: 15 min per server (reboot). Rollback plan: WSUS decline + system restore point."*
>
> Shall I create GLPI change requests for each wave?

### Example Interaction — Post-Patch Failure Analysis

**Query:**

> **User:** ArcBox-SQL failed post-patch checks. Analyze the logs.

**Agent execution trace:**

```
Step 1 — Running post-patch validation
  → RunAzCliReadCommands: Arc Run Command — check LastBootUpTime ✅
  → RunAzCliReadCommands: Arc Run Command — compare services baseline
    → MSSQLSERVER was Running, now Stopped ❌
  → RunAzCliReadCommands: Arc Run Command — check event log (last 2h)
    → Event 7031: SQL Server service terminated unexpectedly
    → Event 1000: Application crash — sqlservr.exe

Step 2 — Analyzing logs (AI reasoning)
  → Correlating event timestamps with patch installation time
  → Checking KB5034441 known issues for SQL Server compatibility
```

**Agent output:**

> **🔴 Post-Patch Failure Analysis — ArcBox-SQL**
>
> **Verdict: Patch-related** — KB5034441 caused a .NET runtime conflict with SQL Server 2022 CU12.
>
> **Evidence:**
> 1. SQL Server service crashed 3 minutes after reboot (Event 7031)
> 2. Application crash points to `sqlservr.exe` .NET runtime exception
> 3. KB5034441 updates .NET Framework 4.8.1 — known conflict with SQL 2022 CU12 (documented in [KB5035857](https://support.microsoft.com))
> 4. Service was healthy in pre-patch baseline (Running)
>
> **Recommendation:** Rollback KB5034441 on ArcBox-SQL. Apply SQL Server CU13 first (includes the .NET fix), then re-apply KB5034441.
>
> **Created:** [GLPI #158 — ArcBox-SQL post-patch failure: KB5034441 + SQL CU12 conflict](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=158) (P1)

### What Makes SRE Agent Unique

| Feature | SRE Agent | Others |
|---------|-----------|--------|
| **Scheduled assessment** | ✅ Built-in (weekly) | ❌ Requires external scheduler |
| **Auto-trigger on patch failure** | ✅ Azure Monitor alert | ❌ Must build webhook handler |
| **Memory** | ✅ Remembers last patch cycle outcomes | ❌ Must implement state |
| **KB knowledge** | ✅ Can reference known issues | ✅ All LLM options can (training data) |
| **No custom code** | ✅ Portal-only | ❌ Python code required |

---

## Option A: Microsoft Agent Framework

> **Effort:** ~2–3 weeks | **AI adds:** Same risk assessment + full code-level control

### Architecture

```
┌──────────────────────────────────────────────────┐
│  Your host (Container Apps / local dev)           │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         patch_assessment_agent.py            │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ SkillsProvider│   │ FunctionTools       │  │  │
│  │  │ (auto-loads   │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)    │   │ │query_patches   │ │  │  │
│  │  └──────────────┘   │ │pre_patch_check  │ │  │  │
│  │                      │ │post_patch_check │ │  │  │
│  │  ┌──────────────┐   │ │query_cmdb_role  │ │  │  │
│  │  │ AzureOpenAI  │   │ │create_glpi_tickt│ │  │  │
│  │  │ Responses API│   │ └────────────────┘ │  │  │
│  │  └──────────────┘   └────────────────────┘  │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Skills Auto-Discovery

```python
from agent_framework import SkillsProvider, FunctionTool

skills = SkillsProvider(skill_paths=["./sre-skills"])
# Auto-discovers patch-validation/SKILL.md
```

### Function Tools

```python
@FunctionTool
def query_missing_patches(resource_group: str = "rg-arcbox-itpro") -> dict:
    """Query Azure Update Manager for missing patches via Resource Graph."""
    query = """patchassessmentresources
    | where type == 'microsoft.hybridcompute/machines/patchassessmentresults'
    | where id contains '{rg}'
    | extend machineName = tostring(split(id, '/')[8])
    | extend criticalCount = toint(properties.availablePatchCountByClassification.critical)
    | extend securityCount = toint(properties.availablePatchCountByClassification.security)
    | project machineName, criticalCount, securityCount""".format(rg=resource_group)
    result = subprocess.run(
        ["az", "graph", "query", "-q", query, "--first", "100", "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def query_patch_details(server_name: str) -> dict:
    """Query Log Analytics for detailed missing patch KBs on a server."""
    kql = f"""Update
    | where TimeGenerated >= ago(7d)
    | where UpdateState == 'Needed'
    | where Computer == '{server_name}'
    | project Computer, KBID, Title, Classification, MSRCSeverity
    | order by MSRCSeverity asc"""
    result = subprocess.run(
        ["az", "monitor", "log-analytics", "query",
         "-w", "f98fca75-7479-45e5-bf0c-87b56a9f9e8c",
         "--analytics-query", kql, "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def run_pre_patch_check(machine_name: str) -> dict:
    """Run pre-patch readiness checks via Arc Run Command."""
    script = """
    $disk = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
    $freeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
    $rebootPending = Test-Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired"
    $services = @("wuauserv","TrustedInstaller","BITS") | ForEach-Object {
        $s = Get-Service $_ -EA SilentlyContinue
        [PSCustomObject]@{Name=$_; Status=if($s){$s.Status}else{"NotFound"}}
    }
    @{DiskFreeGB=$freeGB; RebootPending=$rebootPending; Services=$services} | ConvertTo-Json
    """
    result = subprocess.run(
        ["az", "connectedmachine", "run-command", "create",
         "--resource-group", "rg-arcbox-itpro",
         "--machine-name", machine_name,
         "--name", "PrePatchCheck",
         "--script", script, "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def run_post_patch_check(machine_name: str) -> dict:
    """Run post-patch validation checks via Arc Run Command."""
    script = """
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    $events = Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddHours(-2)} -EA SilentlyContinue
    $services = Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -ne 'Running'}
    @{LastBoot=$boot; CriticalEvents=$events.Count; StoppedAutoServices=($services | Select Name,Status)} | ConvertTo-Json
    """
    result = subprocess.run(
        ["az", "connectedmachine", "run-command", "create",
         "--resource-group", "rg-arcbox-itpro",
         "--machine-name", machine_name,
         "--name", "PostPatchCheck",
         "--script", script, "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def query_server_role(server_name: str) -> dict:
    """Query GLPI CMDB for server role and business context."""
    # Uses existing glpi_tools.py logic
    from sre_tools.python.glpi_tools import main as glpi_query
    return glpi_query(server_name=server_name)
```

### Example Interaction — Risk Assessment

```
Patch Assessment Agent (Agent Framework) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Assess this month's patches and recommend a deployment plan.

Agent: I'll query missing patches, cross-reference with server roles, and build
a risk-aware deployment strategy.

  → Calling query_missing_patches("rg-arcbox-itpro")
  → Calling query_patch_details("ArcBox-Win2K22")
  → Calling query_patch_details("ArcBox-SQL")
  → Calling query_patch_details("ArcBox-Win2K25")
  → Calling query_server_role("ArcBox-SQL")
  → Calling run_pre_patch_check("ArcBox-Win2K22")
  → Calling run_pre_patch_check("ArcBox-SQL")
  → Calling run_pre_patch_check("ArcBox-Win2K25")

🔧 Patch Assessment — January 2025

27 missing patches across 3 servers. Here's my risk-aware recommendation:

⚠️ HIGH RISK: KB5034441 on ArcBox-SQL
GLPI CMDB shows ArcBox-SQL runs SQL Server 2022 CU12. KB5034441 updates
.NET Framework 4.8.1, which has a documented conflict with SQL 2022 CU12.
Recommend: apply SQL CU13 first, then KB5034441.

Wave deployment:
  Wave 1 (Thu 22:00): ArcBox-Win2K25 (dev/test — safe to validate)
  Wave 2 (Sat 02:00): ArcBox-Win2K22 (app server — weekend window)
  Wave 3 (Tue 02:00): ArcBox-SQL (database — after month-end batch, post-CU13)

Create GLPI change requests for each wave? [y/n]
```

### Example Interaction — Post-Patch Failure

```
You: ArcBox-SQL is having issues after patching. Analyze.

Agent: Running post-patch validation checks.

  → Calling run_post_patch_check("ArcBox-SQL")
  → Critical events found: 2
  → Stopped auto-services: MSSQLSERVER

  → Calling query_patch_details("ArcBox-SQL") — to see what was applied

Analysis: The SQL Server service (MSSQLSERVER) crashed 3 minutes after reboot.
Event 7031 + Event 1000 both point to sqlservr.exe .NET runtime exception.
This matches the known KB5034441 + SQL CU12 conflict I flagged earlier.

Verdict: PATCH-RELATED failure.
Recommendation: Rollback KB5034441, apply CU13, then re-attempt.
  → Calling create_glpi_ticket("ArcBox-SQL post-patch failure: KB5034441 conflict", ..., priority="1")
Created: GLPI #158 (P1)
```

### Scheduling (External)

```bash
# Weekly patch assessment via cron (before Patch Tuesday)
0 6 * * 2 cd /path/to/patch-agent && python patch_assessment_agent.py \
  --prompt "Assess missing patches on all Arc servers and recommend wave strategy" \
  >> /var/log/patch-assessment.log 2>&1
```

### Comparison with SRE Agent

| Aspect | SRE Agent | Agent Framework |
|--------|-----------|-----------------|
| **Setup effort** | ~1 hour (portal) | ~2–3 weeks (code + hosting) |
| **Skills** | Upload via UI | `SkillsProvider` (identical behavior) |
| **Patch tools** | Built-in `RunAzCliReadCommands` | Custom `FunctionTool` wrappers |
| **CMDB integration** | Built-in GLPI tool | Custom `FunctionTool` + GLPI code |
| **Wave strategy output** | Agent chat response | Full control (JSON, email, ServiceNow) |
| **Scheduling** | ✅ Built-in | ❌ External (Logic Apps / cron) |
| **Memory** | ✅ Remembers past cycle outcomes | Must implement (Cosmos DB / file) |

---

## Option B: Foundry Agent Service

> **Effort:** ~1–2 weeks | **AI adds:** Same risk assessment + managed hosting + Code Interpreter

### Architecture

```
┌──────────────────────────────────────────────────┐
│            Azure AI Foundry Project               │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         patch-assessment-agent               │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Instructions  │   │ Function Tools      │  │  │
│  │  │ (from        │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)   │   │ │query_patches   │ │  │  │
│  │  └──────────────┘   │ │pre_patch_check  │ │  │  │
│  │                      │ │post_patch_check │ │  │  │
│  │  ┌──────────────┐   │ │query_cmdb_role  │ │  │  │
│  │  │ Code         │   │ │create_ticket   │ │  │  │
│  │  │ Interpreter  │   │ └────────────────┘ │  │  │
│  │  └──────────────┘   └────────────────────┘  │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### SKILL.md → Agent Instructions

```python
from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

skill_content = Path("sre-skills/patch-validation/SKILL.md").read_text()

client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

agent = client.agents.create(
    name="patch-assessment-agent",
    instructions=f"""You are a patch assessment specialist for Azure Arc-enrolled Windows servers.
Your job is to go beyond simple patch listing and provide risk-aware deployment strategies.

Automation handles 85% of the work (patch discovery, classification, pre/post checks). You add the 15%:
- Risk assessment: cross-reference KBs with server roles to flag dangerous patches
- Wave grouping: recommend deployment order based on server role and dependencies
- Business calendar: avoid patching during month-end, peak hours, change freezes
- Post-patch failure analysis: determine if issues are patch-related or pre-existing
- CAB justification: write change advisory board narrative for approval

{skill_content}""",
    tools=patch_tools + [{"type": "code_interpreter"}],
    model="gpt-4o",
)
```

### Function Tool Definitions

```python
patch_tools = [
    {
        "type": "function",
        "function": {
            "name": "query_missing_patches",
            "description": "Query Azure Update Manager for missing patches on Arc-enrolled servers",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_group": {"type": "string", "default": "rg-arcbox-itpro"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_patch_details",
            "description": "Query Log Analytics for specific KB IDs, titles, and severity for a server",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {"type": "string"}
                },
                "required": ["server_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_pre_patch_check",
            "description": "Run pre-patch readiness checks (disk, reboot, services) on an Arc server",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_name": {"type": "string"}
                },
                "required": ["machine_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_post_patch_check",
            "description": "Run post-patch validation (services, events, reboot) on an Arc server",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_name": {"type": "string"}
                },
                "required": ["machine_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_server_role",
            "description": "Query GLPI CMDB for server role and business classification",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {"type": "string"}
                },
                "required": ["server_name"]
            }
        }
    }
]
```

### Example Interaction

```
You: Assess patches and create a wave deployment plan.

Agent: I'll analyze missing patches, check server roles, and build a risk-aware
wave strategy.

  → query_missing_patches("rg-arcbox-itpro")
  → query_patch_details("ArcBox-SQL")
  → query_server_role("ArcBox-SQL")
  → run_pre_patch_check("ArcBox-SQL")
  → code_interpreter: analyzing KB known issues against server roles

🔧 Patch Wave Plan — January 2025

27 patches across 3 servers.

Risk flag: KB5034441 (.NET 4.8.1 update) has a documented conflict with
SQL Server 2022 CU12 running on ArcBox-SQL.

Recommended waves:
  Wave 1: ArcBox-Win2K25 (dev) — Thursday 22:00
  Wave 2: ArcBox-Win2K22 (app) — Saturday 02:00
  Wave 3: ArcBox-SQL (database) — Tuesday 02:00 (after CU13 applied)

[Code Interpreter generated risk matrix visualization]

CAB justification text generated — ready for approval workflow.
```

### Code Interpreter Advantage

The Foundry agent's Code Interpreter enables:
- Statistical analysis of historical patch failure rates
- Risk scoring calculations (KB severity × server criticality × known issues)
- Visual patch deployment timeline charts
- Comparison with previous patch cycle outcomes

### Scheduling

```python
# Azure Functions timer trigger — weekly before Patch Tuesday
@app.timer_trigger(schedule="0 0 6 * * 2", arg_name="timer")
def patch_assessment_trigger(timer: func.TimerRequest) -> None:
    from patch_assessment_agent import run_single_prompt
    run_single_prompt("Assess patches for all Arc servers and recommend wave deployment strategy.")
```

### Comparison with SRE Agent

| Aspect | SRE Agent | Foundry Agent |
|--------|-----------|---------------|
| **Setup effort** | ~1 hour (portal) | ~1–2 weeks (SDK + hosting) |
| **Skills** | Upload via UI | Inject as `instructions` |
| **Code Interpreter** | ✅ Built-in | ✅ Built-in (risk visualizations) |
| **Multi-skill routing** | ✅ Auto-routes | ❌ One skill per agent |
| **Scheduling** | ✅ Built-in | ❌ External trigger |
| **Hosting** | Managed (SaaS) | Managed (Foundry platform) |

---

## Option C: GitHub Copilot CLI

> **Effort:** ~1 day | **AI adds:** Interactive risk assessment and wave planning on demand

### Setup

```bash
# Copy patch skill to Copilot skills directory
cp -r sre-skills/patch-validation .github/skills/

# Or for personal skills (all projects)
cp -r sre-skills/patch-validation ~/.copilot/skills/

# Verify
/skills list
# → patch-validation loaded
```

**That's it.** Copilot CLI runs `az CLI` directly — no tool wrappers needed.

### Example Interaction — Pre-Patch Assessment

```
> Assess missing patches on my Arc servers and recommend a deployment plan

Copilot: I'll query Azure Update Manager and Log Analytics for missing patches,
then provide a risk-aware deployment recommendation.

[Running] az graph query -q "patchassessmentresources | where type ==
  'microsoft.hybridcompute/machines/patchassessmentresults' | where id
  contains 'rg-arcbox-itpro' | extend machineName = tostring(split(id,'/')[8])
  | extend criticalCount = toint(properties.availablePatchCountByClassification.critical)
  | extend securityCount = toint(properties.availablePatchCountByClassification.security)
  | project machineName, criticalCount, securityCount"

[Running] az monitor log-analytics query -w f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Update | where UpdateState == 'Needed' | project Computer,
  KBID, Title, Classification, MSRCSeverity | order by MSRCSeverity"

🔧 Patch Assessment — January 2025

27 missing patches across 3 servers:
  ArcBox-Win2K22: 2 Critical, 5 Security, 3 Other
  ArcBox-Win2K25: 0 Critical, 3 Security, 7 Other
  ArcBox-SQL:     1 Critical, 4 Security, 2 Other

Risk assessment:
- ⚠️ KB5034441 on ArcBox-SQL — this .NET 4.8.1 update has known issues with
  SQL Server 2022 CU12. Recommend applying CU13 before this KB.
- 🟢 KB5034439 — .NET Framework update, low risk for server workloads
- 🟡 KB5034467 — Large cumulative update (1.2 GB), verify disk space first

Recommended wave strategy:
  Wave 1 (Thu): ArcBox-Win2K25 — dev/test, validate KB5034441
  Wave 2 (Sat): ArcBox-Win2K22 — app server, weekend window
  Wave 3 (Tue): ArcBox-SQL — database, post-CU13, skip Monday batch

Shall I run pre-patch readiness checks on all 3 servers?
```

### Example Interaction — Pre-Patch Checks

```
> Yes, run pre-patch checks on all servers

Copilot: Running readiness checks via Azure Arc.

[Running] az connectedmachine run-command create --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 --name PrePatch --script "
    $disk = Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\"
    [math]::Round($disk.FreeSpace/1GB,1)"

[Running] az connectedmachine run-command create --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-SQL --name PrePatch --script "..."

[Running] az connectedmachine run-command create --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K25 --name PrePatch --script "..."

Pre-Patch Readiness:
  ✅ ArcBox-Win2K22: 18 GB free, no pending reboot, all services OK
  ✅ ArcBox-Win2K25: 42 GB free, no pending reboot, all services OK
  ⚠️ ArcBox-SQL: 12 GB free (marginal for 1.2 GB cumulative update),
     no pending reboot, services OK

Recommendation: Clean up temp files on ArcBox-SQL before patching
(C:\Windows\Temp and SQL tempdb).
```

### Example Interaction — Post-Patch Failure

```
> ArcBox-SQL SQL Server won't start after patching. What happened?

Copilot: I'll check the post-patch state and analyze event logs.

[Running] az connectedmachine run-command create --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-SQL --name PostPatch --script "
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    $events = Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddHours(-2)}
    $sqlSvc = Get-Service MSSQLSERVER
    @{LastBoot=$boot; Events=($events|Select TimeCreated,Id,Message); SQLStatus=$sqlSvc.Status} | ConvertTo-Json"

Post-Patch Analysis:
  🔴 MSSQLSERVER: Stopped (was Running before patch)
  Events found:
    - 14:03 Event 7031: SQL Server terminated unexpectedly
    - 14:03 Event 1000: sqlservr.exe crash — .NET runtime exception

Verdict: This is PATCH-RELATED. KB5034441 updated .NET Framework 4.8.1, which
has a documented conflict with SQL Server 2022 CU12. The .NET runtime exception
in sqlservr.exe confirms this is the known issue.

Recommended fix:
1. Rollback KB5034441: wusa /uninstall /kb:5034441 /norestart
2. Install SQL Server CU13 (includes the .NET compatibility fix)
3. Re-apply KB5034441 after CU13

Shall I create a P1 GLPI ticket for this?
```

### Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **Interactive only** | No scheduled patch assessments | Run automation script via cron; use Copilot for ad-hoc risk analysis |
| **No persistent memory** | Can't remember last patch cycle outcomes | Pass context manually or use custom instructions |
| **No auto-trigger** | Can't auto-analyze when patches fail | Use Azure Monitor alerts + SRE Agent for auto-response |
| **Session-based** | Knowledge lost between sessions | Use `~/.copilot/instructions.md` for standing patch policies |

---

## Skills Reusability

All options reuse the **same** `sre-skills/patch-validation/SKILL.md`:

| Platform | How Skills Load |
|---|---|
| **SRE Agent** | Upload `SKILL.md` via Builder → Skills UI |
| **Agent Framework** | `SkillsProvider(skill_paths=["./sre-skills"])` — auto-discovers |
| **Foundry Agent** | `SKILL.md` content injected as agent `instructions` parameter |
| **Copilot CLI** | Copy to `.github/skills/` or `~/.copilot/skills/` — auto-discovers |

## Key Takeaway

**The 85% is already built.** The automation script (`scripts/demo-patch-assessment.ps1`) queries missing patches, classifies by severity, runs pre-patch checks, and applies static SLA rules. The AI options above add the 15% — risk assessment that knows KB5034441 breaks SQL, wave grouping that respects your business calendar, and failure analysis that tells you *whether the crash is patch-related or pre-existing*.

Choose the AI option that fits your operational model:

| If you need... | Choose |
|---|---|
| Turnkey scheduled assessment with memory | **SRE Agent** (Option 0) |
| Full code control + custom approval workflows | **Agent Framework** (Option A) |
| Managed hosting + Code Interpreter visualizations | **Foundry Agent** (Option B) |
| Ad-hoc risk assessment from terminal | **Copilot CLI** (Option C) |

## See Also

- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [Scenario A: Health Check](scenario-a-health-check/) — 70% automation / 30% AI example
- [Scenario D: Compliance Reporting](scenario-d-compliance.md) — 95% automation / 5% AI example
- [Patch validation skill](../../sre-skills/patch-validation/SKILL.md) — the SKILL.md source
- [Update compliance KQL query](../../sre-tools/kusto/query-update-compliance.kql) — Log Analytics query
- [Patch assessment script](../../scripts/demo-patch-assessment.ps1) — the 85% automation baseline
