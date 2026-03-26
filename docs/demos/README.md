# Demo Scenarios

## Philosophy: Automation First, AI Where Needed

These seven demos showcase a pragmatic approach to Wintel operations automation:
**deterministic automation is always the first choice — AI is introduced only where
automation hits a genuine ceiling** (correlation, diagnosis, prioritization).

Every scenario follows the same 2-tier architecture:

```
Tier 2  │  Azure SRE Agent          – incident response + analysis, where human judgment is needed
Tier 1  │  PowerShell Scripts         – deterministic automation (scripts/demo-*.ps1)
        └──────────────────────────────────────────────────────────────────────
           Adapter Layer (Arc · Defender · GLPI ITSM/CMDB · Update Manager)
```

The goal is not to "add AI to everything" — it is to **eliminate toil first**, then
let AI handle the genuinely ambiguous remainder. Two of the seven scenarios (F and G)
prove the point: they run at 100 % automation with zero AI, because the problem is
fully deterministic.

---

## Scenario Overview

| Scenario | Name | Automation | AI | File | Description |
|----------|------|:----------:|:--:|------|-------------|
| **A** | Daily Health Check | 90 % | 10 % | [`scenario-a-health-check.md`](scenario-a-health-check.md) | Collect disk, CPU, memory, services, and event-log metrics across Arc-enrolled servers; AI correlates cross-server anomalies into a daily brief. |
| **B** | Alert Triage & Ticket Creation | 70 % | 30 % | [`scenario-b-alert-triage.md`](scenario-b-alert-triage.md) | Route Azure Monitor alerts through SRE Agent for correlation and root-cause context, then auto-create GLPI tickets with proper severity. |
| **C** | Security Agent Troubleshooting | 60 % | 40 % | [`scenario-c-security-agent.md`](scenario-c-security-agent.md) | Auto-restart unhealthy Defender for Cloud agents; SRE Agent diagnoses the ~40 % of cases that need contextual reasoning (event logs, dependencies, KB correlations). |
| **D** | Compliance Reporting | 95 % | 5 % | [`scenario-d-compliance.md`](scenario-d-compliance.md) | Pull Defender for Cloud + Azure Policy CIS benchmark data and generate HTML/PDF reports; AI adds an executive narrative with trend analysis and prioritisation. |
| **E** | Monthly Patching | 85 % | 15 % | [`scenario-e-patching.md`](scenario-e-patching.md) | Assess, deploy, and validate OS patches via Azure Update Manager with pre/post checks and auto-rollback; AI recommends wave grouping and flags risky KBs. |
| **F** | CMDB Sync | 100 % | 0 % | [`scenario-f-cmdb-sync.md`](scenario-f-cmdb-sync.md) | Compare Azure Resource Graph (source of truth) against GLPI CMDB; auto-update matches, flag ambiguous cases — **no AI needed**. |
| **G** | Snapshot / Checkpoint Cleanup | 100 % | 0 % | [`scenario-g-snapshot-cleanup.md`](scenario-g-snapshot-cleanup.md) | Delete stale Hyper-V checkpoints older than 7 days with safety checks on VM state — **no AI needed**. |

---

## Recommended Demo Order (45-Minute Presentation)

A 45-minute slot fits five live demos comfortably. The order below tells a compelling
story — start with the most relatable pain point, build toward AI-augmented scenarios,
then close by proving that not every problem needs AI.

| # | Scenario | Time | Why This Order |
|---|----------|:----:|----------------|
| 1 | **A — Daily Health Check** | 8 min | Opens with the pain every Wintel admin knows: four manual health checks per day. Immediate audience recognition. |
| 2 | **B — Alert Triage & Ticket Creation** | 8 min | Shows the full alert-to-ticket lifecycle. Introduces SRE Agent's correlation and root-cause capabilities. |
| 3 | **D — Compliance Reporting** | 7 min | High automation percentage (95 %) — demonstrates that even AI-assisted scenarios are mostly deterministic. Quick win. |
| 4 | **F — CMDB Sync** | 7 min | **The "AI is not always needed" moment.** Pure automation, zero AI. Audience sees that the architecture is honest about where AI adds value. |
| 5 | **E — Monthly Patching** | 8 min | Ends on the highest-stakes scenario. AI risk scoring and wave grouping make patching safer — a strong closer. |
|   | *Buffer / Q&A* | 7 min | |

> **Tip:** If time permits, add Scenario C (Security Agent Troubleshooting) after B to
> show the highest-AI scenario (40 %), or swap in Scenario G to reinforce the "100 %
> automation" message with a second zero-AI example.

### Scenarios C and G — On-Deck Extras

- **C — Security Agent Troubleshooting** (60 / 40 split): Best demo for audiences
  interested in Defender for Cloud integration and contextual AI diagnosis.
- **G — Snapshot / Checkpoint Cleanup** (100 / 0 split): Second "no AI" demo;
  useful for audiences sceptical about AI hype.

---

## A Note on Scenarios F and G

Scenarios F (CMDB Sync) and G (Snapshot Cleanup) are **intentionally AI-free**.

> *"Not everything needs AI. CMDB sync is deterministic: query, compare, update.
> Adding AI would add complexity without adding value."*
> — Scenario F

> *"Don't add AI to a problem that a `Where-Object` clause solves perfectly."*
> — Scenario G

Including these scenarios in the demo set is a deliberate design choice. They
demonstrate intellectual honesty: the architecture uses AI where it genuinely helps
(correlation, diagnosis, prioritisation) and avoids it where simple rule-based logic
is sufficient. This builds trust with technical audiences who are wary of
"AI-washing" existing automation.
