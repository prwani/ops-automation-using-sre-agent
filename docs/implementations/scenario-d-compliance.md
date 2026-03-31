# Scenario D: Compliance Reporting — Implementation Guide

Complete implementation comparison for **Scenario D (Compliance Reporting)** across all four AI tier options. Compliance reporting is **95% automation / 5% AI** — the AI add-on is optional and provides executive narrative and root-cause hypothesis on top of fully automated data collection and formatting.

> **Start here:** If you're unsure which option to pick, see the [decision tree in ai-tier-options.md](../ai-tier-options.md#recommendation-decision-tree).

## Automation vs. AI Split

```
┌────────────────────────────────────────────────────────────────┐
│                        95% AUTOMATION                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ✅ Query Defender for Cloud regulatory compliance         │  │
│  │ ✅ Query Azure Policy non-compliant resources             │  │
│  │ ✅ Query Secure Score controls                            │  │
│  │ ✅ Correlate findings (Defender ∩ Policy overlap)          │  │
│  │ ✅ Generate formatted report tables                       │  │
│  │ ✅ Classify by severity (rule-based: P1–P4)               │  │
│  │ ✅ Create GLPI tickets for non-compliant resources        │  │
│  │ ✅ Compare with previous report (delta detection)         │  │
│  └──────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                        5% AI ADD-ON                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🤖 Executive narrative with trend analysis               │  │
│  │ 🤖 Root-cause hypothesis for compliance drift            │  │
│  │ 🤖 Prioritize findings by business impact                │  │
│  │ 🤖 Recommend remediation order based on risk             │  │
│  │ 🤖 Correlate compliance gaps to recent changes           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**The automation script (`scripts/demo-compliance-report.ps1`) already delivers a production-ready compliance report.** The AI options below add the final 5% — the narrative and reasoning that helps leadership understand *why* compliance changed and *what to fix first*.

## Quick Links

| Option | Section | Effort |
|--------|---------|--------|
| **Option 0 — SRE Agent** (recommended) | [Jump ↓](#option-0-sre-agent-recommended) | ~1 hour |
| **Option A — Agent Framework** | [Jump ↓](#option-a-microsoft-agent-framework) | ~2–3 weeks |
| **Option B — Foundry Agent Service** | [Jump ↓](#option-b-foundry-agent-service) | ~1–2 weeks |
| **Option C — Copilot CLI** | [Jump ↓](#option-c-github-copilot-cli) | ~1 day |

## Capability Comparison

How each option delivers the 95% automation base and the 5% AI add-on:

| Capability | What's Needed | Automation (all options) | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|---|---|
| **Query Defender compliance** | `az security` CLI | ✅ `demo-compliance-report.ps1` | Built-in (`RunAzCliReadCommands`) | `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az CLI` directly) |
| **Query Azure Policy state** | `az policy state` CLI | ✅ `demo-compliance-report.ps1` | Built-in (`RunAzCliReadCommands`) | `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az CLI` directly) |
| **Query Secure Score** | `az security secure-score-controls` | ✅ `demo-compliance-report.ps1` | Built-in (`RunAzCliReadCommands`) | `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az CLI` directly) |
| **Generate formatted report** | Tables, severity flags | ✅ `demo-compliance-report.ps1` | ✅ + narrative | ✅ + narrative | ✅ + narrative | ✅ + narrative |
| **Executive narrative** | LLM reasoning (5%) | ❌ Cannot | ✅ Skill auto-loads | ✅ `SkillsProvider` context | ✅ Agent instructions | ✅ Skill auto-loads |
| **Root-cause hypothesis** | LLM correlation (5%) | ❌ Cannot | ✅ "15 servers lost agent after last patch" | ✅ Same reasoning | ✅ Same reasoning | ✅ Same reasoning |
| **Trend comparison** | Compare with prior run | ✅ Delta detection (numeric) | ✅ + NL trend narrative | ✅ + NL trend narrative | ✅ + NL trend narrative | ✅ + NL trend narrative |
| **Scheduled execution** | Timer / cron trigger | ✅ Cron / Task Scheduler | ✅ Built-in scheduled task | ❌ External (Logic Apps / cron) | ❌ External trigger | ❌ Manual only |
| **Create GLPI tickets** | HTTP API call | ✅ Script can automate | Built-in tool (`glpi-create-ticket`) | `FunctionTool` (same GLPI code) | Function tool (same GLPI code) | Terminal (`curl` / Python) |

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

## The 95% — Automation Baseline

Before looking at AI options, here's what the automation script already delivers. **This runs without any AI.**

### Step 1 — Defender for Cloud Regulatory Compliance

```powershell
# Query all regulatory compliance standards
az security regulatory-compliance-standards list `
  --query "[].{Standard:name, State:state, PassedControls:passedControls, FailedControls:failedControls}" -o table
```

