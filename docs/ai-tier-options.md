# AI Tier Options — Alternatives to Azure SRE Agent

## Overview

Our solution uses a 2-tier architecture:
- **Tier 1: PowerShell Scripts** — deterministic automation (70-95% of work)
- **Tier 2: AI Agent** — reasoning, correlation, diagnostics (5-30% of work)

**Azure SRE Agent** is the recommended Tier 2 option. However, if SRE Agent is unavailable (regional availability, licensing, organizational constraints), three alternatives can deliver the same AI capabilities. All options require **Azure Arc** as the hybrid bridge to on-prem servers.

All options support our skills because **AgentSkills.io is an open standard** supported by SRE Agent, Microsoft Agent Framework, AND GitHub Copilot CLI natively.

## Comparison Matrix

| Capability | SRE Agent (Recommended) | Microsoft Agent Framework | Foundry Agent Service | GitHub Copilot CLI |
|---|---|---|---|---|
| **Deployment** | SaaS (sre.azure.com) | Self-hosted (code) | SaaS (ai.azure.com) | Local CLI + cloud models |
| **Development effort** | Low (no-code builder) | High (Python/C# code) | Medium (SDK + portal) | Low (drop SKILL.md files) |
| **AgentSkills.io support** | ✅ Native | ✅ Native (`SkillsProvider`) | ⚠️ Via Agent Framework SDK | ✅ Native (`.github/skills/` or `~/.copilot/skills/`) |
| **MCP tool support** | ✅ Native | ✅ Native | ✅ Native (hosted MCP) | ✅ Native (MCP servers) |
| **Azure Arc integration** | ✅ Built-in (managed identity) | ⚠️ Custom (az CLI / SDK) | ⚠️ Custom (function calling) | ✅ Via CLI tools (az CLI available in terminal) |
| **Incident auto-response** | ✅ Built-in (Azure Monitor, ServiceNow, PagerDuty) | ❌ Build custom | ❌ Build custom | ❌ Interactive only (no auto-trigger) |
| **Memory / learning** | ✅ Built-in | ⚠️ Custom (session state) | ⚠️ Custom (thread history) | ⚠️ Session-based (plan.md, custom instructions) |
| **Scheduled tasks** | ✅ Built-in | ❌ Need external scheduler | ❌ Need external trigger | ❌ Interactive only |
| **Script execution** | ✅ Built-in (runbooks) | ✅ Custom tools | ⚠️ Code interpreter | ✅ Native (runs PowerShell, Python, bash directly) |
| **Regional availability** | Limited (check sre.azure.com) | Any Azure region (self-hosted) | Most Azure regions | Global (runs locally) |
| **Cost model** | Azure Agent Units (AAUs) | Compute + LLM API costs | Per-agent + LLM costs | Copilot license ($19-39/user/month) |
| **Best for** | Ops teams wanting turnkey SRE automation | Teams needing full customization | Teams already on Foundry platform | Engineers who work in the terminal |

## Skills & Tools Reusability

### What We Built for SRE Agent

```
sre-skills/                          # AgentSkills.io format
├── wintel-health-check-investigation/SKILL.md
├── security-agent-troubleshooting/SKILL.md
├── patch-validation/SKILL.md
├── compliance-investigation/SKILL.md
└── vmware-bau-operations/SKILL.md

sre-tools/
├── kusto/*.kql                      # KQL reference queries
└── python/glpi_tools.py             # GLPI ITSM/CMDB integration
```

### How Each Alternative Reuses These Assets

#### Option A: Microsoft Agent Framework (Best portability)

**Skills:** ✅ **100% reusable** — Agent Framework natively supports AgentSkills.io via `SkillsProvider`:

```python
from agent_framework import SkillsProvider

skills_provider = SkillsProvider(
    skill_paths=["./sre-skills"]  # Points to our existing skills directory
)

agent = client.as_agent(
    name="WintelOpsAgent",
    instructions="You are a Wintel operations specialist...",
    context_providers=[skills_provider],
)
```

The agent automatically discovers all 5 SKILL.md files and uses them when context matches — identical behavior to SRE Agent.

**Tools:** ✅ **Reusable with adapter** — Convert our Python tools to Agent Framework function tools:

```python
from agent_framework import FunctionTool

# Our existing glpi_tools.py main() functions become function tools
@FunctionTool
def glpi_create_ticket(title: str, description: str, priority: str = "3") -> dict:
    # ... same code as sre-tools/python/glpi_tools.py
```

**Azure Arc access:** Custom — use `azure-mgmt-hybridcompute` SDK or `subprocess` with `az CLI`:

```python
@FunctionTool  
def arc_run_command(machine_name: str, script: str) -> dict:
    """Execute a command on an Arc-enrolled server."""
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.hybridcompute import HybridComputeManagementClient
    # ... invoke run command via SDK
```

**What you need to build:**
- Hosting (Azure Container Apps or App Service)
- Incident trigger integration (webhook from Azure Monitor)
- Memory/state management (Cosmos DB or file-based)
- Scheduling (Azure Logic Apps or cron)

#### Option B: Foundry Agent Service

**Skills:** ⚠️ **Partially reusable** — Foundry uses its own agent definition format, but can load AgentSkills.io via the Agent Framework SDK:

```python
# Foundry agent with Agent Framework skills
from agent_framework import SkillsProvider
from azure.ai.projects import AIProjectClient

skills = SkillsProvider(skill_paths=["./sre-skills"])
# Inject skill context into Foundry agent instructions
```

Alternatively, convert SKILL.md content into Foundry agent instructions (system prompt):

```json
{
  "name": "wintel-health-check-agent",
  "instructions": "... paste SKILL.md content here ...",
  "tools": [
    {"type": "function", "function": {"name": "glpi_create_ticket", ...}},
    {"type": "code_interpreter"}
  ]
}
```

**Tools:** ✅ **Reusable** — Our Python tools become Foundry function-calling tools:
- `glpi_tools.py` → Foundry function definitions (same `main()` pattern)
- KQL queries → Code Interpreter or function tools wrapping `az CLI`

**Azure Arc access:** Via function calling — define tools that invoke Arc APIs.

**What you need to build:**
- Foundry project + agent deployment
- Function definitions for Arc operations
- Trigger mechanism (webhook or scheduled)
- Convert SKILL.md → agent instructions

#### Option C: GitHub Copilot CLI

**Skills:** ✅ **100% reusable** — Copilot CLI natively supports AgentSkills.io. Just copy our skills to the project or user skills directory:

```bash
# Project skills (specific to this repo)
cp -r sre-skills/* .github/skills/

# Or personal skills (available across all projects)
cp -r sre-skills/* ~/.copilot/skills/
```

That's it. Copilot CLI auto-discovers SKILL.md files and loads them when context matches. Verify:

```
/skills list
```

You should see all 5 skills: `wintel-health-check-investigation`, `security-agent-troubleshooting`, etc.

**Tools:** ✅ **Natively available** — Copilot CLI runs in the terminal with full access to:
- `az CLI` (Azure Arc, Defender, Resource Graph, Update Manager — all available)
- PowerShell / bash scripts (our `scripts/demo-*.ps1` work directly)
- Python scripts (our `sre-tools/python/glpi_tools.py` can be invoked)
- MCP servers (connect GLPI or custom tools via MCP)

No tool conversion needed — Copilot CLI executes commands directly in the shell.

**Azure Arc access:** ✅ **Direct** — Copilot CLI runs in your terminal where `az CLI` is authenticated:

```
Ask Copilot: "Check the health of ArcBox-Win2K22"
→ Copilot loads wintel-health-check-investigation skill
→ Runs: az monitor log-analytics query --workspace f98fca75... --analytics-query "Perf | where Computer == 'ArcBox-Win2K22'..."
→ Interprets results using skill instructions
```

**Example interaction:**

```
> Use the /compliance-investigation skill to check compliance on my Arc servers

Copilot: I'll check compliance using Defender for Cloud and Azure Policy.

[Running] az security regulatory-compliance-standards list -o json
[Running] az policy state summarize --resource-group rg-arcbox-itpro

Based on the results:
- CIS compliance: 78% (22% failing)
- Azure Policy: 3 non-compliant resources
- Top failing control: "Ensure Windows Firewall is enabled" (4 servers)
- Recommendation: Priority fix for firewall settings on ArcBox-Win2K22 and ArcBox-Win2K25

Shall I create a GLPI ticket for remediation?
```

**What you need to build:**
- Nothing — just copy skills to `.github/skills/` or `~/.copilot/skills/`
- Ensure `az CLI` is authenticated in the terminal
- Optionally: connect MCP servers for GLPI integration

**Limitations:**
- **Interactive only** — no automated incident response (user must ask)
- **No scheduled tasks** — runs on-demand, not proactively
- **Session memory only** — knowledge doesn't persist across sessions (use custom instructions for persistent context)
- **Best as complement, not replacement** — great for ad-hoc investigation alongside SRE Agent or scripts

## Recommendation Decision Tree

```
Is Azure SRE Agent available in your region?
├── YES → Use SRE Agent (Option 0 — recommended)
│         Lowest effort, built-in incident response, native skills support
│
└── NO → Do you need automated incident response (24/7 auto-triage)?
          ├── YES → Use Agent Framework (Option A)
          │         Self-host in any region, full skills reuse, most flexible
          │         Effort: ~2-3 weeks to build hosting + triggers + memory
          │
          └── NO → Do engineers work primarily in the terminal?
                    ├── YES → Use GitHub Copilot CLI (Option C)
                    │         Zero build effort — copy skills, use az CLI directly
                    │         Interactive only, no auto-response
                    │         Effort: ~1 day (copy skills + verify)
                    │
                    └── NO → Are you already on Azure AI Foundry?
                              ├── YES → Use Foundry Agent Service (Option B)
                              │         Good skills reuse, managed hosting
                              │         Effort: ~1-2 weeks to convert skills + build tools
                              │
                              └── NO → Use Copilot CLI (Option C) + scripts
                                        Lowest barrier, add Agent Framework later if needed
```

## Migration Effort Summary

| From SRE Agent To | Skills | Tools | Arc Integration | Incident Response | Total Effort |
|---|---|---|---|---|---|
| **Agent Framework** | Copy as-is | Wrap as FunctionTool | Build SDK wrapper | Build webhook handler | ~2-3 weeks |
| **Foundry Agent Service** | Convert to instructions | Convert to function defs | Build function tools | Build trigger | ~1-2 weeks |
| **GitHub Copilot CLI** | Copy to `.github/skills/` | Already available (az CLI) | Already available (terminal) | Not supported (interactive) | **~1 day** |

## Key Principle: Skills Are the Portable Asset

The **AgentSkills.io format** is the interoperability layer. Our 5 SKILL.md files contain:
- Domain expertise (SOPs codified as procedures)
- Step-by-step investigation flows
- Tool references and execution patterns
- Escalation criteria and remediation guidance

This knowledge is **platform-independent**. All three alternatives plus SRE Agent support AgentSkills.io natively or with minimal adaptation:

| Platform | Skills Support | How |
|---|---|---|
| **Azure SRE Agent** | ✅ Native | Upload via Builder UI |
| **Agent Framework** | ✅ Native | `SkillsProvider(skill_paths=["./sre-skills"])` |
| **GitHub Copilot CLI** | ✅ Native | Copy to `.github/skills/` or `~/.copilot/skills/` |
| **Foundry Agent Service** | ⚠️ Convert | Paste SKILL.md content into agent instructions |

**Invest in skills quality, not platform lock-in.**
