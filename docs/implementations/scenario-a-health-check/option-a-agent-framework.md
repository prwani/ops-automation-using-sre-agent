# Option A: Microsoft Agent Framework — Health Check Implementation

Step-by-step guide to implement Scenario A (Daily Health Check) using the **Microsoft Agent Framework** with Azure OpenAI.

> **When to use:** SRE Agent is unavailable in your region, or you need full code-level control over the agent's behavior and hosting.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Your host (Azure Container Apps / local dev)     │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         health_check_agent.py                │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ SkillsProvider│   │ FunctionTools       │  │  │
│  │  │ (auto-loads   │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)    │   │ │query_arc_servers│ │  │  │
│  │  └──────────────┘   │ │run_health_check │ │  │  │
│  │                      │ │query_perf_trends│ │  │  │
│  │  ┌──────────────┐   │ │create_glpi_tickt│ │  │  │
│  │  │ AzureOpenAI  │   │ └────────────────┘ │  │  │
│  │  │ Responses API│   └────────────────────┘  │  │
│  │  └──────────────┘                           │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │  Azure Arc   │  │Log Analytics│  │   GLPI   │ │
│  │  (az CLI)    │  │  (az CLI)   │  │ (REST)   │ │
│  └──────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | 3.11 or later |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |
| **Azure OpenAI** | Deployment with `gpt-4o` model (or equivalent) |
| **GLPI** | Running at `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` with OAuth client configured |

## Project Structure

```
agent-framework/
├── health_check_agent.py    # Main agent — tools, skills, conversation loop
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variables template
```

## Step 1: Clone and Configure

```bash
cd docs/implementations/scenario-a-health-check/agent-framework

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Set Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-03-01-preview

# Azure environment
AZURE_SUBSCRIPTION_ID=31adb513-7077-47bb-9567-8e9d2a462bcf
AZURE_RESOURCE_GROUP=rg-arcbox-itpro
AZURE_LOCATION=swedencentral
LOG_ANALYTICS_WORKSPACE_ID=f98fca75-7479-45e5-bf0c-87b56a9f9e8c

# GLPI
GLPI_BASE_URL=http://glpi-opsauto-demo.swedencentral.azurecontainer.io
GLPI_CLIENT_ID=YOUR_CLIENT_ID
GLPI_CLIENT_SECRET=YOUR_CLIENT_SECRET
GLPI_USERNAME=glpi
GLPI_PASSWORD=YOUR_ADMIN_PASSWORD
```

## Step 3: Verify Azure CLI Access

```bash
# Confirm you can see Arc servers
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' and resourceGroup == 'rg-arcbox-itpro' | project name, properties.status" -o table

# Confirm Log Analytics access
az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Perf | take 1" -o json
```

## Step 4: Run the Agent

```bash
python health_check_agent.py
```

This starts an interactive conversation loop. Type your queries:

```
Health Check Agent (Agent Framework) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Check the health of all my Arc servers and summarize.
```

## Step 5: Example Interaction

### Query 1 — Full health check

```
You: Check the health of all my Arc servers in rg-arcbox-itpro and give me a morning brief.
```

The agent:
1. **Loads the skill** — `SkillsProvider` auto-discovers `wintel-health-check-investigation/SKILL.md` and injects its investigation steps as context.
2. **Calls `query_arc_servers()`** — lists all 5 Arc-enrolled servers and their connection status.
3. **Calls `run_health_check_on_server()`** — for each server, queries Log Analytics for CPU, memory, disk, and service metrics.
4. **Calls `query_perf_trends()`** — pulls 7-day trends for servers with elevated metrics.
5. **Reasons over the data** — using the skill's step-by-step procedure to identify anomalies, correlate cross-server patterns, and project trends.
6. **Calls `create_glpi_ticket()`** — creates tickets for CRITICAL or WARNING findings.
7. **Returns a morning brief** — natural-language summary with severity indicators.

**Expected output:**

