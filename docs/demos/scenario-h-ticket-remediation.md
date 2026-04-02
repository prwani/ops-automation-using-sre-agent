# Scenario H — Ticket-Driven Remediation (Closed-Loop ITSM)

**Automation coverage:** 30% deterministic (ticket routing, status updates)  
**AI value-add:** 70% (ticket triage, investigation, contextual resolution)

---

## Overview

This scenario demonstrates the **closed-loop** pattern: an ITSM ticket arrives →
the AI agent reads it → investigates using Azure Arc / Defender / Log Analytics →
writes findings back to the ticket → resolves or escalates.

This is where AI agents provide the most value — **autonomous triage and
resolution** of routine operations tickets that would otherwise sit in a queue
waiting for an L2/L3 engineer.

### Why This Matters

| Metric | Without AI Agent | With AI Agent |
|--------|-----------------|---------------|
| Mean time to acknowledge | 30–60 min (human queue) | < 2 min (auto-read) |
| Investigation time | 15–45 min per ticket | 2–5 min per ticket |
| CMDB updates | Manual, often forgotten | Auto-corrected from source of truth |
| Ticket quality | Varies by engineer | Consistent, structured findings |

---

## Prerequisites

1. **GLPI running** — Start the container if stopped:
   ```bash
   az container start --resource-group rg-opsauto-sc --name glpi-opsauto-demo
   ```

2. **Arc servers connected** — Start ArcBox if needed:
   ```bash
   az vm start --resource-group rg-arcbox-itpro --name ArcBox-Client
   ```
   Wait 5 minutes for nested VMs to reconnect to Arc.

3. **GLPI OAuth credentials** — Client ID and Secret from Setup > OAuth Clients.

4. **Copilot CLI** (or SRE Agent) with the `ticket-driven-remediation` skill available.

---

## Phase 1 — Seed Sample Tickets (Deterministic)

Run the seed script to create realistic tickets in GLPI:

```powershell
.\scripts\seed-glpi-tickets.ps1 `
  -ClientId "YOUR_CLIENT_ID" `
  -ClientSecret "YOUR_CLIENT_SECRET" `
  -Password "YOUR_GLPI_PASSWORD"
```

This creates 4 tickets:

| # | Title | Type | Priority |
|---|-------|------|----------|
| 1 | `[CMDB] ArcBox-Win2K25 OS mismatch` | CMDB Update | Medium |
| 2 | `[Health] Investigate high CPU on ArcBox-Win2K22` | Health Check | High |
| 3 | `[Security] Verify MDE on all Linux servers` | Security Agent | Medium |
| 4 | `[Compliance] Monthly MCSB posture review` | Compliance | Low |

Verify in GLPI UI: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.php`

---

## Phase 2 — AI Agent Processes Tickets

### Option A: GitHub Copilot CLI

```bash
copilot -p "Use the /ticket-driven-remediation skill. Connect to GLPI at http://glpi-opsauto-demo.swedencentral.azurecontainer.io using client_id=YOUR_CLIENT_ID, client_secret=YOUR_CLIENT_SECRET, username=glpi, password=YOUR_PASSWORD. Read all open tickets, investigate each one using Azure Arc and Defender for Cloud, update each ticket with your findings, and mark resolved tickets as Solved." --allow-all-tools
```

### Option B: Azure SRE Agent

1. Upload the `ticket-driven-remediation` skill to your SRE Agent.
2. Register the GLPI Python tools (`glpi-list-open-tickets`, `glpi-add-followup`, `glpi-update-computer`).
3. Create a scheduled task to run every 15 minutes:
   - **Trigger**: Schedule (every 15 min)
   - **Skill**: ticket-driven-remediation
   - **Prompt**: "Process all open Wintel Ops tickets"

### Option C: Microsoft Agent Framework

```python
from azure.identity import DefaultAzureCredential
from agentskills import SkillsProvider

skills = SkillsProvider(skill_paths=["sre-skills/ticket-driven-remediation"])
# Invoke via LangChain/Semantic Kernel agent with GLPI credentials in env
```

---

## Expected Behavior

