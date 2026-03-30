# Scenario G: Snapshot Cleanup — Implementation Comparison

> **Key message:** Not every scenario needs AI. This is a strength of the automation-first approach.

Snapshot and checkpoint cleanup is **90% deterministic automation** — discover checkpoints, check age against policy, delete old ones, keep recent ones. The PowerShell script handles this end to end. AI is entirely optional, useful only for the ~10% of edge cases where a checkpoint's context makes the delete-or-keep decision ambiguous.

## Overview

| Field | Value |
|---|---|
| **Automation coverage** | ~90% — fully handled by `scripts/demo-snapshot-cleanup.ps1` |
| **AI needed?** | ❌ No. Optional for edge-case judgment calls only. |
| **Duration** | ~3 minutes (automated) vs. ~30 minutes (manual) |
| **Scope** | Hyper-V checkpoint lifecycle — discovery, age analysis, cleanup |
| **Resource group** | `rg-arcbox-itpro` (Arc VMs, Sweden Central) |
| **Run from** | ArcBox-Client VM (Hyper-V host) or any machine (simulated mode) |
| **Script** | [`scripts/demo-snapshot-cleanup.ps1`](../../scripts/demo-snapshot-cleanup.ps1) |

## What Automation Handles (90%)

The PowerShell script performs the entire cleanup lifecycle without any AI involvement:

| Step | What It Does | How |
|---|---|---|
| **1. Discover VMs** | List all Hyper-V VMs and their checkpoints | `Get-VM` + `Get-VMCheckpoint` |
| **2. Age analysis** | Calculate checkpoint age, categorize by policy | Age vs. threshold (default: 7 days) |
| **3. Auto-delete old** | Remove checkpoints older than 3× threshold | `Remove-VMCheckpoint` (>21 days) |
| **4. Flag for review** | Checkpoints between 1× and 3× threshold | Listed in console output for human review |
| **5. Retain recent** | Keep checkpoints under threshold | No action needed |
| **6. Summary report** | Total counts by action category | Console output with color-coded table |

### Why This Doesn't Need AI

| Aspect | Why deterministic automation is sufficient |
|---|---|
| **Age calculation** | Simple date arithmetic — no interpretation needed |
| **Policy application** | Rule-based: `age > threshold × 3 → delete`, `age > threshold → review`, else keep |
| **Disk impact** | Checkpoint file sizes are queryable, no estimation needed |
| **Cleanup execution** | `Remove-VMCheckpoint` — deterministic, idempotent |
| **Reporting** | Template-based summary — no natural language generation needed |

### Running the Automation

```bash
# Run from ArcBox-Client (live) or any machine (simulated mode)
pwsh scripts/demo-snapshot-cleanup.ps1
```

Expected output:

```
╔══════════════════════════════════════════════════════════════════╗
║          DETERMINISTIC SNAPSHOT/CHECKPOINT CLEANUP              ║
║          Automation Coverage: ~90%                              ║
╚══════════════════════════════════════════════════════════════════╝

━━━ Step 2: Checkpoint Age Analysis ━━━

  ┌──────────────────────┬──────────────────────────────┬────────┬──────────┐
  │ VM                   │ Checkpoint                   │ Age    │ Action   │
  ├──────────────────────┼──────────────────────────────┼────────┼──────────┤
  │ ArcBox-SQL           │ Pre-migration snapshot       │ 45d    │ DELETE   │
  │ ArcBox-Win2K19       │ Before SQL update            │ 22d    │ DELETE   │
  │ ArcBox-Win2K22       │ Pre-patch 2024-12-01         │ 15d    │ REVIEW   │
  │ ArcBox-Ubuntu-01     │ Kernel update fallback       │ 10d    │ REVIEW   │
  │ ArcBox-Win2K19       │ Monthly backup               │ 8d     │ REVIEW   │
  │ ArcBox-Win2K22       │ Config change backup         │ 3d     │ KEEP     │
  │ ArcBox-SQL           │ Post-config test             │ 2d     │ KEEP     │
  └──────────────────────┴──────────────────────────────┴────────┴──────────┘

  ┌──────────────────────────────────────────────────────────────┐
  │ CHECKPOINT CLEANUP SUMMARY                                  │
  ├──────────────────────────────────────────────────────────────┤
  │ Total checkpoints found:    7                               │
  │ Auto-deleted (>21 days):    2                               │
  │ Flagged for review:         3                               │
  │ Retained (recent):          2                               │
  └──────────────────────────────────────────────────────────────┘
```

