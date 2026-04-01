# Option C: GitHub Copilot CLI — Compliance Implementation

The simplest option — copy skills, authenticate `az CLI`, and start asking questions.

> **When to use:** Engineers who work in the terminal and want AI-assisted compliance investigation without building or hosting anything. Great as a complement to the automated compliance report or as a standalone tool for ad-hoc investigation.

> **AI contribution: ~5%.** The automation script handles 95% of the work (querying Defender for Cloud, Azure Policy, and secure score). Copilot CLI adds the executive narrative, root-cause hypothesis, and prioritized remediation — the polish that turns a data dump into actionable intelligence.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Your terminal (PowerShell / bash / zsh)          │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │         GitHub Copilot CLI                   │  │
│  │                                              │  │
│  │  ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Skills        │   │ Terminal tools      │  │  │
│  │  │ (.github/     │   │ ┌────────────────┐ │  │  │
│  │  │  skills/)     │   │ │ az CLI         │ │  │  │
│  │  │ Auto-loads    │   │ │ PowerShell     │ │  │  │
│  │  │ SKILL.md      │   │ │ curl           │ │  │  │
│  │  └──────────────┘   │ └────────────────┘ │  │  │
│  │                      └────────────────────┘  │  │
│  │  ┌──────────────┐                            │  │
│  │  │ Azure Skills  │  (optional add-on)        │  │
│  │  │ Plugin        │                            │  │
│  │  │ ┌──────────┐ │                            │  │
│  │  │ │compliance│ │                            │  │
│  │  │ │diagnostics│ │                            │  │
│  │  │ │+200 MCP  │ │                            │  │
│  │  │ └──────────┘ │                            │  │
│  │  └──────────────┘                            │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Defender for │  │Azure Policy │  │   GLPI   │ │
│  │ Cloud (az)   │  │  (az CLI)   │  │(curl/Py) │ │
│  └──────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **GitHub Copilot CLI** | Installed and authenticated (`gh copilot` or standalone) |
| **GitHub Copilot license** | Individual ($19/mo), Business ($19/user/mo), or Enterprise ($39/user/mo) |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |

## Step 1: Copy Skills

```bash
# From repository root — project-level (this repo only)
mkdir -p .github/skills
cp -r sre-skills/compliance-investigation .github/skills/

# Or user-level (all projects)
# Linux/macOS
cp -r sre-skills/compliance-investigation ~/.copilot/skills/
# Windows (PowerShell)
Copy-Item -Recurse sre-skills\compliance-investigation $env:USERPROFILE\.copilot\skills\
```

## Step 2 (Optional): Install the Azure Skills Plugin

```
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

> **💡 `azure-compliance` vs our `compliance-investigation`:** The plugin's `azure-compliance` skill uses `azqr` (Azure Quick Review) for infrastructure compliance scanning — checking Azure resource configurations against best practices. Our `compliance-investigation` skill queries Defender for Cloud for regulatory framework compliance (CIS, NIST, PCI DSS). These are **complementary**, not overlapping. Use both for full coverage.

## Step 3: Verify Skills Are Loaded

```
/skills list
```

**Expected output:**

```
Available skills:
  compliance-investigation             Defender + Azure Policy compliance...
  wintel-health-check-investigation    Investigates Windows server health check failures...
  security-agent-troubleshooting       Troubleshoots Defender agent health issues...
  patch-validation                     Pre/post patch validation checks...
  vmware-bau-operations                Snapshot cleanup, VM health checks...
```

## Demo Walkthrough

### Example 1 — Run the compliance report (95% automation)

This is the **deterministic** baseline — no AI needed.

```
You: Run the compliance report script

Copilot: I'll run the compliance report automation script.

[Running] ./scripts/demo-compliance-report.ps1

📋 Compliance Report — 2025-01-15

Sources queried:
  ✅ Defender for Cloud — regulatory standards
  ✅ Azure Policy — resource compliance state
  ✅ Secure Score — overall posture

Defender for Cloud:
  CIS Azure Foundations 2.0:    8 failing / 142 passing
  NIST SP 800-53 Rev 5:       15 failing / 312 passing
  PCI DSS v4:                  22 failing / 289 passing

Azure Policy (rg-arcbox-itpro):
  3 non-compliant policies affecting 8 resources

Overall Secure Score: 72/100

Report saved to: ./reports/compliance-2025-01-15.json
```

The script handles data collection, threshold evaluation, and formatted output. No AI involved.

### Example 2 — Executive narrative (the 5% AI adds)

```
You: Summarize the compliance findings for my manager — what's the key takeaway?

Copilot: Based on the compliance report data:

**Executive Summary:**
Your estate is 72% compliant across three regulatory frameworks. The single
biggest gap is PCI DSS (22 failing controls), but ~60% of those failures trace
back to a single root cause: 5 servers in rg-arcbox-itpro lost the Guest
Configuration extension after the December patch cycle. One remediation
action — redeploying the extension via Azure Policy remediation task — would
close 13 of 22 PCI failures and improve your secure score to ~81/100.

