# Scenario B: Alert Triage — Implementation Comparison (All 4 Options)

> **Automation ratio:** 70% deterministic scripts / 30% AI reasoning
>
> **What the 70% handles:** Poll fired alerts, map severity → urgency, auto-create GLPI tickets, basic remediation (restart service).
>
> **What the 30% AI adds:** Correlate multiple alerts into a single incident, determine root cause from alert patterns, suggest context-aware remediation, adjust severity based on business context, suppress duplicate/flapping alerts.

This document compares how all four AI tier options implement the alert-triage scenario using the same skill, tools, and environment. If you're unsure which option to pick, see the [decision tree in ai-tier-options.md](../ai-tier-options.md#recommendation-decision-tree).

## Shared Environment

| Component | Value |
|-----------|-------|
| **Resource group** | `rg-arcbox-itpro` |
| **Alert rules RG** | `rg-opsauto-sc` |
| **Region** | `swedencentral` |
| **Windows VMs** | `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL` |
| **Linux VMs** | `ArcBox-Ubuntu-01`, `ArcBox-Ubuntu-02` |
| **Log Analytics workspace** | `f98fca75-7479-45e5-bf0c-87b56a9f9e8c` |
| **GLPI instance** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **GLPI OAuth creds** | `YOUR_CLIENT_ID` / `YOUR_CLIENT_SECRET` (see [glpi-setup.md](../glpi-setup.md)) |

## Capability Comparison

| Capability | What's Needed | SRE Agent (Option 0) | Agent Framework (Option A) | Foundry Agent (Option B) | Copilot CLI (Option C) |
|---|---|---|---|---|---|
| **Receive alerts automatically** | Ingest Azure Monitor / Defender alerts | ✅ Built-in Azure Monitor integration | Webhook handler (`src/alerting/ingestor.py`) | Webhook trigger (Logic Apps → agent) | ❌ Manual (interactive — user pastes alert) |
| **Correlate multiple alerts** | LLM reasoning over alert set | Skill instructions guide correlation | Skill via `SkillsProvider` context | Agent instructions guide correlation | Skill auto-loads from `.github/skills/` |
| **Look up server context** | CMDB + Arc metadata | Built-in `az CLI` (`RunAzCliReadCommands`) | `FunctionTool` wrapping `az CLI` + GLPI | Function tool wrapping `az CLI` + GLPI | Terminal (`az CLI` + `python glpi_tools.py`) |
| **Create contextualized GLPI ticket** | HTTP API call with enriched description | Custom Python tool (`glpi-create-ticket`) | `FunctionTool` (same GLPI code) | Function tool (same GLPI code) | Terminal (`curl` / Python script) |
| **Auto-remediate (restart service)** | Execute command on server | Built-in Arc Run Command | `FunctionTool` wrapping `az connectedmachine run-command` | Function tool wrapping `az CLI` | Terminal (`az connectedmachine run-command`) |
| **Suppress flapping alerts** | Deduplication + intelligent suppression | ✅ Built-in memory | Custom (Cosmos DB dedup — `AlertIngestor`) | Custom (thread state + Cosmos DB) | ❌ Session-only (no persistence) |
| **Scheduled execution** | Timer trigger for proactive poll | ✅ Built-in | ❌ External (Logic Apps / cron) | ❌ External (Logic Apps / Azure Functions) | ❌ Manual only |

## Skills Reusability

All options reuse the same `sre-skills/` directory. The relevant skill for alert triage is the **`security-agent-troubleshooting`** skill (for Defender-related alerts) and any alert-specific instructions embedded in the system prompt.

| Platform | How the Skill Loads |
|---|---|
| **SRE Agent** | Upload `SKILL.md` via Builder → Skills UI — auto-activates on matching triggers |
| **Agent Framework** | `SkillsProvider(skill_paths=["./sre-skills"])` — auto-discovers and injects on trigger match |
| **Foundry Agent** | `SKILL.md` content injected as agent `instructions` parameter |
| **Copilot CLI** | Copy to `.github/skills/` or `~/.copilot/skills/` — auto-discovers on load |

---