### Ticket 1: CMDB Update (ArcBox-Win2K25)

1. Agent reads ticket → classifies as **CMDB Update**
2. Queries Azure Resource Graph for `ArcBox-Win2K25` → finds OS = Windows Server 2025
3. Queries GLPI CMDB → finds recorded OS = Windows Server 2022
4. **Detects mismatch** → Updates GLPI computer record with correct OS
5. Adds followup to ticket: "CMDB corrected: OS updated from 2022 to 2025"
6. Marks ticket **Solved** ✅

### Ticket 2: Health Investigation (ArcBox-Win2K22)

1. Agent reads ticket → classifies as **Health Investigation**
2. Queries Log Analytics for CPU, memory, disk on ArcBox-Win2K22
3. Finds CPU at ~30% avg (normal), memory at ~60% (normal), disk at 75% free (normal)
4. Adds followup: "Investigation complete — all metrics normal. CPU spike may have been transient."
5. Marks ticket **Solved** ✅

### Ticket 3: Security Agent Check (Linux servers)

1. Agent reads ticket → classifies as **Security Agent Check**
2. Queries Resource Graph for MDE extensions on Linux servers
3. Finds MDE.Linux installed on both Ubuntu servers, provisioning Succeeded
4. Adds followup: "MDE agent verified on 2/2 Linux servers. All healthy."
5. Marks ticket **Solved** ✅

### Ticket 4: Compliance Review

1. Agent reads ticket → classifies as **Compliance Review**
2. Queries Defender for Cloud regulatory compliance
3. Lists failing controls with P1-P4 priority
4. Adds followup with compliance summary table
5. If P1/P2 findings exist → leaves ticket **Open** for human review
6. If no critical findings → marks ticket **Solved**

---

## What Makes This a Compelling Demo

| Aspect | Why It Impresses |
|--------|-----------------|
| **Reads natural language** | Agent understands ticket intent without rigid templates |
| **Classifies automatically** | No routing rules needed — AI determines the right action |
| **Investigates with real data** | Queries actual Azure resources, not mock data |
| **Updates the ticket** | Closes the loop — ticket has evidence, not just "acknowledged" |
| **Handles multiple types** | Same skill processes CMDB, health, security, and compliance tickets |
| **Auto-resolves routine work** | L2/L3 engineers only see tickets that truly need human judgment |

---

## Comparison: Rule-Based vs AI Agent

| Capability | Rule-Based Automation | AI Agent |
|-----------|----------------------|----------|
| Read tickets | ✅ Parse structured fields | ✅ Understand free-text descriptions |
| Classify tickets | ⚠️ Keyword matching only | ✅ Semantic understanding of intent |
| Investigate | ⚠️ Fixed script per category | ✅ Adapts investigation to context |
| Handle ambiguity | ❌ Fails on unclear tickets | ✅ Makes reasonable inferences |
| Write findings | ⚠️ Template-based output | ✅ Contextual, human-readable summary |
| Learn from patterns | ❌ Static rules | ✅ Can reference previous similar tickets |

---

## Extending This Pattern

### Add More Ticket Types

Edit the classification rules in Step 3 of the SKILL.md:

```markdown
| "disk full", "storage", "volume" | **Storage Remediation** | Check disk usage, identify large files, clean temp |
| "backup", "restore", "recovery" | **Backup Verification** | Check Azure Backup vault status |
| "certificate", "expiry", "SSL" | **Certificate Management** | Check cert expiry dates |
```

### Schedule for Continuous Processing

With SRE Agent, create a scheduled task that runs every 15 minutes:
- Read new tickets since last run
- Process and update
- Report summary to Teams channel

### Integrate with ServiceNow / ManageEngine

Replace GLPI API calls with the equivalent ITSM API:
- ServiceNow: `GET /api/now/table/incident?sysparm_query=state=1`
- ManageEngine: `GET /api/v3/requests?input_data={"list_info":{"filter_by":[{"field":"status.name","condition":"is","value":"Open"}]}}`

The investigation logic (Azure Arc, Defender, Log Analytics) stays identical.