**Output:**

```
┌────────────────────────────────────────────┬──────────┬──────────┬──────────┐
│ Standard                                   │ State    │ Passed   │ Failed   │
├────────────────────────────────────────────┼──────────┼──────────┼──────────┤
│ CIS Microsoft Azure Foundations 2.0.0      │ Passed   │ 142      │ 8        │
│ NIST SP 800-53 Rev. 5                      │ Passed   │ 312      │ 15       │
│ ISO 27001:2013                             │ Passed   │ 89       │ 4        │
│ PCI DSS v4                                 │ Failed   │ 198      │ 22       │
└────────────────────────────────────────────┴──────────┴──────────┴──────────┘
```

### Step 2 — Azure Policy Compliance Summary

```powershell
# Summarize policy compliance for the resource group
az policy state summarize --resource-group rg-arcbox-itpro `
  --query "value[].{Policy:policyDefinitionName, NonCompliant:results.nonCompliantResources, Total:results.totalResources}" -o table
```

### Step 3 — Non-Compliant Resources Detail

```powershell
# List specific non-compliant resources
az policy state list --resource-group rg-arcbox-itpro `
  --filter "complianceState eq 'NonCompliant'" `
  --query "[].{Resource:resourceId, Policy:policyDefinitionName, State:complianceState}" -o table
```

### Step 4 — Defender Secure Score

```powershell
az security secure-score-controls list `
  --query "[].{Control:displayName, Current:currentScore, Max:maxScore}" -o table
```

### Step 5 — Resource Graph Query for Failing Controls

```kql
// From sre-tools/kusto/query-compliance-state.kql
SecurityResources
| where type == "microsoft.security/regulatorycompliancestandards/regulatorycompliancecontrols/regulatorycomplianceassessments"
| where subscriptionId == "{subscription_id}"
| extend standard = tostring(properties.regulatoryComplianceStandardName)
| where standard contains "CIS"
| extend state = tostring(properties.state)
| where state == "Failed"
| summarize TotalFailedControls = count(), TotalFailedResources = sum(failedResources)
  by controlId, controlName, state, failedResources
| order by failedResources desc
| take 20
```

### What Automation Cannot Do (the 5% gap)

From `scripts/demo-compliance-report.ps1`:

```
╔══════════════════════════════════════════════════════════════════╗
║  WHAT AUTOMATION CANNOT DO (the remaining ~5%)                  ║
╠══════════════════════════════════════════════════════════════════╣
║  • Cannot explain WHY servers are non-compliant                 ║
║  • Cannot prioritize findings by business impact                ║
║  • Cannot write executive narrative for leadership              ║
║  • Cannot recommend remediation order based on risk             ║
║  • Cannot correlate compliance gaps to recent changes           ║
╚══════════════════════════════════════════════════════════════════╝
```

**This is what the AI options below add.**

---

## Option 0: SRE Agent (Recommended)

> **Effort:** ~1 hour | **AI adds:** Executive narrative, root-cause hypothesis, trend narrative

Azure SRE Agent is the recommended option. Upload the compliance skill, and the agent adds the 5% AI narrative on top of the same `az CLI` queries the script uses.

### Setup

| Resource | Location |
|----------|----------|
| Full SRE Agent deployment guide | [`docs/sre-agent-setup.md`](../sre-agent-setup.md) |
| Compliance investigation skill | [`sre-skills/compliance-investigation/SKILL.md`](../../sre-skills/compliance-investigation/SKILL.md) |
| KQL compliance state query | [`sre-tools/kusto/query-compliance-state.kql`](../../sre-tools/kusto/query-compliance-state.kql) |
| GLPI ticket creation tool | [`sre-tools/python/glpi_tools.py`](../../sre-tools/python/glpi_tools.py) |
| Automation script (95% base) | [`scripts/demo-compliance-report.ps1`](../../scripts/demo-compliance-report.ps1) |