## Option 0: SRE Agent (Recommended)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Monitor                             │
│  Fired Alert ──────────────────────┐                        │
│  (Sev0/Sev1 CPU, Disk, Service)   │                        │
└────────────────────────────────────┼────────────────────────┘
                                     │ auto-trigger
                              ┌──────▼──────────────────────┐
                              │      Azure SRE Agent         │
                              │                              │
                              │  ┌────────────────────────┐  │
                              │  │ security-agent-         │  │
                              │  │ troubleshooting SKILL   │  │
                              │  │ (auto-loaded)           │  │
                              │  └────────────────────────┘  │
                              │                              │
                              │  Tools:                      │
                              │  • RunAzCliReadCommands      │
                              │  • RunAzCliWriteCommands     │
                              │  • glpi-create-ticket        │
                              │  • glpi-query-cmdb           │
                              │                              │
                              │  Memory: ✅ built-in         │
                              └───────┬──────────────────────┘
                                      │
                    ┌─────────────────┬┴────────────────┐
                    ▼                 ▼                  ▼
              Azure Arc         GLPI ITSM          GLPI CMDB
         (Run Commands)     (Create Ticket)    (Server Context)
```

### How Alerts Are Handled

SRE Agent receives alerts automatically via its built-in Azure Monitor integration. When an alert fires, the agent:

1. Receives the alert payload (severity, target resource, description)
2. Auto-activates the matching skill based on trigger keywords
3. Executes the skill's investigation steps
4. Creates a contextualized GLPI ticket

No webhook code required — configure in **Builder → Incident Response → Azure Monitor**:

| Setting | Value |
|---------|-------|
| **Alert source** | Azure Monitor (subscription-scoped) |
| **Filter** | Severity ≤ Sev1 (High + Critical) |
| **Auto-triage** | Enabled — correlate related alerts within 15-min window |
| **Skills** | Auto-selected by trigger match |

### How the `security-agent-troubleshooting` Skill Is Loaded

The skill is uploaded via **Builder → Skills → Upload SKILL.md**. When an alert fires that matches the skill's triggers:

```yaml
# From SKILL.md frontmatter
triggers:
  - Defender for Cloud alert: "Agent health issue detected"
  - Defender device health shows "not reporting" for >30 minutes
  - User reports Defender not working on a server
