# Ops Automation Using Azure SRE Agent

Automate Wintel (Windows / VMware / Security) operations using **Azure Arc**, **Microsoft Defender for Cloud**, and **Azure SRE Agent** — eliminating manual toil for health checks, compliance, alerting, patching, and CMDB management.

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

A **2-tier architecture** that uses deterministic automation first, and AI only where human judgment is needed:

```
┌──────────────────────────────────────────────────────────────┐
│  Tier 2: Azure SRE Agent (AI)                                │
│  Incident response, alert triage, security diagnostics,      │
│  compliance analysis, patch risk, trend detection             │
│  Skills (AgentSkills.io) + Custom tools + Runbooks           │
├──────────────────────────────────────────────────────────────┤
│  Tier 1: PowerShell Scripts (Deterministic Automation)        │
│  Health checks, data collection, CMDB sync, patching         │
│  Adapter Layer → Arc, Defender, GLPI ITSM/CMDB, Update Mgr  │
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
| [Azure Update Manager](https://learn.microsoft.com/azure/update-manager/) | Patch assessment, scheduling, and deployment across hybrid estate |
| [GLPI](https://glpi-project.org/) | Open-source ITSM ticketing + CMDB (swappable for ManageEngine in production) |

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full architecture documentation.

## Automation vs. AI Strategy

> **Philosophy:** Deterministic automation is the first choice. AI is introduced only where automation hits a genuine ceiling.

| # | Requirement | Automation Covers | AI Component |
|---|---|---|---|
| 1 | Daily Health Checks | ~90% | Optional — SRE Agent trend analysis |
| 2 | Compliance Reports | ~95% | Optional — SRE Agent executive summaries |
| 3 | Alert Monitoring | ~70% | **SRE Agent** (built-in incident response) |
| 4 | Security Troubleshooting | ~60% | **SRE Agent** (custom subagent + skills) |
| 5 | Accops Support | ~50% | Evaluate in Phase 3 |
| 6 | VMware BAU | ~90% | Not needed |
| 7 | Monthly Patching | ~85% | Optional — SRE Agent risk assessment |
| 8 | Quarterly Hardening | ~80% | Optional — audit narrative |
| 9 | CMDB Updates | ~85% | Not needed |

**7 of 9 requirements are fully served by deterministic automation.** SRE Agent handles the 2 judgment-heavy tasks natively.

## Demo Environment

Uses [Azure Jumpstart ArcBox for IT Pros](https://jumpstart.azure.com/azure_jumpstart_arcbox/ITPro) — a self-contained sandbox with Arc-enrolled VMs. All core components run real (no mocks). Only GLPI (open-source ITSM+CMDB) is demo-specific.

See [docs/demo-environment.md](docs/demo-environment.md) for setup instructions.

## Demo Scripts

Seven PowerShell scripts in `scripts/` demonstrate each automation scenario end-to-end:

| Script | Scenario | Description |
|---|---|---|
| `scripts/demo-a-health-check.ps1` | Daily Health Check | Collect disk, CPU, memory, services, event logs across Arc VMs |
| `scripts/demo-b-alert-triage.ps1` | Alert Triage | Spike CPU + stop service → trigger alerts → create GLPI ticket |
| `scripts/demo-c-security-agent.ps1` | Security Agent | Break/restart Defender agent, auto-diagnose via Arc Run Commands |
| `scripts/demo-d-compliance.ps1` | Compliance Reporting | Pull Defender + Policy compliance data, generate HTML report |
| `scripts/demo-e-patching.ps1` | Monthly Patching | Assess, deploy, validate patches via Azure Update Manager |
| `scripts/demo-f-cmdb-sync.ps1` | CMDB Sync | Compare Azure Resource Graph vs GLPI CMDB, auto-reconcile |
| `scripts/demo-g-snapshot-cleanup.ps1` | Snapshot Cleanup | Find and delete stale Hyper-V checkpoints older than 7 days |

## Project Structure

```
├── docs/                    # Architecture, demo setup, SRE Agent guides
├── scripts/                 # PowerShell demo scripts (7 scenarios)
├── src/adapters/            # Tool-agnostic integration layer (Arc, Defender, ITSM, CMDB, Patch)
├── src/health_checks/       # Health check engine
├── src/compliance/          # Compliance report engine (Defender for Cloud)
├── src/alerting/            # Alert ingestion + routing to SRE Agent
├── src/patching/            # Patch orchestration (Azure Update Manager)
├── src/cmdb/                # CMDB reconciliation engine
├── sre-skills/              # SRE Agent Skills (AgentSkills.io format)
├── sre-tools/               # SRE Agent custom Kusto + Python tools
├── infra/                   # Bicep IaC for Azure resources
└── tests/                   # Test suite
```

## Implementation Timeline

| Phase | Duration | Focus |
|---|---|---|
| **Assess** | Weeks 1–2 | Document SOPs, audit APIs, measure baselines, Arc onboarding |
| **Build** | Weeks 3–6 | Adapters, automation engines, SRE Agent skills, demo scripts |
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

## Testing

See [TESTING.md](TESTING.md) for the quick-start guide.

**Quick test (copy-paste):**
```bash
copilot -p "Use the /wintel-health-check-investigation skill. Run a FULL health check on all my Arc servers — check CPU, memory, disk, services, and event logs." --allow-all-tools
```

**Automation scripts (no AI):**
```bash
./scripts/demo-run-all.ps1
```

**Per-scenario guides:** [docs/implementations/](docs/implementations/)

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Two-tier design, data flow, adapter layer |
| [Demo Environment](docs/demo-environment.md) | ArcBox setup, demo stack, cost estimates |
| [Demo Scenarios](docs/demos/README.md) | Step-by-step demo walkthroughs |
| [SRE Agent Skills](docs/sre-skills.md) | Skill inventory, custom tools, SOP → skill mapping |
| [SRE Agent Setup](docs/sre-agent-setup.md) | Step-by-step SRE Agent deployment and configuration |
| [GLPI Setup](docs/glpi-setup.md) | GLPI ITSM/CMDB installation and configuration |
| [Blog: Wintel Ops SRE Agent](docs/blog-wintel-ops-sre-agent.md) | Project overview blog post |

## License

[MIT](LICENSE)