> **🏥 Morning Health Brief — 2025-01-15 06:00 UTC**
>
> **Estate: 3/5 healthy (60%)**
>
> 🔴 **ArcBox-SQL** — Disk E: 91.3% (CRITICAL)
> - Growing +2.3%/day — projected to hit 95% in ~5 days
> - Probable cause: SQL transaction logs not truncated
> - Created: GLPI #142
>
> 🟡 **ArcBox-Win2K22** — Memory trending up (62% but was 48% last week)
> - +2%/day increase correlates with app v3.2.1 deployment
> - Below threshold but anomalous
>
> 🟢 ArcBox-Win2K25, ArcBox-Ubuntu-01, ArcBox-Ubuntu-02 — healthy
>
> **Action items:** (1) Investigate SQL log growth, (2) Review app v3.2.1 for memory regression

### Query 2 — Investigate a specific server

```
You: Investigate disk usage on ArcBox-SQL — what's filling up drive E:?
```

### Query 3 — Create a ticket

```
You: Create a P2 GLPI ticket for the ArcBox-SQL disk issue with the trend data.
```

## How Skills Auto-Load from sre-skills/

The `SkillsProvider` in `health_check_agent.py` points to the project's `sre-skills/` directory:

```python
skills = SkillsProvider(skill_paths=["../../../../sre-skills"])
```

At startup, it:

1. **Scans** all subdirectories for `SKILL.md` files
2. **Parses** YAML frontmatter (name, triggers, tools, description)
3. **Registers** each skill as available context
4. **Injects** the relevant skill's content when the user's query matches a trigger

The agent receives the skill content as additional context in its system prompt, exactly like SRE Agent does — the skill's investigation steps, thresholds, escalation matrix, and tool references guide the agent's behavior.

**Skills discovered:**

| Skill | Path |
|-------|------|
| `wintel-health-check-investigation` | `sre-skills/wintel-health-check-investigation/SKILL.md` |
| `security-agent-troubleshooting` | `sre-skills/security-agent-troubleshooting/SKILL.md` |
| `patch-validation` | `sre-skills/patch-validation/SKILL.md` |
| `compliance-investigation` | `sre-skills/compliance-investigation/SKILL.md` |
| `vmware-bau-operations` | `sre-skills/vmware-bau-operations/SKILL.md` |

## Adding Scheduled Execution (Optional)

Agent Framework does not include a built-in scheduler. To run the health check on a schedule, use an external trigger:

### Option 1 — Azure Logic Apps

```json
{
  "triggers": {
    "Recurrence": {
      "type": "Recurrence",
      "recurrence": { "frequency": "Hour", "interval": 6 }
    }
  },
  "actions": {
    "HTTP": {
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://your-container-app.azurecontainerapps.io/run",
        "body": {
          "prompt": "Run a comprehensive health check on all Arc servers in rg-arcbox-itpro."
        }
      }
    }
  }
}
```

### Option 2 — cron (Linux/macOS)

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/agent-framework && python health_check_agent.py --prompt "Run health check on all Arc servers" >> /var/log/health-check.log 2>&1
```

## Comparison with SRE Agent

| Aspect | SRE Agent | Agent Framework |
|--------|-----------|-----------------|
| **Setup effort** | ~1 hour (portal) | ~2–3 weeks (code + hosting) |
| **Skills** | Upload via UI | `SkillsProvider` (identical behavior) |
| **Tools** | Built-in `RunAzCliReadCommands` | Custom `FunctionTool` wrappers |
| **Scheduling** | Built-in | External (Logic Apps / cron) |
| **Memory** | Built-in | Must implement (Cosmos DB / file) |
| **Hosting** | Managed (SaaS) | Self-hosted (Container Apps) |
| **Customization** | Limited to portal options | Full code-level control |

## See Also

- [README.md](README.md) — comparison of all 4 options
- [agent-framework/health_check_agent.py](agent-framework/health_check_agent.py) — complete source code
- [`sre-skills/wintel-health-check-investigation/SKILL.md`](../../../sre-skills/wintel-health-check-investigation/SKILL.md) — skill definition
- [`sre-tools/python/glpi_tools.py`](../../../sre-tools/python/glpi_tools.py) — GLPI tool reference