```

The SRE Agent matches the incoming alert against trigger descriptions and loads the full skill — investigation steps, remediation table, and tool references — into context.

### Example Interaction

> **Azure Monitor Alert → SRE Agent (automatic)**
>
> Alert: "High CPU detected on ArcBox-Win2K22" (Sev1)
> Alert: "Service Sense stopped on ArcBox-Win2K22" (Sev1)
> Alert: "Defender agent not reporting on ArcBox-Win2K22" (Sev0)

**Agent Response:**

> **🔔 Alert Triage — 3 alerts correlated → 1 incident**
>
> **Root Cause:** Defender for Endpoint agent (`Sense` service) stopped on ArcBox-Win2K22, causing missed reporting and CPU spike from recovery attempts.
>
> **Investigation:**
> 1. Queried CMDB: ArcBox-Win2K22 is a Windows Server 2022 (production tier)
> 2. Checked service status via Arc: `Sense` service = Stopped, `MdCoreSvc` = Running
> 3. Checked event logs: Event ID 7036 — Sense service entered Stopped state at 14:32 UTC
> 4. Network connectivity: All Defender endpoints reachable ✅
>
> **Remediation (auto-executed):**
> - Restarted `Sense` service via Arc Run Command → now Running ✅
> - CPU returned to normal (12%) after 3 minutes
>
> **Ticket:** [GLPI #156 — [ALERT] Defender agent stopped on ArcBox-Win2K22 (auto-remediated)](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=156)
>
> **Why 3 alerts → 1 ticket:** All three alerts originated from the same root cause (Sense service failure). Without AI correlation, deterministic mapping would have created 3 separate P1/P2 tickets.

### What Makes SRE Agent Unique

| Feature | SRE Agent | Others |
|---------|-----------|--------|
| **Auto-receives alerts** | ✅ Built-in Azure Monitor integration | ❌ Must build webhook/polling |
| **Alert correlation** | ✅ Time-window grouping + LLM reasoning | ⚠️ Must implement dedup logic |
| **Memory** | ✅ Remembers past alert patterns | ❌ Must implement state |
| **No custom code** | ✅ Portal configuration only | ❌ Python code required |

---

## Option A: Microsoft Agent Framework

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Azure Monitor Alert ──→ Action Group ──→ Webhook            │
└──────────────────────────────────┬───────────────────────────┘
                                   │ HTTP POST
┌──────────────────────────────────▼───────────────────────────┐
│  Your host (Azure Container Apps / local dev)                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         alert_triage_agent.py                            │  │
│  │                                                          │  │
│  │  ┌──────────────┐   ┌──────────────────────────────┐    │  │
│  │  │ SkillsProvider│   │ FunctionTools                 │    │  │
│  │  │ (auto-loads   │   │ ┌──────────────────────────┐ │    │  │
│  │  │  SKILL.md     │   │ │query_fired_alerts        │ │    │  │
│  │  │  from         │   │ │query_arc_server_context   │ │    │  │
│  │  │  sre-skills/) │   │ │query_cmdb_context         │ │    │  │
│  │  └──────────────┘   │ │restart_service_via_arc    │ │    │  │
│  │                      │ │create_glpi_ticket         │ │    │  │
│  │  ┌──────────────┐   │ └──────────────────────────┘ │    │  │
│  │  │ AzureOpenAI  │   └──────────────────────────────┘    │  │
│  │  │ Responses API│                                        │  │
│  │  └──────────────┘                                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐  ┌───────┐  │
│  │  Azure Arc   │  │Log Analytics│  │   GLPI   │  │Cosmos │  │
│  │  (az CLI)    │  │  (az CLI)   │  │ (REST)   │  │DB     │  │
│  └──────────────┘  └─────────────┘  └──────────┘  │(dedup)│  │
│                                                    └───────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Key Code — Alert Handling

```python
"""Alert Triage Agent — Microsoft Agent Framework implementation."""

from agent_framework import FunctionTool, SkillsProvider
from azure.ai.openai import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential

# Auto-load all skills from sre-skills/ (including security-agent-troubleshooting)
skills = SkillsProvider(skill_paths=["./sre-skills"])

# --- Tools ---

@FunctionTool
def query_fired_alerts(hours_back: int = 24) -> dict:
    """Query Azure Monitor for fired alerts in the last N hours."""
    query = f"""
    alertsmanagementresources
    | where type == 'microsoft.alertsmanagement/alerts'
    | where properties.essentials.monitorCondition == 'Fired'
    | where properties.essentials.startDateTime > ago({hours_back}h)
    | project name, severity=properties.essentials.severity,
              target=properties.essentials.targetResource,
              startTime=properties.essentials.startDateTime,
              description=properties.essentials.description
    | order by startTime desc
    """
    return _az(["graph", "query", "-q", query])


@FunctionTool
def query_cmdb_context(server_name: str) -> dict:
    """Look up server in GLPI CMDB for business context (owner, tier, SLA)."""
    import requests
    token = _get_glpi_token()
    resp = requests.get(
        f"{GLPI_BASE}/api.php/v2.2/Assets/Computer",
        params={"filter": f"name=={server_name}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200 and resp.json():
        server = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
        return {"found": True, "name": server.get("name"),
                "comment": server.get("comment"), "ci_id": str(server.get("id"))}
    return {"found": False, "server_name": server_name}


@FunctionTool
def restart_service_via_arc(server_name: str, service_name: str) -> dict:
    """Restart a Windows service on an Arc-enrolled server."""
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"RestartSvc-{service_name}",
        "--location", LOCATION,
        "--script", f"Restart-Service '{service_name}' -Force; Get-Service '{service_name}' | Select Status",
        "--async-execution", "false",
    ])


@FunctionTool
def create_glpi_ticket(title: str, description: str, priority: str = "3") -> dict:
    """Create an incident ticket in GLPI with full diagnostic context."""
    # ... same GLPI OAuth2 flow as sre-tools/python/glpi_tools.py ...


# --- Agent ---

