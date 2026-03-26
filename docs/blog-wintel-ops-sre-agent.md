# Automating Windows Server Operations with Azure SRE Agent: An Automation-First Approach

> **How this blog is different from existing coverage:**
>
> Three TechCommunity blogs already cover Azure SRE Agent:
> - *"Announcing GA for Azure SRE Agent"* (March 2026) — GA announcement, Microsoft's internal results (1300 agents, 35K incidents, 20K hours saved)
> - *"Reimagining AI Ops with Azure SRE Agent"* (Nov 2025) — sub-agent builder, MCP connectors, prebuilt scenarios
> - *"What's New in GA Release"* (March 2026) — redesigned onboarding, deep context, ecosystem integrations
>
> **What this blog adds:** A real-world, end-to-end implementation for Windows Server / VMware / Security operations (sometimes called "Wintel" in enterprise IT) — with quantified automation coverage, SRE Agent Skills built from actual SOPs, and a working demo environment you can deploy today. We lead with automation, not AI.

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

**The key insight: 7 of 9 requirements are fully served by deterministic automation.** SRE Agent earns its place on the 2 tasks that genuinely need judgment — alert triage (correlating multiple signals into a root cause) and security troubleshooting (diagnosing why a Defender agent went silent). For everything else, a well-written PowerShell script with the right adapter is faster, cheaper, and more predictable than any LLM.

This isn't about avoiding AI. It's about not using a $0.03/call reasoning engine to check whether a Windows service is running.

## The Architecture

We built a 2-tier system where each tier does what it's best at:

```
Tier 2: Azure SRE Agent — Incident response, alert triage, security diagnostics,
  │      compliance analysis, patch risk, trend detection
  │      Skills (AgentSkills.io) + Custom tools + Runbooks + Memory
  │
Tier 1: PowerShell Scripts — Deterministic automation (the workhorse)
         Health checks, compliance pulls, CMDB sync, patching, VMware BAU
         Adapter Layer → Arc, Defender, GLPI ITSM/CMDB, Update Manager
  │
  ▼
Azure Arc-enrolled servers (on-prem + cloud + VMware)
```

**Azure Arc** is the hybrid bridge — every on-prem and VMware server is Arc-enrolled, giving us Run Commands, Azure Monitor Agent, Update Manager, and Policy from a single control plane. **Defender for Cloud** provides security posture management, CIS compliance baselines, and agent health monitoring. **PowerShell scripts** handle the scheduled automation (health checks 4×/day, compliance pulls daily, CMDB sync monthly). When a script detects something it can't handle — an alert storm, a failed Defender agent — it escalates to **SRE Agent**.

For the full architecture with data flow diagrams and adapter details, see [architecture.md](architecture.md).

## Codifying SOPs as SRE Agent Skills

Every operations team has tribal knowledge locked in people's heads: "If disk is above 90% on SRV-DB, check the temp tables first." "If the Defender agent stops reporting, restart the service, then check connectivity to `*.ods.opinsights.azure.com`."

