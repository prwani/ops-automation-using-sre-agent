# Scenario G: Snapshot Cleanup — Option C: GitHub Copilot CLI

> **Effort:** ~1 hour · **AI involvement:** Optional, ~10% of cases · **Core cleanup:** Fully automated

## Overview

Snapshot/checkpoint cleanup is **90% deterministic automation** — age threshold checks, policy matching, and bulk deletion. No AI is needed for the core cleanup. GitHub Copilot CLI is an optional lightweight add-on for the ~10% of checkpoints the script flags for review (protective tags, pre-migration snapshots, ambiguous ownership).

**This is not an AI scenario.** The script does the real work. Copilot CLI is a convenience for reviewing flagged checkpoints interactively in your terminal.

---

## Step 1: Run the Automation

The full cleanup runs without any AI involvement:

```bash
$ pwsh scripts/demo-snapshot-cleanup.ps1
```

The script:

1. Inventories all **Hyper-V VM checkpoints** across managed hosts
2. Applies **age-based rules** — delete if older than threshold, keep if recent
3. Respects **protective tags** (`do-not-delete`, `keep-until-<date>`)
4. **Auto-deletes** checkpoints that clearly meet the age threshold
5. **Flags checkpoints** that need human review (the ~10%)

The 90% that meets clear age rules is handled automatically. No LLM, no tokens, no latency.

---

## Step 2: When Copilot CLI Helps (The ~10%)

After the script finishes, you'll see flagged checkpoints in the console output. Use Copilot CLI to investigate interactively.

### Example: Old checkpoint with a meaningful name

```
⚠ REVIEW: 'pre-migration' on ArcBox-SQL — 30 days old
```

```bash
$ copilot "The cleanup script flagged a 30-day-old checkpoint on ArcBox-SQL
  tagged 'pre-migration'. Check if there's an active migration ticket in GLPI
  and whether ArcBox-SQL has been stable since. Is it safe to delete?"
```

Copilot checks GLPI for related tickets and VM health, then recommends delete or keep.

### Example: Deciding between ticket and delete

```
⚠ REVIEW: 'kernel-update-fallback' on ArcBox-Ubuntu-01 — 21 days old
```

```bash
$ copilot "Should I create a GLPI ticket to track this stale checkpoint on
  ArcBox-Ubuntu-01, or just delete it? The kernel update was 21 days ago.
  Check if the current kernel is stable and no rollback was needed."
```

Copilot checks the VM's current kernel version and uptime, then advises.

### Example: Checkpoint with protective tag

```
⚠ REVIEW: 'Monthly backup' on ArcBox-Win2K19 — 8 days old (tagged do-not-delete)
```

```bash
$ copilot "ArcBox-Win2K19 has a checkpoint tagged 'do-not-delete' from 8 days ago.
  Who set this tag and is there a corresponding change ticket? Should I
  respect it or escalate to the VM owner?"
```

---

## Why AI Isn't Needed for the Core Cleanup

| Aspect | Why automation is sufficient |
|---|---|
| **Age check** | Date arithmetic is deterministic — no ambiguity |
| **Policy matching** | Threshold rules are simple if/else logic |
| **Bulk deletion** | PowerShell `Remove-VMCheckpoint` is reliable and scriptable |
| **Auditability** | Script logs every action — easier to audit than AI reasoning |
| **Reliability** | No hallucination risk — a date comparison never gets "creative" |

The 10% flagged cases (protective tags, meaningful names like "pre-migration") genuinely benefit from context — but they're rare enough that a human reviewer or an optional Copilot CLI session handles them fine.

---

## Comparison Table

| Criteria | Just Automation | Add Copilot CLI |
|---|---|---|
| **Setup** | Run script | Run script + ask questions |
| **Flagged checkpoints** | Review manually | Ask Copilot interactively |
| **Effort** | ~0 (scheduled) | ~5 min per flagged batch |
| **Best for** | < 5 flagged per cycle | Want faster triage of flags |
| **Requires** | PowerShell, Hyper-V module | + GitHub Copilot CLI installed |

### When to Consider a Heavier AI Tier

| Criteria | Copilot CLI is fine | Consider SRE Agent / Foundry |
|---|---|---|
| **Flagged checkpoints per cycle** | < 5 | > 10 regularly |
| **Protective tags used** | Rarely | Frequently |
| **VM count** | < 20 | 50+ |
| **Checkpoint chaining** | Simple | Complex parent/child chains |

---

## See Also

- [Scenario G full guide](../scenario-g-snapshot-cleanup.md) — all options including SRE Agent and Agent Framework
- [`scripts/demo-snapshot-cleanup.ps1`](../../../scripts/demo-snapshot-cleanup.ps1) — the automation script