SYSTEM_INSTRUCTIONS = """\
You are an alert triage specialist for the ArcBox for IT Pros environment.

When alerts arrive:
1. Correlate related alerts (same server, same time window, causal chain).
2. Look up server context from CMDB (owner, tier, SLA).
3. Determine root cause using the loaded skill's investigation steps.
4. Auto-remediate if safe (restart service, clear temp files).
5. Create ONE contextualized GLPI ticket per incident (not per alert).
6. Use priority: P1 (critical/outage), P2 (degraded), P3 (warning), P4 (info).

Environment:
  Resource group: rg-arcbox-itpro | Region: swedencentral
  Log Analytics workspace: f98fca75-7479-45e5-bf0c-87b56a9f9e8c
"""

agent = client.as_agent(
    model="gpt-4o",
    name="AlertTriageAgent",
    instructions=SYSTEM_INSTRUCTIONS,
    tools=[query_fired_alerts, query_cmdb_context, restart_service_via_arc,
           create_glpi_ticket],
    context_providers=[skills],  # Auto-loads security-agent-troubleshooting skill
)
```

### How the `security-agent-troubleshooting` Skill Is Loaded

```python
skills = SkillsProvider(skill_paths=["./sre-skills"])
```

At startup, `SkillsProvider` scans all subdirectories for `SKILL.md` files, parses YAML frontmatter, and registers each skill. When the user's query (or incoming alert payload) matches the skill's triggers — e.g., "Defender agent not reporting" — the skill's full investigation procedure is injected into the agent's context automatically.

### Example Interaction

```
Alert Triage Agent (Agent Framework) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Triage the fired alerts from the last 6 hours.

Agent: Let me check the current alerts.

  → Calling query_fired_alerts(hours_back=6)
  → Found 3 fired alerts:
    1. "High CPU on ArcBox-Win2K22" (Sev1, 14:35 UTC)
    2. "Sense service stopped on ArcBox-Win2K22" (Sev1, 14:32 UTC)
    3. "Defender not reporting on ArcBox-Win2K22" (Sev0, 14:45 UTC)

  → Calling query_cmdb_context(server_name="ArcBox-Win2K22")
  → CMDB: Windows Server 2022, Tier: Production, Owner: Infra Team

  → Loading skill: security-agent-troubleshooting (trigger match)

  → Calling restart_service_via_arc(server_name="ArcBox-Win2K22",
      service_name="Sense")
  → Service restarted successfully — Status: Running

  → Calling create_glpi_ticket(
      title="[ALERT] Defender agent failure on ArcBox-Win2K22 (auto-remediated)",
      description="...", priority="2")
  → Created GLPI #157

🔔 **Triage Complete — 3 alerts → 1 incident**

Root cause: Sense service stopped → Defender not reporting → CPU spike
from recovery loop. Service restarted via Arc. All 3 alerts resolved.

Ticket: GLPI #157 (P2) — includes full diagnostic timeline.
```

### What's Different from SRE Agent

| Aspect | SRE Agent | Agent Framework |
|--------|-----------|-----------------|
| **Alert reception** | ✅ Automatic (built-in Azure Monitor) | ⚠️ Must build webhook endpoint + Action Group |
| **Alert dedup** | ✅ Built-in time-window correlation | ⚠️ Must implement (Cosmos DB — see `src/alerting/ingestor.py`) |
| **Skills** | Upload via UI | `SkillsProvider` (identical behavior) |
| **Remediation** | Built-in `RunAzCliWriteCommands` | Custom `FunctionTool` wrapping `az CLI` |
| **Hosting** | Managed (SaaS) | Self-hosted (Container Apps / VM) |
| **Setup effort** | ~1 hour | ~2–3 weeks |

---

## Option B: Foundry Agent Service

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Azure Monitor Alert ──→ Action Group ──→ Logic App          │
└──────────────────────────────────┬───────────────────────────┘
                                   │ HTTP POST
┌──────────────────────────────────▼───────────────────────────┐
│             Azure AI Foundry Project                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         alert-triage-agent                               │  │
│  │                                                          │  │
│  │  ┌──────────────────┐   ┌────────────────────────────┐  │  │
│  │  │ Instructions      │   │ Function Tools              │  │  │
│  │  │ (SKILL.md content │   │ ┌────────────────────────┐ │  │  │
│  │  │  injected as      │   │ │query_fired_alerts      │ │  │  │
│  │  │  system prompt)   │   │ │query_cmdb_context      │ │  │  │
│  │  └──────────────────┘   │ │restart_service_via_arc │ │  │  │
│  │                          │ │create_glpi_ticket      │ │  │  │
│  │  ┌──────────────────┐   │ └────────────────────────┘ │  │  │
│  │  │ Code Interpreter  │   └────────────────────────────┘  │  │
│  │  │ (alert analysis)  │                                    │  │
│  │  └──────────────────┘                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐             │
│  │  Azure Arc   │  │Log Analytics│  │   GLPI   │             │
│  │  (az CLI)    │  │  (az CLI)   │  │ (REST)   │             │
│  └──────────────┘  └─────────────┘  └──────────┘             │
└──────────────────────────────────────────────────────────────┘
```

