# Scenario F: CMDB Sync — Implementation Comparison

> **Key message:** Not every scenario needs AI. This is a strength of the automation-first approach.

CMDB synchronization is **85% deterministic automation** — query Azure Resource Graph, compare with GLPI, update matches, flag differences. The PowerShell script handles this end to end. AI is entirely optional, useful only for the ambiguous ~15% where a server exists in one system but not the other and the reason is unclear.

## Overview

| Field | Value |
|---|---|
| **Automation coverage** | ~85% — fully handled by `scripts/demo-cmdb-sync.ps1` |
| **AI needed?** | ❌ No. Optional for ambiguous edge cases only. |
| **Duration** | ~5 minutes (automated) vs. ~2 hours (manual) |
| **Scope** | Sync Azure Resource Graph inventory → GLPI CMDB |
| **Resource group** | `rg-arcbox-itpro` (Arc VMs, Sweden Central) |
| **ITSM** | GLPI — `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **Script** | [`scripts/demo-cmdb-sync.ps1`](../../scripts/demo-cmdb-sync.ps1) |

## What Automation Handles (85%)

The PowerShell script performs the entire sync without any AI involvement:

| Step | What It Does | How |
|---|---|---|
| **1. Query Azure** | Pull current inventory from Resource Graph | `az graph query` — name, OS, status, agent version |
| **2. Query GLPI** | Pull registered computers from CMDB | GLPI REST API (`/apirest.php/Computer`) |
| **3. Set comparison** | Find matches, Azure-only, GLPI-only | Name-based matching — simple set difference |
| **4. Auto-update matches** | Sync attributes for exact matches | `PUT /apirest.php/Computer/{id}` with Azure data |
| **5. Flag discrepancies** | Report mismatches for human review | OS version differs, status differs, etc. |

### Why This Doesn't Need AI

| Aspect | Why deterministic automation is sufficient |
|---|---|
| **Data comparison** | Simple set difference — no interpretation needed |
| **Exact matches** | Name-based matching with attribute diff is trivial |
| **Update logic** | If name matches and attribute changed → update. No judgment required. |
| **Ambiguous cases** | Flagged for humans, not guessed at by AI |
| **Reporting** | Template-based output, no natural language generation needed |

### Running the Automation

```bash
# Run from any machine with az CLI authenticated
pwsh scripts/demo-cmdb-sync.ps1
```

Expected output:

```
╔══════════════════════════════════════════════════════════════════╗
║          DETERMINISTIC CMDB SYNC AUTOMATION                     ║
║          Automation Coverage: ~85%                              ║
╚══════════════════════════════════════════════════════════════════╝

━━━ Step 3: Comparing Azure (truth) vs. GLPI (record) ━━━

  ┌────────────────────────────────────────────────────────────────┐
  │ RECONCILIATION RESULTS                                        │
  ├────────────────────────────────────────────────────────────────┤
  │ Matched (in both Azure and GLPI): 4                           │
  │ In Azure only (missing from GLPI): 1                          │
  │ In GLPI only (not in Azure):       1                          │
  │ Discrepancies in matched records:  1                          │
  └────────────────────────────────────────────────────────────────┘

━━━ Step 5: Flagging ambiguous cases for human review ━━━

  ⚠ Items requiring human review:
  [WARN]  OldServer-Decomm: In GLPI but not in Azure — decommissioned or renamed?