## The Ambiguous 10% — Where AI Could Optionally Help

The automation flags cases it cannot resolve with age alone:

- **Checkpoint tagged `do-not-delete`** — Is the tag still valid, or was it forgotten?
- **Checkpoint created before a migration** — Migration completed successfully, but is the rollback path still needed?
- **Checkpoint on a critical production VM** — Age says delete, but the VM's role warrants extra caution
- **Multiple checkpoints forming a chain** — Deleting a parent checkpoint affects children

These edge cases are currently handled by a human reviewing the "REVIEW" list. Each AI tier below shows how you *could* add optional intelligence — but for most teams, the review list is short enough to handle manually.

---

## Option 0: SRE Agent (Optional)

> **Effort:** ~30 min to add a skill for snapshot review guidance

The SRE Agent can review flagged checkpoints and provide context-aware recommendations by cross-referencing the checkpoint metadata with the VM's role and recent change history.

### Example Interaction

```
SRE Agent:
┌──────────────────────────────────────────────────────────────┐
│ 🔍 Snapshot Cleanup — Flagged Checkpoints Review             │
├──────────────────────────────────────────────────────────────┤
│ 3 checkpoints flagged for review:                            │
│                                                              │
│ 1. ArcBox-Win2K22 / "Pre-patch 2024-12-01" (15 days)        │
│    Context: Patch KB5034441 was applied successfully.         │
│    No rollback needed. Post-patch health check: PASS.        │
│    ✅ Recommendation: Safe to delete.                        │
│                                                              │
│ 2. ArcBox-Ubuntu-01 / "Kernel update fallback" (10 days)    │
│    Context: Kernel 5.15.0-91 → 5.15.0-94 applied.           │
│    VM has been stable for 10 days since update.              │
│    ✅ Recommendation: Safe to delete.                        │
│                                                              │
│ 3. ArcBox-Win2K19 / "Monthly backup" (8 days)               │
│    ⚠ Note: Tagged 'do-not-delete' in checkpoint metadata.   │
│    Tag was set 8 days ago. No associated change ticket.      │
│    🔶 Recommendation: Flag for owner review.                │
│                                                              │
│ Delete checkpoints #1 and #2?                                │
│ [Yes — delete both] [No — keep all] [Review individually]   │
└──────────────────────────────────────────────────────────────┘
```

### When to Use

Use SRE Agent when you have >10 flagged checkpoints per cleanup cycle or when VMs have complex change histories.

---

## Option A: Agent Framework (Optional)

> **Effort:** ~1 week to add function tools for checkpoint context analysis

Build a lightweight agent with tools that cross-reference checkpoint metadata against VM role, change history, and tag policies.

### Code Snippet