### Key Code — Alert Handling

```python
"""Alert Triage Agent — Azure AI Foundry implementation."""

from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Load skill content as agent instructions
skill_path = Path("./sre-skills/security-agent-troubleshooting/SKILL.md")
skill_content = skill_path.read_text(encoding="utf-8")

client = AIProjectClient(
    endpoint=FOUNDRY_ENDPOINT,
    credential=DefaultAzureCredential(),
)

# Define function tools (same az CLI wrappers as Agent Framework)
tools = [
    {"type": "function", "function": {
        "name": "query_fired_alerts",
        "description": "Query Azure Monitor for fired alerts",
        "parameters": {"type": "object", "properties": {
            "hours_back": {"type": "integer", "default": 24}
        }}
    }},
    {"type": "function", "function": {
        "name": "query_cmdb_context",
        "description": "Look up server in GLPI CMDB",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "restart_service_via_arc",
        "description": "Restart a Windows service on an Arc server",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"},
            "service_name": {"type": "string"}
        }, "required": ["server_name", "service_name"]}
    }},
    {"type": "function", "function": {
        "name": "create_glpi_ticket",
        "description": "Create an incident ticket in GLPI",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "default": "3"}
        }, "required": ["title", "description"]}
    }},
    {"type": "code_interpreter"},
]

# Create agent with SKILL.md as instructions
agent = client.agents.create(
    name="alert-triage-agent",
    instructions=f"""\
You are an alert triage specialist. Correlate alerts, determine root cause,
auto-remediate when safe, and create one GLPI ticket per incident.

Environment: rg-arcbox-itpro, swedencentral
Log Analytics: f98fca75-7479-45e5-bf0c-87b56a9f9e8c

{skill_content}
""",
    tools=tools,
    model="gpt-4o",
)
```

### How the `security-agent-troubleshooting` Skill Is Loaded

Foundry Agent Service does not have a `SkillsProvider`. Instead, the SKILL.md content is read from disk and injected directly into the agent's `instructions` parameter:

```python
skill_content = Path("./sre-skills/security-agent-troubleshooting/SKILL.md").read_text()
agent = client.agents.create(
    instructions=f"You are an alert triage specialist.\n\n{skill_content}",
    ...
)
```

**Trade-off:** No automatic skill routing — the full skill is always loaded. For multi-skill scenarios, either concatenate multiple SKILL.md files or create separate agents per skill.

### Example Interaction

```
Alert Triage Agent (Foundry) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: I received 3 alerts for ArcBox-Win2K22 — high CPU, Defender not
     reporting, and Sense service stopped. Triage them.

Agent: I'll correlate these alerts and investigate.

  → query_fired_alerts(hours_back=1) — confirmed 3 active alerts
  → query_cmdb_context("ArcBox-Win2K22") — Production, Infra Team
  → [Code Interpreter] Timeline analysis:
      14:32 — Sense stopped (root cause)
      14:35 — CPU spike (symptom — recovery loop)
      14:45 — Defender not reporting (consequence)

  → restart_service_via_arc("ArcBox-Win2K22", "Sense") — ✅ Running
  → create_glpi_ticket(
      title="[ALERT] Defender agent failure on ArcBox-Win2K22",
      priority="2") — ✅ GLPI #158

🔔 Triage Complete

These 3 alerts share a single root cause: the Sense service stopped at
14:32, causing a CPU spike from the recovery loop and a Defender
reporting gap. I restarted the service — it's now active. One P2 ticket
created with the full timeline.
```

