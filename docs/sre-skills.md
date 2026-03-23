# SRE Agent Skills

## Overview

Every SOP documented in Phase 1 is codified as an [Azure SRE Agent Skill](https://learn.microsoft.com/en-us/azure/sre-agent/skills) using the open-source [AgentSkills.io](https://agentskills.io/specification) format. Skills are loaded **automatically** by SRE Agent when the context matches — no explicit invocation needed.

## Skill Structure

Each skill is a directory containing:

```
skill-name/
├── SKILL.md         # Required: YAML frontmatter + procedural Markdown
├── scripts/         # Optional: PowerShell, Python scripts the skill can execute
└── references/      # Optional: Thresholds, known issues, escalation matrices
```

## Skills Inventory

| Skill | SOP Source | Purpose | Key Tools |
|---|---|---|---|
| `wintel-health-check-investigation` | daily-health-check.md | Investigate health check failures/warnings | Arc Run Cmd, KQL perf trends |
| `security-agent-troubleshooting` | security-agent-troubleshooting.md | Diagnose and remediate Defender agent issues | Defender API, Arc Run Cmd |
| `patch-validation` | windows-patching.md | Pre/post patch validation and rollback decisions | Update Manager, Arc Run Cmd |
| `compliance-investigation` | compliance-reporting.md | Investigate non-compliant servers from Defender | Resource Graph, Defender API |
| `vmware-bau-operations` | vmware-bau.md | Snapshot cleanup, resource monitoring, VM health | Arc Run Cmd |

## Custom Tools

### Kusto Tools (KQL)

| Tool | Purpose |
|---|---|
| `query-perf-trends` | CPU/memory/disk trends over N days from Log Analytics |
| `query-security-alerts` | Defender for Cloud security alerts by server/severity |
| `query-compliance-state` | Regulatory compliance status from Resource Graph |
| `query-update-compliance` | Missing patches by server/classification |

### Python Tools

| Tool | Purpose |
|---|---|
| `glpi-create-ticket` | Create incident in GLPI (or ManageEngine in production) |
| `glpi-query-cmdb` | Query CMDB for server CI record (owner, role, environment) |
| `generate-compliance-report` | Generate HTML/PDF compliance report from Defender data |
| `cosmos-query-runs` | Query Cosmos DB for automation run history |
| `cosmos-check-memories` | Check active memory/suppression rules for a server+task |

### MCP Server Integrations

| MCP Server | Provides |
|---|---|
| GLPI MCP Server | Ticket CRUD, CMDB queries, SLA status |
| Operations Portal MCP | Run history, memory management |

## SOP → Skill Mapping

```
Phase 1 SOPs                    SRE Agent Skills
─────────────                   ────────────────
docs/sops/
  daily-health-check.md    →   sre-skills/wintel-health-check-investigation/SKILL.md
  security-agent-             → sre-skills/security-agent-troubleshooting/SKILL.md
    troubleshooting.md
  windows-patching.md       →   sre-skills/patch-validation/SKILL.md
  compliance-reporting.md   →   sre-skills/compliance-investigation/SKILL.md
  vmware-bau.md             →   sre-skills/vmware-bau-operations/SKILL.md
```

The SOP document is the source of truth. The skill is the executable version. When the SOP updates, the skill updates.