```

## The Ambiguous 15% — Where AI Could Optionally Help

The automation flags cases it cannot resolve deterministically:

- **Server in GLPI but not in Azure** — Was it decommissioned, renamed, or migrated?
- **Server in Azure but not in GLPI** — Is it newly provisioned, or was the CMDB entry accidentally deleted?
- **OS mismatch** — Is the GLPI record stale, or was the server rebuilt?

These cases are rare and **currently handled by a human reviewer**. Each AI tier below shows how you *could* add optional intelligence — but for most teams, the human review queue is perfectly adequate.

---

## Option 0: SRE Agent (Optional)

> **Effort:** ~30 min to add a skill for CMDB ambiguity resolution

The SRE Agent can be given a lightweight skill that fires when the automation script flags ambiguous cases. The agent reviews the evidence and asks the operator for confirmation.

### How It Works

1. Automation script runs on schedule and writes ambiguous cases to a shared log or GLPI ticket
2. SRE Agent picks up the flagged items via a scheduled task or alert trigger
3. Agent investigates (checks Azure Activity Log for delete/rename events) and prompts the operator

### Example Interaction

```
SRE Agent:
┌──────────────────────────────────────────────────────────────┐
│ 🔍 CMDB Sync — Ambiguous Case                               │
├──────────────────────────────────────────────────────────────┤
│ Server: OldServer-Decomm                                     │
│ Status: In GLPI but NOT in Azure Resource Graph              │
│                                                              │
│ Investigation:                                               │
│  • No delete event in Azure Activity Log (last 90 days)      │
│  • No rename event found                                     │
│  • Last GLPI update: 47 days ago                             │
│  • GLPI comment: "Decommissioned?"                           │
│                                                              │
│ Assessment: Likely decommissioned before Arc enrollment.     │
│                                                              │
│ Should I remove OldServer-Decomm from GLPI CMDB?            │
│ [Yes — mark as decommissioned] [No — keep for review]       │
└──────────────────────────────────────────────────────────────┘
```

### When to Use

Use SRE Agent only if you have frequent ambiguous cases (>5 per sync cycle) and want to reduce the human review queue.

---

## Option A: Agent Framework (Optional)

> **Effort:** ~1 week to add a function tool with confirmation prompt

Build a lightweight agent with a single `resolve_cmdb_ambiguity` function tool that wraps the Activity Log check and presents a confirmation prompt.

### Architecture

```
scripts/demo-cmdb-sync.ps1
        │
        ▼ (writes ambiguous cases to JSON)
cmdb_ambiguity_agent.py
        │
        ├── resolve_cmdb_ambiguity()   ← FunctionTool
        │     • Checks Azure Activity Log for delete/rename
        │     • Queries GLPI for last-update timestamp
        │     • Returns evidence summary
        │
        └── confirm_cmdb_action()      ← FunctionTool
              • Presents recommendation to operator
              • Requires explicit confirmation before updating GLPI
```

### Code Snippet

```python
from microsoft.agents import Agent, FunctionTool

@FunctionTool
def resolve_cmdb_ambiguity(server_name: str, issue_type: str) -> dict:
    """Check Azure Activity Log and GLPI history to determine
    if a CMDB discrepancy is a decommission, rename, or error."""

    # Check Azure Activity Log for resource delete/rename events
    activity = subprocess.run(
        ["az", "monitor", "activity-log", "list",
         "--resource-group", "rg-arcbox-itpro",
         "--offset", "90d",
         "--query", f"[?contains(resourceId, '{server_name}')]"],
        capture_output=True, text=True
    )

    events = json.loads(activity.stdout) if activity.returncode == 0 else []
    delete_events = [e for e in events if "delete" in e.get("operationName", {}).get("value", "").lower()]
    rename_events = [e for e in events if "rename" in e.get("operationName", {}).get("value", "").lower()]

    return {
        "server": server_name,
        "delete_events": len(delete_events),
        "rename_events": len(rename_events),
        "recommendation": "decommissioned" if not delete_events and not rename_events else "investigate",
        "confidence": "high" if len(events) == 0 else "medium"
    }

@FunctionTool
def confirm_cmdb_action(server_name: str, action: str) -> str:
    """Require operator confirmation before modifying CMDB.
    action: 'remove' | 'keep' | 'flag'"""

    confirmation = input(f"Confirm {action} for {server_name}? [y/N]: ")
    if confirmation.lower() == "y":
        # Execute the GLPI update
        return f"✅ {action} confirmed for {server_name}"
    return f"❌ Action cancelled for {server_name}"
```

---

## Option B: Foundry Agent Service (Optional)

> **Effort:** ~3–5 days to add a human-in-the-loop workflow step

Azure AI Foundry can wrap the ambiguity resolution as a workflow step that pauses for human approval before modifying CMDB records.

### How It Works

1. Automation script outputs ambiguous cases as a JSON payload
2. Foundry agent receives the payload via HTTP trigger
3. Agent investigates using function tools (Activity Log, GLPI API)
4. **Human-in-the-loop step**: Agent pauses and sends a Teams/email approval request
5. On approval, agent executes the CMDB update

### Workflow Definition

```yaml
# Foundry agent workflow step for CMDB ambiguity
steps:
  - name: investigate_discrepancy
    tool: check_activity_log
    inputs:
      server_name: "{{ ambiguous_case.server }}"
      resource_group: "rg-arcbox-itpro"

  - name: human_approval
    type: human-in-the-loop
    prompt: |
      CMDB Sync found a discrepancy:

      Server: {{ ambiguous_case.server }}
      Issue: {{ ambiguous_case.issue }}
      Investigation: {{ steps.investigate_discrepancy.output.summary }}

      Recommended action: {{ steps.investigate_discrepancy.output.recommendation }}

      Please approve or reject this action.
    notify:
      - channel: teams
        webhook: "{{ env.TEAMS_WEBHOOK_URL }}"
    timeout: 24h

  - name: execute_action
    condition: "{{ steps.human_approval.approved }}"
    tool: update_glpi_computer
    inputs:
      computer_id: "{{ ambiguous_case.glpi_id }}"
      action: "{{ steps.investigate_discrepancy.output.recommendation }}"
