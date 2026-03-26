# Demo Environment

## Overview

The demo environment uses [Azure Jumpstart ArcBox for IT Pros](https://jumpstart.azure.com/azure_jumpstart_arcbox/ITPro) — a self-contained sandbox that deploys an entire simulated on-prem datacenter inside a single Azure subscription. **13 out of 14 components run real** — no mocks, no fake data.

## What ArcBox Deploys

| VM Name | OS | Role | Simulates |
|---|---|---|---|
| **ArcBox-Client** | Windows Server 2022/2025 | Hyper-V host / jump box | Admin workstation |
| **ArcBox-Win2K22** | Windows Server 2022 | Application server | Typical Wintel workload |
| **ArcBox-Win2K25** | Windows Server 2025 | File server | Modern Windows server |
| **ArcBox-SQL** | Windows Server 2022 + SQL Server 2022 | Database server | SQL workload |
| **ArcBox-Ubuntu-01** | Ubuntu 22.04 LTS | Web server | Linux workload |
| **ArcBox-Ubuntu-02** | Ubuntu 22.04 LTS | Monitoring server | Linux workload |

All VMs are **automatically Arc-enrolled** with Azure Monitor Agent, Azure Policy, and Azure Update Manager.

## Demo Stack — What's Real vs. What's Swapped in Production

| Component | Demo Tool | Real? | Production Swap |
|---|---|---|---|
| Azure Arc (servers) | ArcBox VMs | ✅ Real | Same |
| Azure Monitor Agent | ArcBox built-in | ✅ Real | Same |
| Azure Update Manager | ArcBox built-in | ✅ Real | Same |
| Azure Policy / Guest Config | ArcBox built-in | ✅ Real | Same |
| Azure Resource Graph | ArcBox built-in | ✅ Real | Same |
| Arc Run Commands | ArcBox built-in | ✅ Real | Same |
| Azure Functions | Deploy to subscription | ✅ Real | Same |
| Azure AI Foundry Agents | Deploy to subscription | ✅ Real | Same |
| Azure SRE Agent | Deploy to subscription | ✅ Real | Same |
| Defender for Cloud | Toggle on for Arc servers | ✅ Real | Same (no adapter swap!) |
| Log Analytics / KQL | ArcBox built-in | ✅ Real | Same |
| **ITSM (ManageEngine)** | **GLPI** (open-source) | ✅ Real | Swap `glpi_adapter` → `manageengine_adapter` |
| **CMDB** | **GLPI** (built-in CMDB) | ✅ Real | Swap `glpi_cmdb_adapter` → `manageengine_cmdb_adapter` |
| **VMware management** | Hyper-V (ArcBox) / Arc-enabled VMware in production | ✅ Real | `arc_adapter` handles both |
| Accops | N/A | ❌ Skip | Slide-only |

## GLPI — Open-Source ITSM + CMDB

[GLPI](https://glpi-project.org/) is a production-grade open-source ITSM platform with a built-in CMDB module. It covers both ITSM ticketing and CMDB in a single deployment.

**Deployment:**
```bash
docker run -d --name glpi -p 8080:80 diouxx/glpi:latest
```

**Why GLPI:**
- REST API for all operations (tickets, CMDB CIs, SLAs)
- Covers 2 demo needs in 1 tool (ITSM + CMDB)
- Pre-seed CMDB with ArcBox server records + deliberate discrepancies for reconciliation demo
- Professional web UI visible during customer demos

**Adapter swap story:** "This is GLPI — a production-grade ITSM. In your environment, we swap one adapter for ManageEngine. Same REST pattern, different URL."

See [glpi-setup.md](glpi-setup.md) for detailed GLPI installation and configuration instructions.

## SRE Agent Access to ArcBox VMs

SRE Agent accesses Arc-enrolled VMs via its managed identity + RBAC:

```bash
# Grant SRE Agent access to ArcBox resource group
az role assignment create \
  --assignee <SRE_AGENT_MANAGED_IDENTITY_ID> \
  --role Contributor \
  --scope /subscriptions/<SUB_ID>/resourceGroups/<ARCBOX_RG>
```

This gives SRE Agent full access to: Resource Graph queries, Azure Monitor logs, Arc Run Commands, Defender for Cloud alerts, and Azure Update Manager.

## Setup Steps

```
Step 1: Deploy ArcBox for IT Pros
  └─ Bicep deployment → ~30 min → 6 VMs, all Arc-enrolled, monitoring active

Step 2: Enable Defender for Cloud + Deploy GLPI
  ├─ Enable Defender for Servers Plan 2 on ArcBox resource group
  ├─ Deploy GLPI via Docker on ArcBox-Client (~10 min)
  └─ Pre-seed GLPI CMDB with server records + deliberate discrepancies

Step 3: Deploy Solution Stack
  ├─ Azure Function App (Python) with all timer-triggered functions
  ├─ Azure AI Foundry project + agents (Compliance Analyst, Patch Risk, Ops Chat)
  ├─ Azure SRE Agent + subagents + skills + custom tools
  ├─ Adapters: arc, defender, glpi_itsm, glpi_cmdb, patch
  └─ Foundry Workflows (Patch Cycle, Daily Brief)

Step 4: Configure + Verify
  ├─ Azure Monitor alert rules (CPU, disk, heartbeat)
  ├─ Create Hyper-V checkpoints on VMs (for snapshot cleanup demo)
  ├─ Verify Defender compliance scans running
  └─ Verify SRE Agent can see all ArcBox VMs

Step 5: Run Demo Scenarios (all using REAL data — see demos/README.md for walkthroughs)
  ├─ Scenario A: Health check across all VMs → real report → AI summary
  ├─ Scenario B: Spike CPU + stop service → real alerts → SRE Agent triage → GLPI ticket
  ├─ Scenario C: Disable Defender agent → SRE Agent diagnoses via Arc Run Commands
  ├─ Scenario D: Defender compliance scan → real CIS report → AI executive summary
  ├─ Scenario E: Patch assessment → AI risk analysis → approval → deployment
  ├─ Scenario F: CMDB sync: GLPI CMDB vs Azure Resource Graph → real discrepancies
  └─ Scenario G: Snapshot cleanup → old checkpoints detected → auto-cleaned
```

## Estimated Cost

| Resource | Approx. Monthly Cost | Notes |
|---|---|---|
| ArcBox VMs (if left running) | ~$200–400/month | Use auto-shutdown; spin up only for demos |
| Defender for Cloud (Servers P2) | ~$90/month (6 VMs × $15) | 30-day free trial available |
| GLPI (Docker on ArcBox-Client) | $0 | Runs on existing VM |
| Azure Functions (Consumption) | ~$0–5/month | Near-free at demo scale |
| Azure AI Foundry (GPT-4o) | ~$5–20/month | Depends on demo frequency |
| Log Analytics | ~$5–15/month | Minimal data volume |
| **Total (demo days only)** | **~$50–80/month** | Shut down ArcBox VMs when not demoing |

## 45-Minute Demo Script

| Time | Segment | What You Show |
|---|---|---|
| 0–5 min | Problem statement | "Here's what your team does manually today, and where the time goes" |
| 5–10 min | Architecture overview | 3-tier diagram: Functions + SRE Agent + Foundry Agents |
| 10–20 min | **Live: Automation** | Health check → report; patching assessment; CMDB sync |
| 20–30 min | **Live: SRE Agent** | Alert storm → SRE Agent correlates → GLPI ticket. Stop Defender agent → SRE Agent diagnoses. |
| 30–35 min | **Live: Portal** | Dashboard, chat ("why did health check fail?"), create memory |
| 35–40 min | Adapter pattern | "Here's GLPI. Here's where ManageEngine plugs in. One config change." |
| 40–45 min | KPIs & Roadmap | Time savings, phase timeline, next steps |