### What's Different from SRE Agent

| Aspect | SRE Agent | Foundry Agent |
|--------|-----------|---------------|
| **Alert reception** | ✅ Automatic | ❌ Must build Logic App → webhook trigger |
| **Skills** | Upload via UI (auto-route) | Inject as `instructions` (no auto-routing) |
| **Code Interpreter** | ✅ Built-in | ✅ Built-in (timeline analysis, pattern detection) |
| **Multi-skill** | ✅ Auto-routes by trigger | ❌ One skill per agent or concatenate |
| **Memory** | ✅ Cross-session | ⚠️ Thread-scoped (within conversation) |
| **Hosting** | Managed (SaaS) | Managed (Foundry platform) |
| **Setup effort** | ~1 hour | ~1–2 weeks |

---

## Option C: GitHub Copilot CLI

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Engineer's Terminal                                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         GitHub Copilot CLI                               │  │
│  │                                                          │  │
│  │  ┌──────────────────┐   ┌────────────────────────────┐  │  │
│  │  │ .github/skills/   │   │ Terminal Tools (native)     │  │  │
│  │  │ security-agent-   │   │ ┌────────────────────────┐ │  │  │
│  │  │ troubleshooting/  │   │ │az graph query          │ │  │  │
│  │  │ SKILL.md          │   │ │az monitor log-analytics│ │  │  │
│  │  │ (auto-loaded)     │   │ │az connectedmachine     │ │  │  │
│  │  └──────────────────┘   │ │python glpi_tools.py    │ │  │  │
│  │                          │ │curl (GLPI REST API)    │ │  │  │
│  │  ┌──────────────────┐   │ └────────────────────────┘ │  │  │
│  │  │ MCP Servers       │   └────────────────────────────┘  │  │
│  │  │ (optional GLPI)   │                                    │  │
│  │  └──────────────────┘                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  az CLI authenticated ──→ Azure Arc, Log Analytics, Defender  │
└──────────────────────────────────────────────────────────────┘

NOTE: No automatic alert reception — engineer sees alert in
      Azure Portal / email / Teams and brings context to Copilot.