```python
from microsoft.agents import Agent, FunctionTool

@FunctionTool
def analyze_checkpoint_context(vm_name: str, checkpoint_name: str, age_days: int) -> dict:
    """Analyze whether a flagged checkpoint is safe to delete by checking
    VM role, recent changes, and checkpoint tags."""

    # Check if checkpoint has protective tags
    tags = get_checkpoint_tags(vm_name, checkpoint_name)
    has_do_not_delete = "do-not-delete" in [t.lower() for t in tags]

    # Check if the associated change was successful
    change_ticket = find_related_ticket(vm_name, checkpoint_name)
    change_succeeded = change_ticket and change_ticket.get("status") == "resolved"

    # Check VM stability since checkpoint creation
    health_since = get_vm_health_summary(vm_name, days=age_days)

    return {
        "vm": vm_name,
        "checkpoint": checkpoint_name,
        "age_days": age_days,
        "has_do_not_delete_tag": has_do_not_delete,
        "related_change_resolved": change_succeeded,
        "vm_stable_since": health_since.get("stable", False),
        "recommendation": (
            "flag_for_review" if has_do_not_delete
            else "safe_to_delete" if change_succeeded and health_since.get("stable")
            else "investigate"
        )
    }

@FunctionTool
def confirm_checkpoint_deletion(vm_name: str, checkpoint_name: str) -> str:
    """Require operator confirmation before deleting a checkpoint."""

    confirmation = input(
        f"Delete checkpoint '{checkpoint_name}' on {vm_name}? [y/N]: "
    )
    if confirmation.lower() == "y":
        return f"✅ Deletion confirmed for '{checkpoint_name}' on {vm_name}"
    return f"❌ Deletion cancelled — checkpoint retained"
```

---

## Option B: Foundry Agent Service (Optional)

> **Effort:** ~3–5 days to add a human-in-the-loop approval step

Azure AI Foundry can wrap the checkpoint review as a workflow that pauses for human approval, with context-enriched summaries sent via Teams or email.

### Workflow Definition

```yaml
# Foundry agent workflow step for checkpoint review
steps:
  - name: enrich_checkpoint_context
    tool: analyze_checkpoint
    inputs:
      vm_name: "{{ flagged_checkpoint.vm }}"
      checkpoint_name: "{{ flagged_checkpoint.name }}"
      age_days: "{{ flagged_checkpoint.age }}"

  - name: human_approval
    type: human-in-the-loop
    prompt: |
      Snapshot Cleanup flagged a checkpoint for review:

      VM: {{ flagged_checkpoint.vm }}
      Checkpoint: {{ flagged_checkpoint.name }}
      Age: {{ flagged_checkpoint.age }} days
      Tag: {{ steps.enrich_checkpoint_context.output.tag_status }}
      Related change: {{ steps.enrich_checkpoint_context.output.change_status }}
      VM stability: {{ steps.enrich_checkpoint_context.output.health_status }}

      Recommendation: {{ steps.enrich_checkpoint_context.output.recommendation }}

      Approve deletion?
    notify:
      - channel: teams
        webhook: "{{ env.TEAMS_WEBHOOK_URL }}"
    timeout: 24h

  - name: execute_deletion
    condition: "{{ steps.human_approval.approved }}"
    tool: remove_checkpoint
    inputs:
      vm_name: "{{ flagged_checkpoint.vm }}"
      checkpoint_name: "{{ flagged_checkpoint.name }}"
```

---

## Option C: GitHub Copilot CLI (Optional)

> **Effort:** ~1 hour to create an interactive terminal workflow

Run the cleanup script, then interactively ask Copilot about the flagged checkpoints in your terminal.

### Example Terminal Session

```bash
# Step 1: Run the automation
$ pwsh scripts/demo-snapshot-cleanup.ps1

# ... automation runs, flags 3 checkpoints for review ...
# [WARN]  REVIEW: 'Pre-patch 2024-12-01' on ArcBox-Win2K22 — 15 days old
# [WARN]  REVIEW: 'Kernel update fallback' on ArcBox-Ubuntu-01 — 10 days old
# [WARN]  REVIEW: 'Monthly backup' on ArcBox-Win2K19 — 8 days old (tagged do-not-delete)

# Step 2: Ask Copilot about the flagged checkpoints
$ copilot "I have 3 Hyper-V checkpoints flagged for review:
  1. ArcBox-Win2K22 'Pre-patch 2024-12-01' (15 days old)
  2. ArcBox-Ubuntu-01 'Kernel update fallback' (10 days old)
  3. ArcBox-Win2K19 'Monthly backup' (8 days, tagged do-not-delete)
  Check if the related patches/updates completed successfully and if
  these VMs have been stable. Are any safe to delete?"
```