### Skill Auto-Activation

The `compliance-investigation` skill activates on these triggers:

```yaml
triggers:
  - Compliance score drops >5% in 24 hours
  - New high-severity compliance finding detected
  - Azure Policy reports non-compliant resources
  - User asks about compliance status
```

### Scheduled Task

Configure in **Builder → Scheduled Tasks**:

| Setting | Value |
|---------|-------|
| **Task name** | `weekly-compliance-report` |
| **Schedule** | Weekly (Monday 08:00 UTC) |
| **Prompt** | `Generate a compliance report for all Arc servers in rg-arcbox-itpro. Include Defender for Cloud regulatory compliance, Azure Policy state, and Secure Score. Compare with last week's report and highlight trends.` |

### Example Interaction

**Query:**

> **User:** Generate a compliance report for leadership — include trends and priorities.

**Agent execution trace:**

```
Step 1 — Querying Defender for Cloud compliance
  → RunAzCliReadCommands: az security regulatory-compliance-standards list -o json
  → Found 4 standards: CIS (8 failing), NIST (15 failing), ISO 27001 (4 failing), PCI DSS (22 failing)

Step 2 — Querying Azure Policy state
  → RunAzCliReadCommands: az policy state summarize --resource-group rg-arcbox-itpro -o json
  → 3 non-compliant policies, 8 non-compliant resources

Step 3 — Querying Secure Score
  → RunAzCliReadCommands: az security secure-score-controls list -o json
  → Score: 72/100 (72%)

Step 4 — Correlating findings and spot-checking
  → RunAzCliReadCommands: Arc Run Command on ArcBox-Win2K22 (audit policy check)
  → RunAzCliReadCommands: Arc Run Command on ArcBox-SQL (firewall check)

Step 5 — Comparing with previous run (Cosmos DB)
  → cosmos-query-runs(task_type="compliance", date="2025-01-08")
  → Last week: CIS had 12 failing controls — now 8 (improved)
```

**Agent output (the 5% AI adds):**

