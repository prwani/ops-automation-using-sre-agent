# Architecture

## Design Principles

| Principle | Detail |
|---|---|
| **Tool-agnostic** | All ITSM/monitoring integrations via adapter pattern — swap ManageEngine for ServiceNow without changing core logic |
| **Hybrid-ready via Azure Arc** | On-prem servers enrolled in Azure Arc for unified management; Arc-enabled VMware vSphere projects vCenter VMs into Azure |
| **AI-augmented (where needed)** | Azure SRE Agent for incident response/diagnostics; Foundry Agents for compliance analysis/reporting/portal chat |
| **SOP-first** | Every automation starts with a documented SOP; SRE Agent Skills codify SOPs as executable procedures |
| **Observable** | Every run emits structured logs, metrics, and alerts; all results stored in Cosmos DB and visible in the Operations Portal |

## Three-Tier Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Tier 3: Azure SRE Agent (Incident Response)                     │
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
│  Custom Tools: Kusto queries, Python (GLPI, Cosmos), MCP servers │
└──────────────────┬───────────────────────────────────────────────┘
                   │ Triggers Foundry for analysis / Creates ITSM tickets
┌──────────────────▼───────────────────────────────────────────────┐
│  Tier 2: Azure AI Foundry Agents + Workflows (Analysis Layer)    │
│                                                                  │
│  Agents:                                                         │
│  ┌────────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ Compliance     │ │ Patch Risk │ │ Health     │ │ Ops Chat │ │
│  │ Analyst        │ │ Agent      │ │ Insights   │ │ (Portal) │ │
│  └────────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│                                                                  │
│  Workflows (Foundry):                                            │
│  • Patch Cycle: Risk Assessment → Approval → Deploy → Validate   │
│  • Daily Brief: Health + Compliance + Patch (concurrent → summary)│
└──────────────────┬───────────────────────────────────────────────┘
                   │ Invokes when AI analysis needed
┌──────────────────▼───────────────────────────────────────────────┐
│  Tier 1: Azure Functions (Deterministic Automation)              │
│                                                                  │
│  Timer Triggers:                                                 │
│  • Health check data collection (4×/day)                         │
│  • Compliance data pull (daily)                                  │
│  • Alert ingestion (every 5 min)                                 │
│  • CMDB sync (monthly)                                           │
│  • Patch assessment (monthly)                                    │
│  • VMware BAU tasks (scheduled)                                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Adapter Layer (Python Package)                │  │
│  │  arc │ defender │ itsm │ cmdb │ patch │ ad                │  │
│  └──┬──────┬───────────┬────────┬───────────┬────────────────┘  │
└─────┼──────┼───────────┼────────┼───────────┼───────────────────┘
      │      │           │        │           │
      ▼      ▼           ▼        ▼           ▼
   Azure   Defender   ManageEng  GLPI      Azure
   Arc     for Cloud  (or GLPI)  CMDB      Update
   Services API       ITSM API   API       Manager
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

1. **Health Checks:** Azure Functions → Arc Run Command → PowerShell script on server → results via ARM API
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

Compliance data is queried via Azure Resource Graph and the Security API, consumed by both the automation layer (report generation) and the Compliance Analyst Foundry Agent (executive summaries).

## Azure SRE Agent — Incident Response & Diagnostics

SRE Agent handles the judgment-heavy tasks that deterministic automation can't:

| Feature | How It's Used |
|---|---|
| **Automatic incident reception** | Azure Monitor Alerts → SRE Agent → auto-triage + investigation |
| **Custom subagents** | VM Diagnostics, Security Agent Troubleshooting (no-code builder) |
| **Skills (AgentSkills.io)** | Each SOP becomes an executable skill with scripts + tools |
| **Custom tools** | Kusto queries, Python functions (GLPI, Cosmos DB), MCP servers |
| **Memory** | Learns from every incident resolution |
| **Run modes** | Autonomous / semi-autonomous / human-in-the-loop |

### SRE Agent Skills

Every SOP from Phase 1 becomes a SKILL.md with attached tools:

| Skill | SOP Source | Scripts | Tools |
|---|---|---|---|
| `wintel-health-check-investigation` | daily-health-check.md | Disk, services, event logs, CPU/memory | Arc Run Cmd, KQL perf trends |
| `security-agent-troubleshooting` | security-agent-troubleshooting.md | Defender agent check, restart, connectivity | Defender API, Arc Run Cmd |
| `patch-validation` | windows-patching.md | Pre/post patch checks, rollback assessment | Update Manager, Arc Run Cmd |
| `compliance-investigation` | compliance-reporting.md | Defender compliance query | Resource Graph, Defender API |
| `vmware-bau-operations` | vmware-bau.md | Snapshot list/cleanup, resource report, VM health | Arc Run Cmd |

## Foundry Agents — Analysis & Reporting

Foundry Agents handle tasks that require data synthesis and natural-language output:

| Agent | Purpose |
|---|---|
| **Compliance Analyst** | Interprets Defender for Cloud data, identifies trends, generates executive summaries |
| **Patch Risk** | Assesses patch risk by server role/dependencies, recommends wave grouping |
| **Health Insights** | Analyzes health data across servers, identifies anomalies, generates daily briefs |
| **Ops Chat** | Portal-integrated assistant with memory — queries live data, accepts user instructions |

## Foundry Workflows

| Workflow | Pattern | Purpose |
|---|---|---|
| **Patch Cycle** | Sequential + Human-in-the-loop | Risk assessment → approval → deploy → validate |
| **Daily Brief** | Concurrent → Sequential | Health + Compliance + Patch in parallel → combined summary |

## Operations Portal

React + TypeScript + Fluent UI frontend with FastAPI backend:

| Page | Purpose |
|---|---|
| **Dashboard** | Today's runs overview — cards per task type, timeline with memory annotations |
| **History** | Paginated execution history with date/task/status/server filters |
| **Chat** | Streaming AI assistant (Foundry Ops Chat Agent) with memory creation |
| **Memories** | Manage active/expired user instructions that affect automation behavior |

**Tech stack:** Entra ID authentication (MSAL.js), Cosmos DB (runs/feedback/memories), SSE for streaming.

See [portal.md](portal.md) for detailed page designs and data models.

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
  └── Arc Run Commands ◄──────────── Azure Functions (automation)
                                        │
                                        ├──→ Cosmos DB (run history)
                                        ├──→ SRE Agent (incidents)
                                        ├──→ Foundry Agents (analysis)
                                        └──→ Operations Portal (UI)
```
