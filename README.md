# Ops Automation Using Azure SRE Agent

Automate Wintel (Windows / VMware / Security) operations using **Azure Arc**, **Microsoft Defender for Cloud**, **Azure SRE Agent**, and **Azure AI Foundry Agents** — eliminating manual toil for health checks, compliance, alerting, patching, and CMDB management.

## Problem

The Wintel team spends significant time on repetitive BAU operations:

| Task | Current Effort | Frequency |
|---|---|---|
| Daily health checks | 30–45 min × 4/day | 4×/day |
| Compliance reports (security agents) | 1 hr | Daily |
| Alert monitoring & ticket management | 24/7 | Continuous |
| Security agent troubleshooting | Ad-hoc | As needed |
| VMware BAU tasks | Ad-hoc | As needed |
| Windows patching | 9 hrs | Monthly |
| Hardening / recertification | Multi-day | Quarterly |
| CMDB updates | 2 hrs | Monthly |

All tasks are largely manual, ad-hoc, and undocumented. This project automates them.

## Solution Overview

A **3-tier architecture** that uses deterministic automation first, and AI only where human judgment is needed:

```
┌──────────────────────────────────────────────────────────────┐
│  Tier 3: Azure SRE Agent                                     │
│  Incident response, alert triage, security diagnostics       │
│  Skills (AgentSkills.io) + Custom tools + Runbooks           │
├──────────────────────────────────────────────────────────────┤
│  Tier 2: Azure AI Foundry Agents + Workflows                 │
│  Compliance analysis, patch risk, daily briefs, portal chat  │
├──────────────────────────────────────────────────────────────┤
│  Tier 1: Azure Functions (Deterministic Automation)           │
│  Health checks, data collection, CMDB sync, patching         │
│  Adapter Layer → Arc, Defender, ITSM, CMDB, Update Manager   │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
   Azure Arc-enrolled servers (on-prem + cloud)
```

## Key Azure Services

| Service | Role |
|---|---|
| [Azure Arc](https://learn.microsoft.com/azure/azure-arc/) | Hybrid bridge — enroll on-prem servers, run commands remotely, unified management |
| [Arc-enabled VMware vSphere](https://learn.microsoft.com/azure/azure-arc/vmware-vsphere/overview) | Project vCenter VMs into Azure — same `arc_adapter` handles everything |
| [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/) | Security posture, CIS compliance, vulnerability assessment, agent health |
| [Azure SRE Agent](https://learn.microsoft.com/azure/sre-agent/) | AI-powered incident response, investigation, remediation with built-in memory |
| [Azure AI Foundry Agent Service](https://learn.microsoft.com/azure/ai-services/agents/) | Compliance analysis, patch risk assessment, portal chat with memory |
| [Azure Functions](https://learn.microsoft.com/azure/azure-functions/) | Timer-triggered automation — health checks, compliance pulls, CMDB sync |
| [Azure Update Manager](https://learn.microsoft.com/azure/update-manager/) | Patch assessment, scheduling, and deployment across hybrid estate |
| [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/) | Run history, user feedback, and memory storage for the Operations Portal |

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full architecture documentation.

## Automation vs. AI Strategy

> **Philosophy:** Deterministic automation is the first choice. AI is introduced only where automation hits a genuine ceiling.

| # | Requirement | Automation Covers | AI Component |
|---|---|---|---|
| 1 | Daily Health Checks | ~90% | Optional — Health Insights Agent |
| 2 | Compliance Reports | ~95% | Optional — Compliance Analyst Agent |
| 3 | Alert Monitoring | ~70% | **SRE Agent** (built-in incident response) |
| 4 | Security Troubleshooting | ~60% | **SRE Agent** (custom subagent + skills) |
| 5 | Accops Support | ~50% | Evaluate in Phase 3 |
| 6 | VMware BAU | ~90% | Not needed |
| 7 | Monthly Patching | ~85% | Optional — Patch Risk Agent |
| 8 | Quarterly Hardening | ~80% | Optional — audit narrative |
| 9 | CMDB Updates | ~85% | Not needed |

**7 of 9 requirements are fully served by deterministic automation.** SRE Agent handles the 2 judgment-heavy tasks natively.

## Operations Portal

A unified web app (React + TypeScript + Fluent UI) where engineers:
- **View today's runs** — real-time status of all automated tasks
- **Browse history** — filterable execution history with success/failure details
- **Chat with AI** — ask questions about runs, servers, or alerts using natural language
- **Give feedback** — instructions that become persistent memories (e.g., "ignore disk warnings on SRV-A for 10 days")

See [docs/portal.md](docs/portal.md) for portal design details.

## Demo Environment

Uses [Azure Jumpstart ArcBox for IT Pros](https://jumpstart.azure.com/azure_jumpstart_arcbox/ITPro) — a self-contained sandbox with Arc-enrolled VMs. **13 out of 14 components run real** (no mocks). Only GLPI (open-source ITSM+CMDB) is demo-specific.

See [docs/demo-environment.md](docs/demo-environment.md) for setup instructions.

## Project Structure

```
├── docs/                    # Architecture, portal design, demo setup
├── src/adapters/            # Tool-agnostic integration layer (Arc, Defender, ITSM, CMDB, Patch)
├── src/health_checks/       # Health check engine
├── src/compliance/          # Compliance report engine (Defender for Cloud)
├── src/alerting/            # Alert ingestion + routing to SRE Agent
├── src/patching/            # Patch orchestration (Azure Update Manager)
├── src/cmdb/                # CMDB reconciliation engine
├── agents/                  # Foundry Agent definitions (Compliance, Patch Risk, Ops Chat)
├── sre-skills/              # SRE Agent Skills (AgentSkills.io format)
├── sre-tools/               # SRE Agent custom Kusto + Python tools
├── workflows/               # Foundry Workflow definitions (YAML)
├── functions/               # Azure Functions entry points (timer-triggered)
├── portal/                  # React + TypeScript frontend
├── portal-api/              # FastAPI backend (Entra auth, Cosmos DB, Foundry chat)
├── infra/                   # Bicep IaC for Azure resources
└── tests/                   # Test suite
```

## Implementation Timeline

| Phase | Duration | Focus |
|---|---|---|
| **Assess** | Weeks 1–2 | Document SOPs, audit APIs, measure baselines, Arc onboarding |
| **Build** | Weeks 3–6 | Adapters, automation engines, SRE Agent skills, Functions, Portal |
| **Pilot** | Weeks 7–10 | Deploy to 10–20% of estate, measure KPIs, tune |
| **Scale** | Month 3 / Q2 | Full rollout, operations handover, ongoing KPI reporting |

## Success KPIs

| KPI | Baseline | Target |
|---|---|---|
| Time on health checks | ~2–3 hrs/day | < 15 min/day |
| Time on compliance reports | ~1 hr/day | < 5 min/day |
| Mean time to acknowledge alerts | TBD | Reduce by ≥ 50% |
| Monthly patching effort | ~9 hrs | < 2 hrs |
| Patch compliance rate | TBD | ≥ 95% |
| CMDB accuracy | TBD | ≥ 98% |

## License

[MIT](LICENSE)