> **📋 Weekly Compliance Report — 2025-01-15**
>
> **Overall compliance improved 4% this month** (from 68% → 72% Secure Score).
>
> **Executive Summary:**
> Compliance posture is trending positive. CIS benchmark failures dropped from 12 → 8 after the firewall remediation sprint completed Friday. However, **8 servers in the finance zone remain priority** — they account for 60% of remaining PCI DSS failures.
>
> **🔴 Priority 1 — PCI DSS (22 failing controls)**
> - Root cause: 15 servers lost the Guest Configuration agent after last month's patch cycle (KB5034441). The agent was removed during cleanup and never reinstalled.
> - Affected: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL + 5 others in finance OU
> - **Recommendation:** Redeploy Guest Configuration extension via Azure Policy remediation task
>
> **🟡 Priority 2 — CIS Benchmark (8 failing)**
> - Down from 12 last week ✅
> - Remaining: 4 servers missing audit policy configuration, 4 missing Windows Firewall rules
> - Estimate: 2 hours remediation via Group Policy push
>
> **🟢 ISO 27001 (4 failing) / NIST (15 failing)**
> - Stable — most findings are informational (tagging, naming conventions)
> - Schedule for next sprint
>
> **Trend:** At current remediation velocity (4 controls/week), PCI DSS compliance target of <10 failures is achievable by Feb 15.
>
> **GLPI tickets created:**
> - [#156 — Redeploy Guest Configuration on finance zone servers](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=156) (P1)
> - [#157 — Audit policy GPO push for 4 CIS failures](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=157) (P2)

### What Makes SRE Agent Unique

| Feature | SRE Agent | Others |
|---------|-----------|--------|
| **Scheduled reports** | ✅ Built-in (weekly) | ❌ Requires external scheduler |
| **Auto-trigger on compliance drift** | ✅ Azure Monitor alert | ❌ Must build webhook handler |
| **Memory** | ✅ Remembers last week's numbers | ❌ Must implement state |
| **No custom code** | ✅ Portal-only | ❌ Python code required |

---

## Option A: Microsoft Agent Framework

> **Effort:** ~2–3 weeks | **AI adds:** Same narrative + full code-level control

### Architecture

```
┌──────────────────────────────────────────────────┐
│  Your host (Container Apps / local dev)           │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         compliance_agent.py                  │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ SkillsProvider│   │ FunctionTools       │  │  │
│  │  │ (auto-loads   │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)    │   │ │query_compliance│ │  │  │
│  │  └──────────────┘   │ │query_policy     │ │  │  │
│  │                      │ │query_score      │ │  │  │
│  │  ┌──────────────┐   │ │spot_check_server│ │  │  │
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
# Auto-discovers compliance-investigation/SKILL.md
```

### Function Tools

```python
@FunctionTool
def query_defender_compliance() -> dict:
    """Query Defender for Cloud regulatory compliance standards."""
    result = subprocess.run(
        ["az", "security", "regulatory-compliance-standards", "list", "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def query_policy_state(resource_group: str = "rg-arcbox-itpro") -> dict:
    """Query Azure Policy compliance summary for the resource group."""
    result = subprocess.run(
        ["az", "policy", "state", "summarize",
         "--resource-group", resource_group, "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def query_secure_score() -> dict:
    """Query Defender for Cloud Secure Score controls."""
    result = subprocess.run(
        ["az", "security", "secure-score-controls", "list", "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

@FunctionTool
def spot_check_server(machine_name: str, script: str) -> dict:
    """Run a compliance spot-check on an Arc-enrolled server."""
    result = subprocess.run(
        ["az", "connectedmachine", "run-command", "create",
         "--resource-group", "rg-arcbox-itpro",
         "--machine-name", machine_name,
         "--name", "ComplianceCheck",
         "--script", script, "-o", "json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

### Example Interaction

```
Compliance Agent (Agent Framework) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Generate a compliance report with executive narrative.

Agent: I'll query Defender for Cloud, Azure Policy, and Secure Score, then provide
an executive summary.

  → Calling query_defender_compliance()
  → Calling query_policy_state("rg-arcbox-itpro")
  → Calling query_secure_score()
  → Calling spot_check_server("ArcBox-Win2K22", "auditpol /get /category:*")

📋 Compliance Report — 2025-01-15

Compliance improved 4% this month. CIS benchmark failures dropped from 12 → 8
after the firewall remediation sprint. 8 servers in the finance zone remain
priority — they account for 60% of PCI DSS failures.

Root-cause hypothesis: 15 servers lost the Guest Configuration agent after
KB5034441 was applied last month. The agent was removed during post-patch
cleanup and was never reinstalled.

Recommended remediation order:
1. Redeploy Guest Configuration on finance servers (P1 — fixes 60% of PCI failures)
2. Push audit policy GPO for 4 CIS failures (P2 — 2 hours)
3. Schedule tagging/naming fixes for next sprint (P3)

Create GLPI tickets for #1 and #2? [y/n]
```

### Scheduling (External)

```bash
# Weekly compliance report via cron
0 8 * * 1 cd /path/to/compliance-agent && python compliance_agent.py \
  --prompt "Generate weekly compliance report for rg-arcbox-itpro" \
  >> /var/log/compliance-report.log 2>&1
```

### Comparison with SRE Agent

| Aspect | SRE Agent | Agent Framework |
|--------|-----------|-----------------|
| **Setup effort** | ~1 hour (portal) | ~2–3 weeks (code + hosting) |
| **Skills** | Upload via UI | `SkillsProvider` (identical behavior) |
| **Compliance tools** | Built-in `RunAzCliReadCommands` | Custom `FunctionTool` wrappers |
| **Trend comparison** | Built-in memory | Must implement (Cosmos DB / file) |
| **Custom report format** | Limited (agent output) | Full control (HTML, PDF, email) |
| **Scheduling** | ✅ Built-in | ❌ External (Logic Apps / cron) |

---

## Option B: Foundry Agent Service

> **Effort:** ~1–2 weeks | **AI adds:** Same narrative + managed hosting on Foundry platform

### Architecture

```
┌──────────────────────────────────────────────────┐
│            Azure AI Foundry Project               │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         compliance-report-agent              │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Instructions  │   │ Function Tools      │  │  │
│  │  │ (from        │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)   │   │ │query_compliance│ │  │  │
│  │  └──────────────┘   │ │query_policy     │ │  │  │
│  │                      │ │query_score      │ │  │  │
│  │  ┌──────────────┐   │ │spot_check      │ │  │  │
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

skill_content = Path("sre-skills/compliance-investigation/SKILL.md").read_text()

client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

agent = client.agents.create(
    name="compliance-report-agent",
    instructions=f"""You are a compliance reporting specialist for Azure Arc-enrolled servers.
Your job is to generate executive compliance reports that leadership can act on.

Automation handles 95% of the work (data collection and formatting). You add the 5%:
- Executive narrative explaining WHY compliance changed
- Root-cause hypothesis for compliance drift
- Prioritized remediation recommendations by business impact

{skill_content}""",
    tools=compliance_tools + [{"type": "code_interpreter"}],
    model="gpt-4o",
)
```

### Function Tool Definitions

```python
compliance_tools = [
    {
        "type": "function",
        "function": {
            "name": "query_defender_compliance",
            "description": "Query Defender for Cloud regulatory compliance standards (CIS, NIST, ISO, PCI DSS)",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_policy_state",
            "description": "Query Azure Policy compliance summary for the resource group",
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
            "name": "query_secure_score",
            "description": "Query Defender for Cloud Secure Score controls",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spot_check_server",
            "description": "Run a compliance spot-check script on an Arc-enrolled server",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_name": {"type": "string"},
                    "script": {"type": "string"}
                },
                "required": ["machine_name", "script"]
            }
        }
    }
]
```

### Example Interaction

```
You: Generate a compliance report with executive narrative for the board.