We documented these procedures as SOPs, then converted each into an [AgentSkills.io](https://agentskills.io/specification) skill — the format SRE Agent natively loads:

```
sre-skills/
├── wintel-health-check-investigation/
│   └── SKILL.md          # YAML frontmatter + step-by-step procedure
├── security-agent-troubleshooting/
│   └── SKILL.md
├── patch-validation/
│   └── SKILL.md
├── compliance-investigation/
│   └── SKILL.md
└── vmware-bau-operations/
    └── SKILL.md
```

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

SRE Agent loads these skills automatically when the context matches — no explicit invocation needed. The agent reads the SKILL.md, follows the steps, calls the listed tools, and applies the decision table. Your senior engineer's judgment, codified and reproducible at 3 AM.

For the full skills inventory and custom tools, see [sre-skills.md](sre-skills.md).

## Seeing It In Action: The Health Check Demo

This is the "aha moment" for stakeholders. The contrast tells the story:

**Before:** An engineer SSHes/RDPs into each server, runs `Get-PSDrive`, checks services, scans event logs, copies results into a spreadsheet. Repeat for every server. **45 minutes per cycle, 4 cycles per day.**

**After:** A PowerShell script (`scripts/demo-a-health-check.ps1`) runs health checks across all Arc-enrolled servers via Run Commands in parallel, evaluates thresholds, and generates a structured report. **30 seconds, zero human effort.**

But here's where SRE Agent adds value that automation alone can't: the script reports "Disk at 88% on SRV-DB — WARNING." A human glances at that and moves on. SRE Agent queries the performance trend data via KQL, sees that disk has been growing at 3% per week, and reports: *"Disk on SRV-DB is at 88% and growing ~3%/week. At current rate, it will breach 95% in approximately 5 days. Recommend scheduling cleanup or capacity increase this week."*

That's the difference between monitoring and *insight* — and it's the kind of judgment that earns AI its place in the stack.

We built 7 demo scenarios covering health checks, alert triage, security agent troubleshooting, compliance reporting, patching, CMDB sync, and VMware snapshot cleanup. Each one follows the same pattern: automation does the heavy lifting, AI adds the judgment. See [demos/](demos/) for all scenario walkthroughs.

## Demo Environment: Zero-Cost Proof of Concept

You don't need a production environment to prove this out. [Azure Jumpstart ArcBox for IT Pros](https://jumpstart.azure.com/azure_jumpstart_arcbox/ITPro) deploys a full simulated datacenter — 5 Arc-enrolled VMs (Windows Server 2022, 2025, SQL Server, Ubuntu) — in a single Azure subscription via Bicep. Add GLPI (open-source ITSM+CMDB) in a Docker container, enable Defender for Cloud, and you have a working demo environment in under an hour.

**13 of 14 components are real** — same Azure Arc, same Defender for Cloud, same SRE Agent you'd use in production. The only demo-specific component is GLPI standing in for ManageEngine. When you move to production, you swap one adapter (`glpi_adapter` → `manageengine_adapter`). Everything else stays identical.

Estimated cost: **~$50–80/month** if you shut down VMs when not demoing. Defender for Cloud offers a 30-day free trial.

For full setup instructions, see [demo-environment.md](demo-environment.md).

## What We Learned

**Start with automation — get the 85–90% win first.** The temptation is to lead with AI because it demos well. Resist it. A scheduled PowerShell script that runs health checks in 30 seconds is more valuable than the world's smartest AI agent that takes 2 minutes and costs $0.15 per run. Get the deterministic wins locked in, then layer AI on the gaps.

**SOPs → Skills is the killer pattern for SRE Agent adoption.** Most teams already have procedures — they're just in wikis, runbooks, or (worst case) someone's head. The hardest part isn't building the skill; it's getting the SOP documented. Once it's written down, converting it to a SKILL.md with YAML frontmatter and tool references is straightforward.

**The memory feature compounds over time.** Every time SRE Agent resolves an incident, it can learn from the outcome. "Server SRV-BATCH runs a nightly job that spikes CPU to 95% — this is expected, don't create a ticket." After a month, the agent knows your environment better than a new hire.

**The adapter pattern pays for itself immediately.** We spent extra time building a tool-agnostic adapter layer (Arc, Defender, ITSM, CMDB). The payoff: when the customer's production ITSM is ManageEngine and the demo uses GLPI, we change one config value. Same REST pattern, different URL.

## Get Started

The full implementation is open source:

- **GitHub repo:** [ops-automation-using-sre-agent](https://github.com/prwani/ops-automation-using-sre-agent)
- **Start here:** [architecture.md](architecture.md) for the system design, [sre-agent-setup.md](sre-agent-setup.md) for SRE Agent configuration, [demo-environment.md](demo-environment.md) for the sandbox setup
- **SRE Agent portal:** [https://sre.azure.com](https://sre.azure.com)

The repo includes all PowerShell demo scripts, SRE Agent skills, adapter implementations, Bicep infrastructure templates, and GLPI integration. Everything you need to go from "we do this manually" to "this runs itself" — with AI adding judgment where it genuinely matters.
