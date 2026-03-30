# Option 0: SRE Agent — Health Check Implementation

> **Status:** Already implemented. This document is a reference guide pointing to the existing setup.

Azure SRE Agent is the **recommended** option for Scenario A. It requires no custom code — skills, tools, and scheduling are configured through the SRE Agent portal at [sre.azure.com](https://sre.azure.com).

## Setup References

| Resource | Location |
|----------|----------|
| Full SRE Agent deployment guide | [`docs/sre-agent-setup.md`](../../sre-agent-setup.md) |
| Health check skill definition | [`sre-skills/wintel-health-check-investigation/SKILL.md`](../../../sre-skills/wintel-health-check-investigation/SKILL.md) |
| Scenario A demo walkthrough | [`docs/demos/scenario-a-health-check.md`](../../demos/scenario-a-health-check.md) |
| GLPI ticket creation tool | [`sre-tools/python/glpi_tools.py`](../../../sre-tools/python/glpi_tools.py) |
| KQL perf trends query | [`sre-tools/kusto/query-perf-trends.kql`](../../../sre-tools/kusto/query-perf-trends.kql) |
| Health Insights subagent | [`agents/health-insights.json`](../../../agents/health-insights.json) |

## How the Skill Loads Automatically

When you type a health-related query into the SRE Agent chat, the agent **automatically** activates the `wintel-health-check-investigation` skill based on trigger matching:

```yaml
# From SKILL.md frontmatter
triggers:
  - Health check run completed with WARNING or CRITICAL status
  - Alert from Azure Monitor: disk, CPU, memory, or service threshold exceeded
  - User asks about a server health issue
```

No manual skill selection required. The agent matches your query against the trigger descriptions and loads the skill's investigation steps as context.

**Trigger examples that activate the skill:**

| User Query | Skill Activated? |
|---|---|
| "Check the health of all my Arc servers" | ✅ Yes |
| "ArcBox-SQL disk is almost full, investigate" | ✅ Yes |
| "Why is ArcBox-Win2K22 memory climbing?" | ✅ Yes |
| "What patches are missing?" | ❌ No (activates `patch-validation` instead) |

## Scheduled Task Configuration

The SRE Agent supports built-in scheduled tasks for proactive health checks. Configure in **Builder → Scheduled Tasks**:

| Setting | Value |
|---------|-------|
| **Task name** | `proactive-health-scan` |
| **Schedule** | Every 6 hours (06:00, 12:00, 18:00, 00:00 UTC) |
| **Prompt** | `Run a comprehensive health check on all Arc servers in rg-arcbox-itpro. Report any WARNING or CRITICAL findings and create GLPI tickets for issues requiring attention.` |
| **Skills** | Auto-selected (`wintel-health-check-investigation`) |
| **Notification** | Email + Teams channel on CRITICAL findings |

The scheduled task runs the same investigation flow as an interactive chat query, but without user involvement.

## Example SRE Agent Chat Interaction

### Query

> **User:** Check the health of all my Arc servers and summarize.

### Agent Response

The agent executes the `wintel-health-check-investigation` skill and produces the following (visible in the activity trace):

```
Step 1 — Identifying Arc servers
  → RunAzCliReadCommands: az graph query -q "Resources | where type == 
    'microsoft.hybridcompute/machines' and resourceGroup == 'rg-arcbox-itpro'"
  → Found 5 servers: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL, 
    ArcBox-Ubuntu-01, ArcBox-Ubuntu-02

Step 2 — Querying 7-day performance trends from Log Analytics
  → RunAzCliReadCommands: az monitor log-analytics query --workspace 
    f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query 
    "Perf | where TimeGenerated > ago(7d) | where Computer in 
    ('ArcBox-Win2K22','ArcBox-Win2K25','ArcBox-SQL') | summarize 
    avg(CounterValue) by bin(TimeGenerated, 1d), Computer, CounterName"

Step 3 — Running live diagnostics on flagged servers
  → RunAzCliReadCommands: Arc Run Command on ArcBox-SQL (disk check)
  → RunAzCliReadCommands: Arc Run Command on ArcBox-Win2K22 (memory check)

Step 4 — Analysis complete
```

### Agent Summary Output

> **🏥 Daily Health Brief — 2025-01-15 06:00 UTC**
>
> **Overall estate health: 3/5 servers healthy (60%)**
>
> 🔴 **ArcBox-SQL** — Disk E: at 91.3% (CRITICAL)
> - SQL transaction logs growing at +2.3%/day
> - **Projected to hit 95% in ~5 days**
> - Ticket created: [GLPI #142 — ArcBox-SQL Disk E: trending to capacity](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=142)
>
> 🟡 **ArcBox-Win2K22** — Memory at 62.1% but **trending up**
> - Was 48% a week ago, climbing +2%/day
> - Currently within thresholds but anomalous vs. historical baseline (45–50%)
> - Correlates with app deployment v3.2.1 on Tuesday
>
> 🟢 **ArcBox-Win2K25, ArcBox-Ubuntu-01, ArcBox-Ubuntu-02** — All healthy
>
> **🔗 Cross-server correlation:** Memory increases on ArcBox-Win2K22, ArcBox-Win2K25, and ArcBox-SQL all started Tuesday — investigate app deployment v3.2.1.
>
> **Top 3 action items:**
> 1. Investigate SQL transaction log growth on ArcBox-SQL (P2 — 5-day runway)
> 2. Review app v3.2.1 deployment for memory regression (P3)
> 3. Schedule capacity review for ArcBox-SQL E: drive (P4)

## What Makes SRE Agent Unique

Compared to the other three options, SRE Agent provides these out of the box:

| Feature | SRE Agent | Others |
|---------|-----------|--------|
| **Scheduled execution** | ✅ Built-in (every 6 h) | ❌ Requires external scheduler |
| **Incident auto-response** | ✅ Azure Monitor triggers | ❌ Must build webhook handler |
| **Memory / learning** | ✅ Built-in (remembers past patterns) | ❌ Must implement state management |
| **No custom code** | ✅ Portal-only configuration | ❌ Python code required |
| **Managed identity** | ✅ Auto-provisioned | ❌ Must configure `DefaultAzureCredential` |

## See Also

- [README.md](README.md) — comparison of all 4 options
- [Option A — Agent Framework](option-a-agent-framework.md) — if SRE Agent is unavailable in your region
- [Option B — Foundry Agent](option-b-foundry-agent.md) — if already on Azure AI Foundry
- [Option C — Copilot CLI](option-c-copilot-cli.md) — for interactive terminal usage