```

---

## Option C: GitHub Copilot CLI (Optional)

> **Effort:** ~1 hour to create an interactive terminal workflow

Copilot CLI is the simplest option — run the automation script, then interactively ask Copilot about the flagged cases right in your terminal.

### Example Terminal Session

```bash
# Step 1: Run the automation
$ pwsh scripts/demo-cmdb-sync.ps1

# ... automation runs, flags ambiguous cases ...
# ⚠ OldServer-Decomm: In GLPI but not in Azure — decommissioned or renamed?

# Step 2: Ask Copilot about the flagged case
$ copilot "OldServer-Decomm is in our GLPI CMDB but not in Azure Resource Graph.
  Check the Azure Activity Log for any delete or rename events for this server
  in rg-arcbox-itpro over the last 90 days. Should I remove it from CMDB?"
```

Copilot response:

```
I checked the Azure Activity Log for rg-arcbox-itpro (last 90 days):

  • No delete events for "OldServer-Decomm"
  • No rename events found
  • No resource with a similar name exists in Azure

This server was likely decommissioned before Azure Arc was set up, or it
was never enrolled. Since there's no Azure-side record, it's safe to mark
as decommissioned in GLPI.

Want me to run the GLPI API call to update the status?
  az rest --method PUT \
    --url "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Computer/5" \
    --body '{"input": {"comment": "Decommissioned — not in Azure Resource Graph"}}'
```

---

## Comparison: When to Add AI (and When Not To)

| Criteria | Just Automation | Add AI |
|---|---|---|
| **Ambiguous cases per sync** | < 5 | > 5 regularly |
| **Team has CMDB admin** | ✅ Reviews flags manually | ❌ No dedicated reviewer |
| **Sync frequency** | Weekly | Daily or continuous |
| **Environment size** | < 50 servers | 100+ servers |
| **Rename/migration frequency** | Rare | Frequent |

### AI Tier Comparison for Optional 15%

| Aspect | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|
| **Setup effort** | ~30 min (skill) | ~1 week (code) | ~3–5 days | ~1 hour |
| **Automation** | Scheduled pickup | Triggered by script | HTTP trigger + workflow | Manual, interactive |
| **Human approval** | Chat confirmation | `input()` prompt | Built-in HITL step | Terminal dialogue |
| **Best for** | Teams already using SRE Agent | Need custom logic | Need audit trail | Ad-hoc review |

## Talking Points

| Point | Script |
|---|---|
| **"Not everything needs AI"** | "CMDB sync is a solved problem. Set comparison, API calls, attribute matching — this is what scripts have done for decades. The value is in the *integration* (Resource Graph ↔ GLPI), not in AI." |
| **Automation-first maturity** | "A mature ops team knows when to use AI and when simple automation is better. Reaching for AI on a CMDB sync is over-engineering." |
| **The 85/15 split** | "85% is purely deterministic — exact matches, attribute updates, new-server additions. The 15% ambiguous cases (server disappeared — why?) are rare enough that a human reviewer is fine." |
| **Optional AI for scale** | "If you're managing 500+ servers with frequent renames and migrations, *then* adding an AI layer for the ambiguous cases starts to pay for itself. For most teams, it's overkill." |
| **Same script, any ITSM** | "This is GLPI, but the pattern is identical for ServiceNow, ManageEngine, or Jira Service Management. Swap the REST adapter, keep the logic." |

## Expected Output

| Artifact | Location |
|---|---|
| Azure Resource Graph inventory | `az graph query` output |
| GLPI CMDB computer list | GLPI REST API response |
| Reconciliation report (matches, gaps, discrepancies) | Console output from `scripts/demo-cmdb-sync.ps1` |
| Auto-updated GLPI records | GLPI → Assets → Computers |
| Ambiguous cases flagged for review | Console output (or GLPI ticket if integrated) |

## See Also

- [Scenario F demo walkthrough](../demos/scenario-f-cmdb-sync.md) — full demo with expected output
- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [`scripts/demo-cmdb-sync.ps1`](../../scripts/demo-cmdb-sync.ps1) — the automation script