Agent: I'll compile compliance data from Defender for Cloud and Azure Policy,
then write an executive summary.

  → query_defender_compliance()
  → query_policy_state("rg-arcbox-itpro")
  → query_secure_score()
  → code_interpreter: calculating week-over-week trend from historical data

📋 Board Compliance Summary — January 2025

Overall compliance score: 72% (↑4% from December).

Key narrative: The firewall remediation sprint closed 4 CIS controls. PCI DSS
remains our biggest gap — 22 failing controls driven by Guest Configuration
agent loss after the December patch cycle.

Hypothesis: KB5034441 side-effect removed the Guest Configuration extension
from 15 servers. Remediation is a single Policy remediation task (ETA: 1 day).

[Code Interpreter generated trend chart showing 3-month compliance trajectory]
```

### Scheduling

```python
# Azure Functions timer trigger
@app.timer_trigger(schedule="0 0 8 * * 1", arg_name="timer")
def compliance_report_trigger(timer: func.TimerRequest) -> None:
    from compliance_agent import run_single_prompt
    run_single_prompt("Generate weekly compliance report for rg-arcbox-itpro with executive narrative.")
```

### Comparison with SRE Agent

| Aspect | SRE Agent | Foundry Agent |
|--------|-----------|---------------|
| **Setup effort** | ~1 hour (portal) | ~1–2 weeks (SDK + hosting) |
| **Skills** | Upload via UI | Inject as `instructions` |
| **Code Interpreter** | ✅ Built-in | ✅ Built-in (trend charts) |
| **Multi-skill routing** | ✅ Auto-routes | ❌ One skill per agent |
| **Scheduling** | ✅ Built-in | ❌ External trigger |
| **Hosting** | Managed (SaaS) | Managed (Foundry platform) |

---

## Option C: GitHub Copilot CLI

> **Effort:** ~1 day | **AI adds:** Interactive executive narrative on demand

### Setup

```bash
# Copy compliance skill to Copilot skills directory
cp -r sre-skills/compliance-investigation .github/skills/

# Or for personal skills (all projects)
cp -r sre-skills/compliance-investigation ~/.copilot/skills/

# Verify
/skills list
# → compliance-investigation loaded
```

**That's it.** Copilot CLI runs `az CLI` directly in your terminal — no tool wrappers needed.

### Example Interaction

```
> Run a compliance check on my Arc servers and give me an executive summary

Copilot: I'll query Defender for Cloud and Azure Policy for compliance status,
then provide an executive narrative.

[Running] az security regulatory-compliance-standards list -o json
[Running] az policy state summarize --resource-group rg-arcbox-itpro -o json
[Running] az security secure-score-controls list -o json

📋 Compliance Report — 2025-01-15

Based on the results across 3 sources:

**Overall Secure Score: 72/100**

