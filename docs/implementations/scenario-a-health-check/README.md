# Scenario A: Health Check — Implementation Guide

This directory contains complete, runnable implementations of **Scenario A (Daily Health Check)** across all four AI tier options. Each implementation performs the same task — check the health of Arc-enrolled servers, interpret results, project trends, and create tickets — using a different AI platform.

> **Start here:** If you're unsure which option to pick, see the [decision tree in ai-tier-options.md](../../ai-tier-options.md#recommendation-decision-tree).

## Quick Links

| Option | Guide | Code | Effort |
|--------|-------|------|--------|
| **Option 0 — SRE Agent** (recommended) | [option-0-sre-agent.md](option-0-sre-agent.md) | N/A (no-code) | ~1 hour |
| **Option A — Agent Framework** | [option-a-agent-framework.md](option-a-agent-framework.md) | [agent-framework/](agent-framework/) | ~2–3 weeks |
| **Option B — Foundry Agent Service** | [option-b-foundry-agent.md](option-b-foundry-agent.md) | [foundry-agent/](foundry-agent/) | ~1–2 weeks |
| **Option C — Copilot CLI** | [option-c-copilot-cli.md](option-c-copilot-cli.md) | N/A (interactive) | ~1 day |

## Capability Comparison

How each option implements the core health-check capabilities:

| Capability | What's Needed | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|---|
| **Run health checks on Arc servers** | Execute PowerShell remotely | Built-in (`az CLI` via RunAzCliReadCommands) | Custom tool (`subprocess` / Azure SDK) | Function calling (`az CLI` wrapper) | Terminal (`az CLI` directly) |
| **Query Log Analytics for trends** | KQL query execution | Built-in (`az monitor log-analytics query`) | Custom `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az CLI` directly) |
| **Interpret results + find anomalies** | LLM reasoning | Skill auto-loads from `SKILL.md` | Agent with `SkillsProvider` context | Agent instructions (from `SKILL.md`) | Skill auto-loads from `.github/skills/` |
| **Project disk trend (5-day forecast)** | Data analysis + extrapolation | Built-in code interpreter | Code interpreter tool | Code interpreter tool | Terminal (Python / inline analysis) |
| **Correlate across servers** | Multi-server pattern matching | Skill instructions guide correlation | Skill instructions via `SkillsProvider` | Agent instructions guide correlation | Skill instructions guide correlation |
| **Generate NL summary** | LLM output formatting | Built-in (agent response) | Agent response | Agent response | Chat response |
| **Create GLPI ticket for critical** | HTTP API call | Custom Python tool (`glpi-create-ticket`) | `FunctionTool` (same GLPI code) | Function tool (same GLPI code) | Terminal (`curl` / Python script) |
| **Scheduled execution** | Timer / cron trigger | ✅ Built-in scheduled task (every 6 h) | ❌ External scheduler needed (Logic Apps / cron) | ❌ External trigger needed (Logic Apps / webhook) | ❌ Manual only (interactive) |

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
| **GLPI OAuth creds** | `YOUR_CLIENT_ID` / `YOUR_CLIENT_SECRET` (see [glpi-setup.md](../../glpi-setup.md)) |

## Skills Reusability

All options reuse the **same** `sre-skills/wintel-health-check-investigation/SKILL.md` — the investigation procedure, thresholds, escalation matrix, and tool references are identical. The only difference is *how* each platform loads the skill:

| Platform | How Skills Load |
|---|---|
| **SRE Agent** | Upload `SKILL.md` via Builder → Skills UI |
| **Agent Framework** | `SkillsProvider(skill_paths=["./sre-skills"])` — auto-discovers all skills |
| **Foundry Agent** | `SKILL.md` content injected as agent `instructions` parameter |
| **Copilot CLI** | Copy to `.github/skills/` or `~/.copilot/skills/` — auto-discovers on load |

## Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │         Shared Infrastructure                │
                    │                                             │
                    │  Azure Arc ── Log Analytics ── GLPI ITSM    │
                    │       │              │              │        │
                    │  Arc Run Cmd    KQL queries    REST API      │
                    └───────┬──────────────┬──────────────┬────────┘
                            │              │              │
            ┌───────────────┼──────────────┼──────────────┼──────────────┐
            │               │              │              │              │
     ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────┐       │
     │  SRE Agent  │ │   Agent     │ │  Foundry   │ │ Copilot  │       │
     │  (Option 0) │ │  Framework  │ │  Agent     │ │   CLI    │       │
     │             │ │  (Option A) │ │  (Option B)│ │(Option C)│       │
     │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌────────┐ │ │ ┌──────┐ │       │
     │ │SKILL.md │ │ │ │Skills   │ │ │ │Agent   │ │ │ │SKILL │ │       │
     │ │(upload) │ │ │ │Provider │ │ │ │instruct│ │ │ │.md   │ │       │
     │ └─────────┘ │ │ └─────────┘ │ │ └────────┘ │ │ └──────┘ │       │
     └─────────────┘ └─────────────┘ └────────────┘ └──────────┘       │
            │               │              │              │              │
            └───────────────┴──────────────┴──────────────┘              │
                            │                                            │
                    ┌───────▼────────┐                                   │
                    │  Same SKILL.md │                                   │
                    │  Same tools    │                                   │
                    │  Same SOPs     │                                   │
                    └────────────────┘                                   │
            ────────────────────────────────────────────────────────────
```

## See Also

- [Scenario A demo walkthrough](../../demos/scenario-a-health-check.md) — full demo with expected output
- [AI tier options comparison](../../ai-tier-options.md) — cross-scenario platform comparison
- [SRE Agent setup guide](../../sre-agent-setup.md) — complete SRE Agent deployment
- [SKILL.md source](../../../sre-skills/wintel-health-check-investigation/SKILL.md) — the health-check investigation skill
