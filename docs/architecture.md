# Architecture

## Design Principles

| Principle | Detail |
|---|---|
| **Tool-agnostic** | All ITSM/monitoring integrations via adapter pattern — swap ManageEngine for ServiceNow without changing core logic |
| **Hybrid-ready via Azure Arc** | On-prem servers enrolled in Azure Arc for unified management; Arc-enabled VMware vSphere projects vCenter VMs into Azure |
| **AI-augmented (where needed)** | Azure SRE Agent for incident response, diagnostics, compliance analysis, and trend detection |
| **SOP-first** | Every automation starts with a documented SOP; SRE Agent Skills codify SOPs as executable procedures |
| **Observable** | Every run emits structured logs, metrics, and alerts; results queryable via Log Analytics and GLPI |

## Two-Tier Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Tier 2: Azure SRE Agent (AI — Incident Response + Analysis)     │
│                                                                  │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────┐  │
│  │ Incident Auto-   │  │ Custom Subagents   │  │ Scheduled    │  │
│  │ Response         │  │ • VM Diagnostics   │  │ Health Checks│  │
│  │ • Alert triage   │  │ • Security Agent   │  │              │  │
│  │ • Correlate logs │  │   Troubleshooting  │  │              │  │
│  │ • Root cause     │  │ • Network Issues   │  │              │  │
│  │ • Auto-remediate │  │                    │  │              │  │
│  │ • Memory/learning│  │ Runbooks:          │  │              │  │
│  └──────────────────┘  │ • Arc Run Commands │  └──────────────┘  │
│                        └───────────────────┘                     │
│  Skills (AgentSkills.io):                                        │
│  • wintel-health-check-investigation                             │
│  • security-agent-troubleshooting                                │
│  • patch-validation                                              │
│  • compliance-investigation                                      │
│  • vmware-bau-operations                                         │
│                                                                  │
│  Custom Tools: Kusto queries, Python (GLPI), MCP servers         │
└──────────────────┬───────────────────────────────────────────────┘
                   │ Creates ITSM tickets / queries CMDB
┌──────────────────▼───────────────────────────────────────────────┐
│  Tier 1: PowerShell Scripts (Deterministic Automation)            │
│                                                                  │
│  Demo Scripts (scripts/):                                        │
│  • demo-a-health-check.ps1    (4×/day)                           │
│  • demo-b-alert-triage.ps1    (event-driven)                     │
│  • demo-c-security-agent.ps1  (event-driven)                     │
│  • demo-d-compliance.ps1      (daily)                            │
│  • demo-e-patching.ps1        (monthly)                          │
│  • demo-f-cmdb-sync.ps1       (monthly)                          │
│  • demo-g-snapshot-cleanup.ps1 (weekly)                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Adapter Layer (Python Package)                │  │
│  │  arc │ defender │ itsm │ cmdb │ patch │ ad                │  │
│  └──┬──────┬───────────┬────────┬───────────┬────────────────┘  │
└─────┼──────┼───────────┼────────┼───────────┼───────────────────┘
      │      │           │        │           │
      ▼      ▼           ▼        ▼           ▼
   Azure   Defender    GLPI     GLPI       Azure
   Arc     for Cloud   ITSM     CMDB       Update
   Services API        API      API        Manager
