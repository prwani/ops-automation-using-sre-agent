# Option B: Foundry Agent Service — Health Check Implementation

Step-by-step guide to implement Scenario A (Daily Health Check) using **Azure AI Foundry Agent Service** with the `azure-ai-projects` SDK.

> **When to use:** Your organization is already on the Azure AI Foundry platform and you want a managed agent with minimal infrastructure to maintain.

## Architecture

```
┌──────────────────────────────────────────────────┐
│            Azure AI Foundry Project               │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         health-check-agent                   │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Instructions  │   │ Function Tools      │  │  │
│  │  │ (from        │   │ ┌────────────────┐ │  │  │
│  │  │  SKILL.md)   │   │ │query_arc_servers│ │  │  │
│  │  └──────────────┘   │ │run_health_check │ │  │  │
│  │                      │ │query_perf_trends│ │  │  │
│  │  ┌──────────────┐   │ │create_glpi_tickt│ │  │  │
│  │  │ Code         │   │ └────────────────┘ │  │  │
│  │  │ Interpreter  │   └────────────────────┘  │  │
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
| **Azure AI Foundry project** | With a `gpt-4o` model deployment |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |
| **GLPI** | Running with OAuth client configured |

## Project Structure

```
foundry-agent/
├── health_check_agent.py    # Agent creation, tool dispatch, conversation loop
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variables template
```

## Step 1: Set Up Azure AI Foundry Project

If you don't already have a Foundry project:

```bash
# Create via Azure CLI
az ml workspace create \
  --name wintel-ops-foundry \
  --resource-group rg-opsauto-sc \
  --location swedencentral \
  --kind project
```

Or create via the [Azure AI Foundry portal](https://ai.azure.com):
1. Click **+ New project**
2. Name: `wintel-ops-foundry`
3. Region: `Sweden Central`
4. Deploy a `gpt-4o` model

Note your **project endpoint** — you'll need it in `.env`.

## Step 2: Clone and Configure

```bash
cd docs/implementations/scenario-a-health-check/foundry-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Set Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Azure AI Foundry
AZURE_AI_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project-name
FOUNDRY_MODEL=gpt-4o

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

## Step 4: Run the Agent

```bash
python health_check_agent.py
```

Interactive mode:

```
Health Check Agent (Foundry Agent Service) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Check the health of all my Arc servers and summarize.
```

## Step 5: Example Interaction

### Full Health Check

```
You: Check the health of all Arc servers in rg-arcbox-itpro and give me a morning brief.
```

The agent:

1. **Reads SKILL.md instructions** — the skill content is injected as the agent's `instructions` parameter, providing the investigation procedure.
2. **Calls `query_arc_servers`** — the function tool lists all 5 servers.
3. **Calls `run_health_check`** — queries Log Analytics for each server's current metrics.
4. **Calls `query_perf_trends`** — pulls 7-day history for flagged servers.
5. **Uses Code Interpreter** — performs trend projection (linear regression on disk growth).
6. **Calls `create_glpi_ticket`** — creates tickets for CRITICAL/WARNING findings.
7. **Returns morning brief** — structured natural-language summary.

**Expected output:**

> **🏥 Morning Health Brief — 2025-01-15**
>
> **Estate: 3/5 healthy (60%)**
>
> 🔴 **ArcBox-SQL** — Disk E: 91.3% CRITICAL
> - Trend: +2.3%/day over 7 days — reaches 95% in ~5 days
> - Root cause: SQL transaction logs growing unchecked
> - GLPI ticket #142 created (P2)
>
> 🟡 **ArcBox-Win2K22** — Memory anomaly (62% but +2%/day)
> - Below threshold but diverging from baseline (45–50%)
> - Correlates with app v3.2.1 deployment
>
> 🟢 ArcBox-Win2K25, ArcBox-Ubuntu-01, ArcBox-Ubuntu-02 — All clear

### Disk Investigation

