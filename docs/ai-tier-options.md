# AI Tier Options — Alternatives to Azure SRE Agent

## Overview

Our solution uses a 2-tier architecture:
- **Tier 1: PowerShell Scripts** — deterministic automation (70-95% of work)
- **Tier 2: AI Agent** — reasoning, correlation, diagnostics (5-30% of work)

**Azure SRE Agent** is the recommended Tier 2 option. However, if SRE Agent is unavailable (regional availability, licensing, organizational constraints), three alternatives can deliver the same AI capabilities. All options require **Azure Arc** as the hybrid bridge to on-prem servers.

## Comparison Matrix

| Capability | SRE Agent (Recommended) | Microsoft Agent Framework | Foundry Agent Service | GitHub Copilot Extensions |
|---|---|---|---|---|
| **Deployment** | SaaS (sre.azure.com) | Self-hosted (code) | SaaS (ai.azure.com) | SaaS (github.com) |
| **Development effort** | Low (no-code builder) | High (Python/C# code) | Medium (SDK + portal) | Medium (API + extensions) |
| **AgentSkills.io support** | ✅ Native | ✅ Native (`SkillsProvider`) | ⚠️ Via Agent Framework SDK | ❌ Custom integration |
| **MCP tool support** | ✅ Native | ✅ Native | ✅ Native (hosted MCP) | ⚠️ Limited |
| **Azure Arc integration** | ✅ Built-in (managed identity) | ⚠️ Custom (az CLI / SDK) | ⚠️ Custom (function calling) | ⚠️ Custom (API calls) |
| **Incident auto-response** | ✅ Built-in (Azure Monitor, ServiceNow, PagerDuty) | ❌ Build custom | ❌ Build custom | ❌ Not applicable |
| **Memory / learning** | ✅ Built-in | ⚠️ Custom (session state) | ⚠️ Custom (thread history) | ❌ No persistence |
| **Scheduled tasks** | ✅ Built-in | ❌ Need external scheduler | ❌ Need external trigger | ❌ Not applicable |
| **Regional availability** | Limited (check sre.azure.com) | Any Azure region (self-hosted) | Most Azure regions | Global |
| **Cost model** | Azure Agent Units (AAUs) | Compute + LLM API costs | Per-agent + LLM costs | Copilot license |
| **Best for** | Ops teams wanting turnkey SRE automation | Teams needing full customization | Teams already on Foundry platform | Developer-centric teams |

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

#### Option C: GitHub Copilot Extensions

**Skills:** ❌ **Not directly reusable** — Copilot Extensions use a different model (API endpoints, not AgentSkills.io). However, the SKILL.md **content** (procedures, steps) can be converted into Copilot Extension responses.

**Tools:** ⚠️ **Partially reusable** — Build a Copilot Extension API that calls our Python tools internally:

```
GitHub Copilot → Copilot Extension API → glpi_tools.py / az CLI
```

**Azure Arc access:** The extension API server would need Azure credentials to call Arc APIs.

**What you need to build:**
- Copilot Extension API server (significant effort)
- OAuth flow for GitHub → Azure authentication
- Convert all skills to API response logic
- No incident auto-response (Copilot is pull-based, not push-based)

**Best for:** Teams that primarily work in GitHub and want AI assistance during code review, PR investigation, or ad-hoc queries — NOT for automated incident response.

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
          └── NO → Are you already on Azure AI Foundry?
                    ├── YES → Use Foundry Agent Service (Option B)
                    │         Good skills reuse, managed hosting
                    │         Effort: ~1-2 weeks to convert skills + build tools
                    │
                    └── NO → Is the team developer-centric (GitHub-first)?
                              ├── YES → Use GitHub Copilot Extensions (Option C)
                              │         Pull-based only, significant build effort
                              │         Effort: ~3-4 weeks
                              │
                              └── NO → Use Agent Framework (Option A)
                                        Best balance of flexibility and portability
```

## Migration Effort Summary

| From SRE Agent To | Skills | Tools | Arc Integration | Incident Response | Total Effort |
|---|---|---|---|---|---|
| **Agent Framework** | Copy as-is | Wrap as FunctionTool | Build SDK wrapper | Build webhook handler | ~2-3 weeks |
| **Foundry Agent Service** | Convert to instructions | Convert to function defs | Build function tools | Build trigger | ~1-2 weeks |
| **GitHub Copilot Extension** | Rewrite as API | Build API server | Build auth flow | Not supported | ~3-4 weeks |

## Key Principle: Skills Are the Portable Asset

The **AgentSkills.io format** is the interoperability layer. Our 5 SKILL.md files contain:
- Domain expertise (SOPs codified as procedures)
- Step-by-step investigation flows
- Tool references and execution patterns
- Escalation criteria and remediation guidance

This knowledge is **platform-independent**. Whether the runtime is SRE Agent, Agent Framework, Foundry, or a future platform — the skills carry the operational intelligence.

**Invest in skills quality, not platform lock-in.**