```

### Key Code — Skill Setup

No agent code to write. Copy the skill and use `az CLI` directly:

```bash
# Copy skills to project directory
cp -r sre-skills/* .github/skills/

# Verify skills are loaded
# In Copilot CLI:
/skills list
# → security-agent-troubleshooting  v1.0.0
# → wintel-health-check-investigation  v1.0.0
# → patch-validation  v1.0.0
# → compliance-investigation  v1.0.0
# → vmware-bau-operations  v1.0.0
```

### How the `security-agent-troubleshooting` Skill Is Loaded

Copilot CLI natively supports AgentSkills.io. When skills are placed in `.github/skills/` or `~/.copilot/skills/`, they are auto-discovered at session start:

```
.github/skills/
└── security-agent-troubleshooting/
    └── SKILL.md    ← auto-loaded when query matches triggers
```

When you ask about alert triage or Defender issues, Copilot matches your query against the skill's triggers and loads the investigation procedure into context — the same mechanism as SRE Agent, with zero code.

### Example Interaction

```
> I just got 3 alerts on ArcBox-Win2K22: high CPU (Sev1),
  Sense service stopped (Sev1), and Defender not reporting (Sev0).
  Help me triage.

Copilot: I'll investigate using the security-agent-troubleshooting skill.
Let me check the current state.

[Running] az graph query -q "alertsmanagementresources
  | where type == 'microsoft.alertsmanagement/alerts'
  | where properties.essentials.monitorCondition == 'Fired'
  | where properties.essentials.targetResource contains 'ArcBox-Win2K22'
  | project name, properties.essentials.severity,
    properties.essentials.startDateTime"

Found 3 active alerts. Let me check service status on the server.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "CheckDefenderServices" \
  --location swedencentral \
  --script "Get-Service Sense, MdCoreSvc | Select Name, Status | ConvertTo-Json"

Results: Sense = Stopped, MdCoreSvc = Running.

Based on the skill's investigation steps, the root cause is the Sense
service failure. Let me restart it.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "RestartSense" \
  --location swedencentral \
  --script "Restart-Service Sense -Force; Start-Sleep 5; Get-Service Sense | Select Status"

✅ Sense service restarted — Status: Running

Now let me create a GLPI ticket for the audit trail.

[Running] python sre-tools/python/glpi_tools.py \
  --title "[ALERT] Defender agent failure on ArcBox-Win2K22 (remediated)" \
  --description "3 correlated alerts... Sense restarted via Arc." \
  --priority 2

✅ Created GLPI ticket #159

**Summary:** 3 alerts → 1 root cause (Sense service stopped).
Auto-remediated by restarting the service. GLPI #159 created.
```

### What's Different from SRE Agent

> **💡 Tip:** Install the [Azure Skills Plugin](https://github.com/microsoft/azure-skills) for additional Azure diagnostics, observability, and compliance capabilities. The plugin provides 20 Azure skills + 200+ MCP tools that complement our custom Wintel ops skills. For example, `azure-diagnostics` can help correlate alert signals from AppLens, and `azure-observability` can query Log Analytics directly. Our custom skills remain essential for Arc Run Commands, Defender-specific troubleshooting, and GLPI integration.

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Alert reception** | ✅ Automatic | ❌ Manual (engineer initiates) |
| **Skills** | Upload via UI | Copy to `.github/skills/` (identical content) |
| **Tool execution** | Built-in `RunAzCliWriteCommands` | Direct terminal (`az CLI`, Python, curl) |
| **Code required** | None | None (uses existing `az CLI` + scripts) |
| **Scheduling** | ✅ Built-in | ❌ Interactive only |
| **Memory** | ✅ Cross-session | ⚠️ Session-only (use custom instructions for persistence) |
| **Best for** | 24/7 automated triage | Ad-hoc investigation by engineers |
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify az CLI) |

---

## Summary Comparison

| Dimension | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|-----------|-----------|-----------------|---------------|-------------|
| **Setup effort** | ~1 hour | ~2–3 weeks | ~1–2 weeks | ~1 day |
| **Alert reception** | ✅ Automatic | ⚠️ Build webhook | ⚠️ Build trigger | ❌ Manual |
| **Alert correlation** | ✅ Built-in | ⚠️ Custom logic | ⚠️ LLM reasoning | ⚠️ LLM reasoning |
| **Skills** | Upload UI | `SkillsProvider` | Inject instructions | `.github/skills/` |
| **Auto-remediation** | ✅ Built-in | ✅ FunctionTool | ✅ Function tool | ✅ Terminal cmd |
| **GLPI tickets** | Python tool | `FunctionTool` | Function tool | Terminal / script |
| **Memory** | ✅ Built-in | ⚠️ Custom (Cosmos) | ⚠️ Thread-scoped | ❌ Session-only |
| **Scheduling** | ✅ Built-in | ❌ External | ❌ External | ❌ None |
| **Hosting** | Managed SaaS | Self-hosted | Managed Foundry | Local terminal |
| **Best for** | 24/7 ops teams | Full customization | Foundry-native teams | Terminal engineers |

## See Also

- [Scenario A — Health Check implementations](scenario-a-health-check/README.md) — same pattern, different scenario
- [Scenario C — Security Agent Troubleshooting](scenario-c-security-troubleshooting.md) — related diagnostic scenario
- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [Alert monitoring demo script](../../scripts/demo-alert-monitoring.ps1) — the deterministic 70% automation
- [`sre-skills/security-agent-troubleshooting/SKILL.md`](../../sre-skills/security-agent-troubleshooting/SKILL.md) — skill definition
- [`src/alerting/ingestor.py`](../../src/alerting/ingestor.py) — Python alert ingestion (used by Agent Framework option)