Defender for Cloud findings:
- CIS Azure Foundations: 8 failing controls (142 passing)
- NIST SP 800-53: 15 failing (312 passing)
- PCI DSS v4: 22 failing — this is your biggest gap

Azure Policy findings:
- 3 non-compliant policies affecting 8 resources in rg-arcbox-itpro
- Top offender: Guest Configuration policy (5 servers missing the extension)

**Executive Narrative:**
Compliance improved 4% this month. The remaining PCI DSS gap appears linked to
Guest Configuration agent loss — likely a side-effect of KB5034441 from the
December patch cycle. 15 servers in the finance zone lost the extension and it
was never reinstalled. This single remediation (redeploy via Policy remediation
task) would close ~60% of remaining PCI failures.

Priority order:
1. Redeploy Guest Configuration extension (P1 — 1 day)
2. Push audit policy GPO for CIS gaps (P2 — 2 hours)
3. Address tagging policies (P3 — next sprint)

Shall I create GLPI tickets for priorities 1 and 2?
```

### Spot-Check a Specific Server

```
> Check audit policy configuration on ArcBox-Win2K22

Copilot: I'll run a compliance spot-check via Azure Arc.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name AuditCheck \
  --script "auditpol /get /category:*"

Audit policy results for ArcBox-Win2K22:
- Account Logon: No Auditing ⚠️ (CIS requires Success+Failure)
- Logon/Logoff: Success only ⚠️ (CIS requires Success+Failure)
- Object Access: No Auditing ⚠️

This server is missing 3 CIS audit policy controls. Remediation: apply
the "CIS L1 - Audit Policy" GPO to the server's OU.
```

### Limitations

> **💡 Tip:** Install the [Azure Skills Plugin](https://github.com/microsoft/azure-skills) for additional Azure diagnostics, observability, and compliance capabilities. The plugin provides 20 Azure skills + 200+ MCP tools that complement our custom Wintel ops skills. For compliance, the plugin's `azure-compliance` skill uses `azqr` (Azure Quick Review) for infrastructure compliance scanning — this is different from our Defender for Cloud approach (CIS, NIST, PCI DSS standards) but both are valid, complementary compliance tools. Use `azure-compliance` for Azure resource configuration checks and our `compliance-investigation` skill for regulatory framework compliance.

| Limitation | Impact | Workaround |
|---|---|---|
| **Interactive only** | No scheduled compliance reports | Run automation script via cron; use Copilot for ad-hoc analysis |
| **No persistent memory** | Can't compare with last week automatically | Pass previous report as context or use custom instructions |
| **Session-based** | Knowledge lost between sessions | Use `~/.copilot/instructions.md` for standing context |

---

## Skills Reusability

All options reuse the **same** `sre-skills/compliance-investigation/SKILL.md`:

| Platform | How Skills Load |
|---|---|
| **SRE Agent** | Upload `SKILL.md` via Builder → Skills UI |
| **Agent Framework** | `SkillsProvider(skill_paths=["./sre-skills"])` — auto-discovers |
| **Foundry Agent** | `SKILL.md` content injected as agent `instructions` parameter |
| **Copilot CLI** | Copy to `.github/skills/` or `~/.copilot/skills/` — auto-discovers |

## Key Takeaway

**The 95% is already built.** The automation script (`scripts/demo-compliance-report.ps1`) queries all three compliance sources and generates a formatted report. The AI options above add only the executive narrative, root-cause hypothesis, and prioritization — the 5% that makes the difference between a data dump and actionable intelligence for leadership.

Choose the AI option that fits your operational model:

| If you need... | Choose |
|---|---|
| Turnkey scheduled reports with memory | **SRE Agent** (Option 0) |
| Full code control + custom output formats | **Agent Framework** (Option A) |
| Managed hosting on AI Foundry platform | **Foundry Agent** (Option B) |
| Ad-hoc compliance investigation from terminal | **Copilot CLI** (Option C) |

## See Also

- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [Scenario A: Health Check](scenario-a-health-check/) — 70% automation / 30% AI example
- [Compliance investigation skill](../../sre-skills/compliance-investigation/SKILL.md) — the SKILL.md source
- [Compliance state KQL query](../../sre-tools/kusto/query-compliance-state.kql) — Resource Graph query
- [Compliance report script](../../scripts/demo-compliance-report.ps1) — the 95% automation baseline