```
You: Deep-dive into ArcBox-SQL disk E: — what's consuming space?
```

The agent runs an Arc command on the server to list top directories by size, then analyzes the output.

## How SKILL.md Becomes Agent Instructions

Foundry Agent Service uses an `instructions` parameter (system prompt) instead of a `SkillsProvider`. The agent code loads the skill content at creation time:

```python
skill_path = Path("../../../../sre-skills/wintel-health-check-investigation/SKILL.md")
skill_content = skill_path.read_text(encoding="utf-8")

agent = client.agents.create(
    name="health-check-agent",
    instructions=f"You are a health check specialist.\n\n{skill_content}",
    tools=tools,
    model="gpt-4o",
)
```

The entire SKILL.md — triggers, investigation steps, thresholds, escalation matrix — becomes part of the agent's system prompt. The agent follows these steps just like SRE Agent follows the uploaded skill.

**Trade-off vs. SkillsProvider:**

| Aspect | SkillsProvider (Agent Framework) | Instructions (Foundry) |
|--------|----------------------------------|------------------------|
| Multi-skill routing | ✅ Auto-selects by trigger match | ❌ Must create separate agents per skill |
| Skill updates | Hot-reload on next call | Must recreate the agent |
| Context size | Only loads relevant skill | Loads full skill into every request |

## Code Interpreter for Trend Analysis

The Foundry agent includes `code_interpreter` as a tool, enabling it to:

- Perform linear regression on disk growth data
- Project when a metric will breach a threshold
- Generate trend visualizations (if requested)
- Calculate statistical anomalies (z-scores, deviation from baseline)

This is equivalent to SRE Agent's built-in code interpreter capability.

## Adding Scheduled Execution (Optional)

Like Agent Framework, Foundry Agent Service requires an external trigger for scheduled runs:

### Azure Logic Apps

```json
{
  "triggers": {
    "Recurrence": {
      "type": "Recurrence",
      "recurrence": { "frequency": "Hour", "interval": 6 }
    }
  },
  "actions": {
    "RunFoundryAgent": {
      "type": "Http",
      "inputs": {
        "method": "POST",
        "uri": "https://your-foundry-endpoint/agents/run",
        "body": {
          "prompt": "Run a comprehensive health check on all Arc servers in rg-arcbox-itpro."
        }
      }
    }
  }
}
```

### Azure Functions (Timer Trigger)

```python
import azure.functions as func

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 */6 * * *", arg_name="timer")
def health_check_trigger(timer: func.TimerRequest) -> None:
    # Import and run the Foundry agent with a health-check prompt
    from health_check_agent import run_single_prompt
    run_single_prompt("Run health check on all Arc servers in rg-arcbox-itpro.")
```

## Comparison with SRE Agent

| Aspect | SRE Agent | Foundry Agent |
|--------|-----------|---------------|
| **Setup effort** | ~1 hour (portal) | ~1–2 weeks (SDK + hosting) |
| **Skills** | Upload via UI | Inject as `instructions` |
| **Tools** | Built-in `RunAzCliReadCommands` | Custom function definitions |
| **Code Interpreter** | ✅ Built-in | ✅ Built-in |
| **Scheduling** | ✅ Built-in | ❌ External trigger needed |
| **Memory** | ✅ Built-in | ⚠️ Thread-based (within session) |
| **Hosting** | Managed (SaaS) | Managed (Foundry platform) |
| **Multi-skill** | ✅ Auto-routes by trigger | ❌ One skill per agent (or concatenate) |

## See Also

- [README.md](README.md) — comparison of all 4 options
- [foundry-agent/health_check_agent.py](foundry-agent/health_check_agent.py) — complete source code
- [`sre-skills/wintel-health-check-investigation/SKILL.md`](../../../sre-skills/wintel-health-check-investigation/SKILL.md) — skill definition
- [Azure AI Foundry Agent Service docs](https://learn.microsoft.com/azure/ai-services/agents/)
