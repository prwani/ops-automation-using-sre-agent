# Scenario F: CMDB Sync — Option C: GitHub Copilot CLI

> **Effort:** ~1 hour · **AI involvement:** Optional, ~15% of cases · **Core sync:** Fully automated

## Overview

CMDB synchronization is **85% deterministic automation** — set comparison, attribute matching, and API calls. No AI is needed for the core sync. GitHub Copilot CLI is an optional lightweight add-on for the ~15% of cases the automation script flags as ambiguous (servers that disappeared, naming mismatches, unresolvable duplicates).

**This is not an AI scenario.** The script does the real work. Copilot CLI is a convenience for reviewing edge cases interactively in your terminal.

---

## Step 1: Run the Automation

The full sync runs without any AI involvement:

```bash
$ pwsh scripts/demo-cmdb-sync.ps1
```

The script:

1. Queries **Azure Resource Graph** for all Arc-enabled servers
2. Queries **GLPI REST API** for all computer CIs
3. Performs a **deterministic diff** — matches by hostname, flags gaps
4. **Auto-updates** GLPI for exact matches (OS version, IP, status)
5. **Auto-creates** GLPI CIs for new servers found in Azure
6. **Flags ambiguous cases** for human review (the ~15%)

The 85% that matches cleanly is handled automatically. No LLM, no tokens, no latency.

---

## Step 2: When Copilot CLI Helps (The ~15%)

After the script finishes, you'll see flagged cases in the console output. Use Copilot CLI to investigate interactively.

### Example: Server not found in Azure

```
⚠ REVIEW: OLD-SERVER-01 — In GLPI but not in Azure Resource Graph
```

```bash
$ copilot "The CMDB sync flagged OLD-SERVER-01 as 'not found in Resource Graph'.
  Check the Azure Activity Log in rg-arcbox-itpro for any delete or rename
  events in the last 90 days. Should I mark it decommissioned or investigate further?"
```

Copilot checks the activity log and responds with a recommendation — decommission, investigate, or escalate.

### Example: New servers without CMDB entries

```
⚠ REVIEW: 2 servers in Azure not found in GLPI — ArcBox-NewSQL, ArcBox-NewWeb
```

```bash
$ copilot "Two new servers appeared in Resource Graph that aren't in CMDB:
  ArcBox-NewSQL (Standard_D4s_v3, SQL Server 2022) and ArcBox-NewWeb
  (Standard_B2ms, Windows Server 2022). Help me create the right CI records
  with correct categories and business impact fields for GLPI."
```

Copilot generates the GLPI API calls with appropriate CI attributes pre-filled.

### Example: Naming mismatch

```bash
$ copilot "GLPI has 'PROD-DB-01' but Azure has 'arcbox-prod-db-01'.
  Are these the same server? Check if the IP addresses or OS details match."
```

---

## Why AI Isn't Needed for the Core Sync

| Aspect | Why automation is sufficient |
|---|---|
| **Matching logic** | Hostname comparison is deterministic — no ambiguity |
| **Attribute updates** | OS version, IP, RAM are factual — copy from source of truth |
| **New server creation** | Template-based CI creation — fill fields from Resource Graph |
| **Auditability** | Script produces a clear diff log — easier to audit than AI reasoning |
| **Reliability** | No hallucination risk, no token costs, no API rate limits |

The 15% ambiguous cases (disappeared servers, naming mismatches) genuinely benefit from contextual investigation — but they're rare enough that a human reviewer or an optional Copilot CLI session handles them fine.

---

## Comparison Table

| Criteria | Just Automation | Add Copilot CLI |
|---|---|---|
| **Setup** | Run script | Run script + ask questions |
| **Ambiguous cases** | Review manually | Ask Copilot interactively |
| **Effort** | ~0 (scheduled) | ~10 min per flagged batch |
| **Best for** | < 5 ambiguous cases/sync | Want faster triage of flags |
| **Requires** | PowerShell, Azure CLI, GLPI API | + GitHub Copilot CLI installed |

### When to Consider a Heavier AI Tier

| Criteria | Copilot CLI is fine | Consider SRE Agent / Foundry |
|---|---|---|
| **Ambiguous cases per sync** | < 5 | > 5 regularly |
| **Sync frequency** | Weekly | Daily or continuous |
| **Environment size** | < 50 servers | 100+ servers |
| **Rename/migration frequency** | Rare | Frequent |

---

## See Also

- [Scenario F full guide](../scenario-f-cmdb-sync.md) — all options including SRE Agent and Agent Framework
- [`scripts/demo-cmdb-sync.ps1`](../../../scripts/demo-cmdb-sync.ps1) — the automation script