```

## Azure Arc — The Hybrid Bridge

Azure Arc is the core mechanism for reaching on-prem and VMware machines from cloud-based automation.

| Capability | How It's Used |
|---|---|
| **Run Commands** | Execute health check scripts, diagnostics, and remediation on servers remotely |
| **Azure Monitor Agent** | Collect performance counters, event logs, and custom metrics → Log Analytics |
| **Azure Update Manager** | Cloud-orchestrated patch assessment, scheduling, and deployment |
| **Azure Policy / Guest Configuration** | Enforce CIS benchmarks and compliance baselines |
| **Azure Resource Graph** | Query all servers (cloud + on-prem + VMware) uniformly |
| **Arc-enabled VMware vSphere** | Project vCenter VMs into Azure — managed via the same Arc APIs, no separate VMware adapter needed |

### How Azure Arc Replaces Direct Network Access

1. **Health Checks:** PowerShell scripts → Arc Run Command → PowerShell script on server → results via ARM API
2. **Telemetry:** Azure Monitor Agent streams perf counters + event logs → Log Analytics → queryable via KQL
3. **Patching:** Azure Update Manager handles assessment + deployment → orchestrated via ARM API
4. **Compliance:** Azure Policy Guest Configuration evaluates CIS benchmarks → state queryable via Resource Graph
5. **VMware:** Arc-enabled VMware vSphere projects VMs into Azure → same APIs as native Azure VMs

## Microsoft Defender for Cloud — Security & Compliance

Defender for Cloud provides the security posture management layer:

| Capability | How It's Used |
|---|---|
| **Regulatory Compliance Dashboard** | CIS, NIST, PCI DSS, ISO 27001 — continuous evaluation across all Arc-enrolled servers |
| **Security Alerts** | AI-powered threat detection with kill-chain correlation and MITRE ATT&CK mapping |
| **Defender for Endpoint** | Agent health monitoring, vulnerability assessment on all servers |
| **Security Recommendations** | Prioritized remediation guidance queryable via API |
| **Secure Score** | Single metric for overall security posture across hybrid estate |

Compliance data is queried via Azure Resource Graph and the Security API, consumed by both the automation scripts (report generation) and the SRE Agent (executive summaries and trend analysis).

## Azure SRE Agent — Incident Response, Diagnostics & Analysis

SRE Agent handles the judgment-heavy tasks that deterministic automation can't, plus analysis and reporting that benefits from AI reasoning:

| Feature | How It's Used |
|---|---|
| **Automatic incident reception** | Azure Monitor Alerts → SRE Agent → auto-triage + investigation |
| **Custom subagents** | VM Diagnostics, Security Agent Troubleshooting (no-code builder) |
| **Skills (AgentSkills.io)** | Each SOP becomes an executable skill with scripts + tools |
| **Custom tools** | Kusto queries, Python functions (GLPI), MCP servers |
| **Memory** | Learns from every incident resolution |
| **Run modes** | Autonomous / semi-autonomous / human-in-the-loop |
| **Compliance analysis** | Executive summaries, trend analysis, business-context prioritization |
| **Patch risk assessment** | KB risk scoring, wave grouping, post-patch failure correlation |
| **Health insights** | Cross-server anomaly detection, trend projection, daily briefs |

### SRE Agent Skills

Every SOP from Phase 1 becomes a SKILL.md with attached tools:

| Skill | SOP Source | Scripts | Tools |
|---|---|---|---|
| `wintel-health-check-investigation` | daily-health-check.md | Disk, services, event logs, CPU/memory | Arc Run Cmd, KQL perf trends |
| `security-agent-troubleshooting` | security-agent-troubleshooting.md | Defender agent check, restart, connectivity | Defender API, Arc Run Cmd |
| `patch-validation` | windows-patching.md | Pre/post patch checks, rollback assessment | Update Manager, Arc Run Cmd |
| `compliance-investigation` | compliance-reporting.md | Defender compliance query | Resource Graph, Defender API |
| `vmware-bau-operations` | vmware-bau.md | Snapshot list/cleanup, resource report, VM health | Arc Run Cmd |

## GLPI — ITSM & CMDB

[GLPI](https://glpi-project.org/) is a production-grade open-source ITSM platform with a built-in CMDB module. In the demo environment it provides both ticketing and configuration management. In production, the adapter layer swaps GLPI for ManageEngine (or any ITSM with a REST API).

| Capability | How It's Used |
|---|---|
| **Incident tickets** | Auto-created by scripts and SRE Agent with severity mapping |
| **CMDB** | Server CI records queried for context enrichment during triage |
| **SLA tracking** | Priority-based escalation timers |
| **REST API** | All operations automated — no manual portal interaction |

See [sre-skills.md](sre-skills.md) for the full skill inventory and custom tools.

See [sre-agent-setup.md](sre-agent-setup.md) for the step-by-step SRE Agent deployment guide.

## Adapter Layer

All external tool integrations go through swappable adapters:

| Adapter | Production Tool | Demo Tool |
|---|---|---|
| `arc_adapter` | Azure Arc (same) | Azure Arc (same) |
| `defender_adapter` | Defender for Cloud (same) | Defender for Cloud (same) |
| `itsm_adapter` | ManageEngine ServiceDesk Plus | GLPI (open-source) |
| `cmdb_adapter` | ManageEngine CMDB | GLPI CMDB (built-in) |
| `patch_adapter` | Azure Update Manager (same) | Azure Update Manager (same) |
| `ad_adapter` | AD / Entra ID (same) | AD / Entra ID (same) |

**Only the ITSM and CMDB adapters differ** between demo and production. All Azure-native adapters are identical.

## Data Flow

```
On-prem servers                    Azure
──────────────                     ─────
Windows/VMware VMs                 
  │                                
  ├── Arc Agent ──────────────────→ Azure Resource Manager
  │   ├── Monitor Agent ──────────→ Log Analytics (telemetry)
  │   ├── Defender for Endpoint ──→ Defender for Cloud (security)
  │   └── Update Manager ────────→ Azure Update Manager (patches)
  │
  └── Arc Run Commands ◄──────────── PowerShell scripts (automation)
                                        │
                                        ├──→ SRE Agent (incidents + analysis)
                                        └──→ GLPI (ITSM tickets + CMDB)
```
