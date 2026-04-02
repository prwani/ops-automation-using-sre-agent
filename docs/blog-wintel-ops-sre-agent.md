# Automating Windows Server Operations with AI Agents: An Automation-First Approach

> **How this blog is different from existing coverage:**
>
> Three TechCommunity blogs already cover Azure SRE Agent:
> - *"Announcing GA for Azure SRE Agent"* (March 2026) — GA announcement, Microsoft's internal results (1300 agents, 35K incidents, 20K hours saved)
> - *"Reimagining AI Ops with Azure SRE Agent"* (Nov 2025) — sub-agent builder, MCP connectors, prebuilt scenarios
> - *"What's New in GA Release"* (March 2026) — redesigned onboarding, deep context, ecosystem integrations
>
> **What this blog adds:** A real-world, end-to-end implementation for Windows Server / VMware / Security operations (sometimes called "Wintel" in enterprise IT) — with quantified automation coverage, 6 Agent Skills built from actual SOPs, a closed-loop ITSM integration, and a working demo environment you can deploy today. We show two delivery options (Azure SRE Agent and GitHub Copilot CLI) and lead with automation, not AI.

## The Problem

Windows Server operations teams spend 15+ hours per week on manual health checks (30–45 min × 4/day), compliance reports (1 hr/day), alert monitoring (24/7), monthly patching (~9 hrs), and CMDB updates (~2 hrs/month). These tasks are repetitive, largely scriptable, and almost entirely undocumented — the procedures live in people's heads. When someone goes on leave, the team scrambles.

## Our Philosophy: Automation First, AI Where Needed

Before reaching for AI, we asked a simple question for each operational requirement: *can deterministic automation handle this?* The answer was yes far more often than expected.

| # | Requirement | Automation Covers | AI Needed? |
|---|---|---|---|
| 1 | Daily Health Checks | ~90% | Optional — trend analysis |
| 2 | Compliance Reports | ~95% | Optional — executive summaries |
| 3 | Alert Monitoring & Triage | ~70% | **Yes** — correlation, root cause |
| 4 | Security Agent Troubleshooting | ~60% | **Yes** — diagnosis, remediation |
| 5 | Accops Support | ~50% | Evaluate later |
| 6 | VMware BAU Tasks | ~90% | No |
| 7 | Monthly Patching | ~85% | Optional — risk assessment |
| 8 | Quarterly Hardening | ~80% | Optional — audit narrative |
| 9 | CMDB Updates | ~85% | No |

**The key insight: 7 of 9 requirements are fully served by deterministic automation.** AI agents earn their place on the 2–3 tasks that genuinely need judgment — alert triage (correlating multiple signals into a root cause), security troubleshooting (diagnosing why a Defender agent went silent), and ticket-driven remediation (reading a ticket, deciding what to investigate, and closing the loop). For everything else, a well-written PowerShell script with the right adapter is faster, cheaper, and more predictable than any LLM.

This isn't about avoiding AI. It's about not using a $0.03/call reasoning engine to check whether a Windows service is running.

The customer's technology preference was **low-code / no-code** — so we evaluated options that minimise custom application development while still delivering full automation coverage.

## The Architecture

We built a 2-tier system where each tier does what it's best at:

```
Tier 2: AI Agents — Incident response, alert triage, security diagnostics,
  │      compliance analysis, patch risk, trend detection, ticket remediation
  │      Skills (AgentSkills.io) + Tools (az CLI, GLPI REST, scripts)
  │
  │      Delivery options (same skills work on all):
  │      ├── Azure SRE Agent   — SaaS, production incident management
  │      ├── GitHub Copilot CLI — Terminal-native, lowest barrier to entry
  │      ├── Agent Framework    — Self-hosted, full customisation
  │      └── Foundry Agent      — SaaS, managed hosting
  │
Tier 1: PowerShell Scripts — Deterministic automation (the workhorse)
         Health checks, compliance pulls, CMDB sync, patching, VMware BAU
         Adapter Layer → Arc, Defender, GLPI ITSM/CMDB, Update Manager
  │
  ▼
Azure Arc-enrolled servers (on-prem + cloud + VMware)
```

**Azure Arc** is the hybrid bridge — every on-prem and VMware server is Arc-enrolled, giving us Run Commands, Azure Monitor Agent, Update Manager, and Policy from a single control plane. **Defender for Cloud** provides security posture management, CIS compliance baselines, and agent health monitoring. **PowerShell scripts** handle the scheduled automation (health checks 4×/day, compliance pulls daily, CMDB sync monthly). When a script detects something it can't handle — an alert storm, a failed Defender agent — it escalates to the **AI agent layer**.