**Key takeaway for leadership:** Compliance improved 4% month-over-month.
The remaining gap is concentrated, not widespread — one targeted fix gets
you to 80%+ across all frameworks.

**Recommended next steps:**
1. Redeploy Guest Configuration extension (P1 — est. 1 day)
2. Push CIS audit policy GPO to non-compliant servers (P2 — est. 2 hours)
3. Address resource tagging policies (P3 — next sprint)
```

> This narrative is the part automation can't do — it synthesizes findings into a story a non-technical manager can act on.

### Example 3 — Investigate specific non-compliance (AI + skill)

```
You: Why are 3 servers non-compliant on CIS control 1.1.1?

Copilot: I'll investigate CIS control 1.1.1 using the compliance-investigation
skill and Azure Arc.

[Running] az policy state list --resource-group rg-arcbox-itpro \
  --filter "complianceState eq 'NonCompliant'" -o json | head -50

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name CISCheck \
  --location swedencentral \
  --script "auditpol /get /category:* | Select-String 'Account Logon'"

CIS 1.1.1 — "Ensure 'Enforce password history' is set to '24 or more'"

Non-compliant servers: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL

Root cause: The Guest Configuration extension is missing on these 3 servers.
Without it, Azure Policy cannot evaluate local security policies, so the
control reports as non-compliant by default.

This is the same root cause as the PCI DSS gap — redeploy the extension
and these controls will likely pass on the next evaluation cycle.
```

### Example 4 — Create GLPI tickets for top findings

```
You: Create a GLPI ticket for the top 5 compliance findings prioritized by risk

Copilot: I'll create a GLPI ticket with the top 5 findings ranked by risk impact.

[Running] curl -s -X POST \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token" \
  -d "grant_type=password&client_id=YOUR_CLIENT_ID&..."

[Running] curl -s -X POST \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2.2/Assistance/Ticket" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"[Compliance] Top 5 Findings — Jan 2025",
       "content":"Priority findings ranked by risk:\n
       1. [P1] Guest Config extension missing (5 servers) — blocks PCI+CIS\n
       2. [P1] Audit policy GPO not applied (3 servers) — CIS L1 gap\n
       3. [P2] Disk encryption policy (2 servers) — NIST control\n
       4. [P3] Resource tagging non-compliance (8 resources)\n
       5. [P3] Network watcher not enabled (1 subscription-level)",
       "type":1,"priority":4}'

✅ Ticket created: GLPI #156
   Title: [Compliance] Top 5 Findings — Jan 2025
   Priority: 4 (High)
   URL: http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=156
```

## Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **Interactive only** | No scheduled compliance reports | Run `demo-compliance-report.ps1` via cron; use Copilot for ad-hoc narrative |
| **No persistent memory** | Can't compare with last week automatically | Pass previous report as context or use `~/.copilot/instructions.md` |
| **Session-based** | Knowledge lost between sessions | Use custom instructions for standing compliance context |
| **95% is automation** | AI adds polish, not core functionality | Use the script for data; Copilot for interpretation |

## Recommended Usage Pattern

```
                     Scheduled (weekly)               Ad-hoc (as needed)
                    ┌──────────────────┐           ┌──────────────────┐
                    │ PowerShell script │           │  Copilot CLI     │
                    │ (95% of work)     │           │  (5% AI polish)  │
                    │                   │           │                  │
                    │ ✅ Query Defender  │ ─ data ─▶ │ 🔍 Narrative     │
                    │ ✅ Query Policy    │ for AI    │ 🔍 Root-cause    │
                    │ ✅ Score + report  │           │ 🔍 Prioritize    │
                    │ ✅ Auto-ticket     │           │ 🔍 Investigate   │
                    └──────────────────┘           └──────────────────┘
```

## Comparison with SRE Agent

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify) |
| **Skills** | Upload via UI | Copy to `.github/skills/` |
| **Tools** | Built-in + custom | Terminal (az CLI, PowerShell, curl) |
| **Scheduling** | ✅ Built-in | ❌ Manual only |
| **Memory** | ✅ Built-in | ⚠️ Session-only |
| **Executive narrative** | ✅ Auto-generated | ✅ On-demand (interactive) |
| **Deep investigation** | ✅ Good | ✅ Excellent (full terminal access) |
| **Cost** | Azure Agent Units | Copilot license ($19-39/user/mo) |

## See Also

- [Scenario D overview](../scenario-d-compliance.md) — comparison of all 4 options
- [`sre-skills/compliance-investigation/SKILL.md`](../../../sre-skills/compliance-investigation/SKILL.md) — skill definition
- [Azure Skills Plugin](https://github.com/microsoft/azure-skills) — optional add-on (`azure-compliance` uses `azqr`)
- [GitHub Copilot CLI documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