Copilot response:

```
I'll check each one:

1. ArcBox-Win2K22 — "Pre-patch 2024-12-01" (15 days)
   The December patching completed successfully (KB5034441 installed,
   no reboot failures). VM has been stable since. ✅ Safe to delete.

2. ArcBox-Ubuntu-01 — "Kernel update fallback" (10 days)
   Kernel upgraded from 5.15.0-91 to 5.15.0-94. No kernel panics or
   service issues in the last 10 days. ✅ Safe to delete.

3. ArcBox-Win2K19 — "Monthly backup" (8 days, do-not-delete tag)
   ⚠ This checkpoint has a 'do-not-delete' tag. I can't determine
   who set it or why. Recommend checking with the VM owner before
   removing.

Want me to delete checkpoints 1 and 2?
  Remove-VMCheckpoint -VMName 'ArcBox-Win2K22' -Name 'Pre-patch 2024-12-01'
  Remove-VMCheckpoint -VMName 'ArcBox-Ubuntu-01' -Name 'Kernel update fallback'
```

---

## Comparison: When to Add AI (and When Not To)

| Criteria | Just Automation | Add AI |
|---|---|---|
| **Flagged checkpoints per cycle** | < 5 | > 10 regularly |
| **Protective tags used** | Rarely | Frequently (`do-not-delete`, `keep-until`) |
| **VM count** | < 20 | 50+ |
| **Checkpoint chaining** | Simple (no parent/child) | Complex chains |
| **Change management maturity** | Tickets always closed | Tickets sometimes stale |

### AI Tier Comparison for Optional 10%

| Aspect | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|
| **Setup effort** | ~30 min (skill) | ~1 week (code) | ~3–5 days | ~1 hour |
| **Automation** | Scheduled pickup | Triggered by script | HTTP trigger + workflow | Manual, interactive |
| **Context analysis** | Built-in (queries Arc, Log Analytics) | Custom function tools | Function tools + HITL | Terminal commands |
| **Human approval** | Chat confirmation | `input()` prompt | Built-in HITL step | Terminal dialogue |
| **Best for** | Teams already using SRE Agent | Need custom delete logic | Need audit trail | Ad-hoc review |

## Talking Points

| Point | Script |
|---|---|
| **"Not everything needs AI"** | "Snapshot cleanup is rule-based: age threshold → delete or keep. This is what PowerShell scripts have done for decades. No LLM needed." |
| **Automation-first maturity** | "A mature ops team knows when to use AI and when simple automation is better. Adding GPT to a date comparison is over-engineering." |
| **The 90/10 split** | "90% is purely deterministic — age check, policy match, delete or keep. The 10% edge cases (tagged checkpoints, pre-migration snapshots) are rare enough that a human glancing at the review list is perfectly fine." |
| **Optional AI for scale** | "If you're managing hundreds of VMs with complex checkpoint chains and protective tags, *then* adding AI context analysis starts to pay for itself. For most teams, it's overkill." |
| **Disk savings are real** | "Even without AI, the automation reclaims disk space that manual processes leave sitting for months. The value is in *running consistently*, not in *running intelligently*." |

## Expected Output

| Artifact | Location |
|---|---|
| Hyper-V VM and checkpoint inventory | Console output from `scripts/demo-snapshot-cleanup.ps1` |
| Age analysis table (DELETE / REVIEW / KEEP) | Console output with color-coded table |
| Auto-deleted checkpoint confirmations | Console output (or Hyper-V event log) |
| Flagged checkpoints for human review | Console output — "REVIEW" category |
| Cleanup summary report | Console output — totals by action category |

## See Also

- [Scenario G demo walkthrough](../demos/scenario-g-snapshot-cleanup.md) — full demo with expected output
- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [`scripts/demo-snapshot-cleanup.ps1`](../../scripts/demo-snapshot-cleanup.ps1) — the automation script