The tools the agents call are deliberately simple: **Azure CLI** (`az graph query`, `az monitor log-analytics query`, `az connectedmachine run-command`), **GLPI REST API** (via `curl`), and **shell scripts**. No SDKs, no custom middleware. If an operations engineer can run the command in a terminal, the agent can too.

For the full architecture with data flow diagrams and adapter details, see [architecture.md](architecture.md).

## Agent Skills: An Open Standard for Operational Knowledge

Agent Skills are **packaged operational knowledge** — SOPs, scripts, and decision tables bundled into a format that AI coding agents (GitHub Copilot, Claude Code, Azure SRE Agent) can invoke on demand. The agent reads a `SKILL.md`, identifies the task, and executes commands step-by-step. No custom training or fine-tuning required.

The format follows the [AgentSkills.io](https://agentskills.io/specification) open standard:

```
my-skill/
├── SKILL.md          # Required: YAML frontmatter + step-by-step procedure
├── scripts/          # Optional: executable automation for deterministic tasks
├── references/       # Optional: domain docs loaded as needed
└── assets/           # Optional: templates, config files
```

The key design: **progressive disclosure**. The agent always loads the metadata (~100 words). It reads the full SKILL.md only when the trigger matches (<500 lines). Reference files load on demand. This keeps context windows lean while giving the agent deep expertise when needed.

We documented our team's SOPs, then converted each into a skill:

```
sre-skills/
├── wintel-health-check-investigation/
│   └── SKILL.md          # Disk, CPU, memory, services, event logs
├── security-agent-troubleshooting/
│   └── SKILL.md          # Defender for Endpoint agent diagnosis
├── compliance-investigation/
│   └── SKILL.md          # CIS benchmarks, Azure Policy correlation
├── patch-validation/
│   └── SKILL.md          # Pre/post patch health, rollback assessment
├── vmware-bau-operations/
│   └── SKILL.md          # Snapshot cleanup, resource monitoring
└── ticket-driven-remediation/
    └── SKILL.md          # ITSM closed-loop: read → classify → investigate → resolve
```

Because AgentSkills.io is an open standard, **these same 6 skills run unchanged on Azure SRE Agent, GitHub Copilot CLI, Agent Framework, and Foundry Agent Service.** Write once, deploy to any agent platform.

Here's what the health check skill looks like (abbreviated):

```yaml
---
name: wintel-health-check-investigation
version: 1.0.0
description: Investigates health check failures and warnings on Windows servers.
triggers:
  - Health check run completed with WARNING or CRITICAL status
  - Alert from Azure Monitor: disk, CPU, memory, or service threshold exceeded
tools:
  - arc-run-command
  - query-perf-trends
  - glpi-create-ticket
sop_source: docs/sops/daily-health-check.md
---

# Wintel Health Check Investigation

## Step 1 — Identify the affected server and check type
Query the most recent health check run...

## Step 2 — Check for active suppression rules
Before investigating, verify if there is an active suppression memory...

## Step 3 — Run live diagnostic via Arc Run Command
Based on the failing check: disk, services, event log, or CPU/memory...

## Step 4 — Determine root cause and action
| Finding              | Action                                    |
|----------------------|-------------------------------------------|
| Disk >90%            | Identify top consumers → cleanup ticket   |
| Disk >95%            | CRITICAL → P1 ticket + notify on-call     |
| Service won't restart| P2 ticket → escalate to app team          |
| CPU sustained >80%   | P3 ticket → capacity review               |
```

The agent reads the SKILL.md, follows the steps, calls the listed tools (all via `az` CLI and `curl`), and applies the decision table. Your senior engineer's judgment, codified and reproducible at 3 AM.

For the full skills inventory and custom tools, see [sre-skills.md](sre-skills.md).

## Two Delivery Options: SRE Agent vs. Copilot CLI

We evaluated four AI platforms, but two stood out for low-code/no-code delivery:

| Dimension | Azure SRE Agent | GitHub Copilot CLI |
|---|---|---|
| **Deployment** | SaaS (sre.azure.com) | Local CLI + cloud models |
| **Setup time** | ~2 hrs (portal config) | ~1 hr (install + clone repo) |
| **Skill format** | AgentSkills.io (shared) | AgentSkills.io (shared) |
| **Trigger model** | Automatic (alerts, schedules) | On-demand (engineer types a prompt) |
| **MCP Ecosystem** | Built-in connectors (Datadog, PagerDuty, ServiceNow, New Relic, Atlassian, GitHub) | Extensible via MCP servers |
| **Memory** | Persistent (learns from past incidents) | Session-only |
| **Best for** | Production 24/7 automation | Interactive investigation, demos, ad-hoc ops |
| **Custom code** | None (portal + SKILL.md) | None (CLI + SKILL.md) |

**SRE Agent** is the production choice — it runs continuously, triggers from alerts, and accumulates memory. **Copilot CLI** is the fastest path to a working demo — an engineer can run `copilot -p "investigate health on all my Arc servers" --allow-all-tools` and see results in 60 seconds. Both use the same 6 skills.

For the two pro-code options (Agent Framework, Foundry Agent Service), see [ai-tier-options.md](ai-tier-options.md).

## Seeing It In Action: 8 Demo Scenarios

This is the "aha moment" for stakeholders. Each scenario follows the same pattern: automation does the heavy lifting, AI adds judgment where it genuinely matters.

### Scenario A: Daily Health Check

**Before:** An engineer SSHes/RDPs into each server, runs `Get-PSDrive`, checks services, scans event logs, copies results into a spreadsheet. Repeat for every server. **45 minutes per cycle, 4 cycles per day.**

**After:** A PowerShell script runs health checks across all Arc-enrolled servers via Run Commands in parallel, evaluates thresholds, and generates a structured report. **30 seconds, zero human effort.**

But here's where the AI agent adds value that automation alone can't: the script reports "Disk at 88% on SRV-DB — WARNING." A human glances at that and moves on. The agent queries performance trend data via KQL, sees that disk has been growing at 3% per week, and reports: *"Disk on SRV-DB is at 88% and growing ~3%/week. At current rate, it will breach 95% in approximately 5 days. Recommend scheduling cleanup or capacity increase this week."*

That's the difference between monitoring and *insight*.

### Scenario H: Ticket-Driven Remediation (Closed-Loop ITSM)

This is the highest-AI scenario and the one that demonstrates the full power of an AI agent. A ticket lands in GLPI:

> *"CMDB shows ArcBox-Win2K25 running Windows Server 2022, but Azure shows 2025. Please verify and update."*

The agent:
1. **Reads** all open tickets from GLPI via REST API
2. **Classifies** each ticket by type (CMDB mismatch, health issue, security concern, compliance gap, patching request)
3. **Investigates** — for a CMDB ticket, queries Azure Resource Graph for the real OS version, compares against GLPI CMDB
4. **Updates** the ticket with structured findings (what was checked, what was found, what action was taken)
5. **Resolves** the ticket automatically

No deterministic script can do this — it requires reading natural language, inferring intent, choosing the right investigation, and composing a coherent follow-up. This is where AI agents earn their keep.

### All 8 Scenarios

| # | Scenario | Automation | AI | Description |
|---|---|---|---|---|
| A | Health Check | 90% | 10% | Cross-server metrics → AI adds trend analysis |
| B | Alert Triage | 70% | 30% | Route alerts → AI correlates root cause |
| C | Security Agent | 60% | 40% | Restart agents → AI diagnoses complex failures |
| D | Compliance | 95% | 5% | Pull CIS data → AI writes executive narrative |
| E | Patching | 85% | 15% | Deploy patches → AI assesses rollback risk |
| F | CMDB Sync | 100% | 0% | Compare & update — **no AI needed** |
| G | Snapshot Cleanup | 100% | 0% | Delete stale checkpoints — **no AI needed** |
| H | Ticket Remediation | 30% | 70% | Read ticket → classify → investigate → resolve |

Scenarios F and G are deliberately **100% automation with zero AI** — demonstrating intellectual honesty about where AI adds value versus where simple rule-based logic is sufficient.

See [demos/](demos/) for all scenario walkthroughs.

## Demo Environment: Zero-Cost Proof of Concept

You don't need a production environment to prove this out. [Azure Jumpstart ArcBox for IT Pros](https://jumpstart.azure.com/azure_jumpstart_arcbox/ITPro) deploys a full simulated datacenter — 5 Arc-enrolled VMs (Windows Server 2022, 2025, SQL Server, Ubuntu) — in a single Azure subscription via Bicep. Add [GLPI](https://glpi-project.org/) (open-source ITSM + CMDB) running in Azure Container Instances, enable Defender for Cloud, and you have a working demo environment in under an hour.

```
Demo Environment
├── ArcBox for IT Pros     → 5 Arc-enrolled VMs (the "datacenter")
├── Defender for Cloud     → Security posture, CIS compliance, agent health
├── Log Analytics          → Unified telemetry (perf, events, heartbeats)
├── Azure Update Manager   → Patch assessment and deployment
├── GLPI (ACI container)   → ITSM ticketing + CMDB (simulates ManageEngine)
└── GitHub Copilot CLI     → AI agent runtime (or SRE Agent portal)
```

**13 of 14 components are real** — same Azure Arc, same Defender for Cloud, same agent skills you'd use in production. The only demo-specific component is GLPI standing in for ManageEngine. When you move to production, you swap one adapter. Everything else stays identical.

Estimated cost: **~$50–80/month** if you shut down VMs when not demoing. Defender for Cloud offers a 30-day free trial.

For full setup instructions, see [demo-environment.md](demo-environment.md).

## What We Learned

**Start with automation — get the 85–90% win first.** The temptation is to lead with AI because it demos well. Resist it. A scheduled PowerShell script that runs health checks in 30 seconds is more valuable than the world's smartest AI agent that takes 2 minutes and costs $0.15 per run. Get the deterministic wins locked in, then layer AI on the gaps.

**SOPs → Skills is the killer pattern.** Most teams already have procedures — they're just in wikis, runbooks, or (worst case) someone's head. The hardest part isn't building the skill; it's getting the SOP documented. Once it's written down, converting it to a SKILL.md with YAML frontmatter and tool references is straightforward. And because AgentSkills.io is an open standard, the same skill works across SRE Agent, Copilot CLI, and any future agent platform.

**Skills are portable — write once, run anywhere.** We wrote 6 skills and tested them on GitHub Copilot CLI (fast iteration, immediate feedback in the terminal). The same SKILL.md files can be uploaded to Azure SRE Agent without modification. This decouples your operational knowledge from any single AI platform.

**The closed-loop ITSM pattern is the most impressive demo.** When stakeholders see a ticket get created, investigated, annotated with findings, and auto-resolved — all without human intervention — it clicks. The ticket-driven remediation skill (Scenario H) combines everything: ITSM API integration, Azure investigation, natural language understanding, and structured output. It's the scenario that sells the vision.

**The memory feature compounds over time.** Every time the agent resolves an incident, it can learn from the outcome. "Server SRV-BATCH runs a nightly job that spikes CPU to 95% — this is expected, don't create a ticket." After a month, the agent knows your environment better than a new hire.

**The adapter pattern pays for itself immediately.** We spent extra time building a tool-agnostic adapter layer (Arc, Defender, ITSM, CMDB). The payoff: when the customer's production ITSM is ManageEngine and the demo uses GLPI, we change one config value. Same REST pattern, different URL.

**Low-code/no-code is achievable.** The customer's preference was minimal custom code. With Agent Skills + Azure CLI + REST APIs, we delivered 8 demo scenarios without writing a single custom application. The skills are Markdown files. The tools are CLI commands. An operations engineer can maintain this.

## Get Started

The full implementation is open source:

- **GitHub repo:** [ops-automation-using-sre-agent](https://github.com/prwani/ops-automation-using-sre-agent)
- **Start here:** [architecture.md](architecture.md) for the system design, [demo-environment.md](demo-environment.md) for the sandbox setup, [TESTING.md](../TESTING.md) for quick validation
- **AI tier comparison:** [ai-tier-options.md](ai-tier-options.md) — SRE Agent vs. Copilot CLI vs. Agent Framework vs. Foundry
- **Skills directory:** [sre-skills.md](sre-skills.md) — all 6 skills with tool inventories
- **SRE Agent portal:** [https://sre.azure.com](https://sre.azure.com)
- **Agent Skills resources:** [AgentSkills.io](https://agentskills.io/specification) (open standard), [Azure Skills Directory](https://github.com/microsoft/azure-skills/), [Anthropic Skills Gallery](https://github.com/anthropics/skills)

The repo includes all PowerShell demo scripts, 6 Agent Skills (AgentSkills.io format), GLPI ITSM integration, Bicep infrastructure templates, and 8 demo scenarios. Everything you need to go from "we do this manually" to "this runs itself" — with AI adding judgment where it genuinely matters.
