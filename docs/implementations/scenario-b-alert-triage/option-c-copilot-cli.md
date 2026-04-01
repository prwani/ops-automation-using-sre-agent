# Option C: GitHub Copilot CLI — Alert Triage Implementation

The simplest alert-triage option — copy skills, authenticate `az CLI`, and start investigating alerts interactively.

> **When to use:** Engineers who see an Azure Monitor alert in email/Teams/Portal and want AI-assisted triage without building or hosting anything. Great as a complement to SRE Agent or for ad-hoc investigation of correlated alert storms.

> **Automation ratio:** 70% deterministic scripts / 30% AI reasoning via Copilot CLI

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Engineer's Terminal (PowerShell / bash / zsh)                │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         GitHub Copilot CLI                               │  │
│  │                                                          │  │
│  │  ┌──────────────────┐   ┌────────────────────────────┐  │  │
│  │  │ Skills            │   │ Terminal Tools (native)     │  │  │
│  │  │ (.github/skills/) │   │ ┌────────────────────────┐ │  │  │
│  │  │                   │   │ │ az graph query          │ │  │  │
│  │  │ security-agent-   │   │ │ az monitor alert        │ │  │  │
│  │  │ troubleshooting/  │   │ │ az monitor log-analytics│ │  │  │
│  │  │ SKILL.md          │   │ │ az connectedmachine     │ │  │  │
│  │  │ (auto-loaded)     │   │ │ python glpi_tools.py    │ │  │  │
│  │  └──────────────────┘   │ │ curl (GLPI REST API)    │ │  │  │
│  │                          │ └────────────────────────┘ │  │  │
│  │  ┌──────────────────┐   └────────────────────────────┘  │  │
│  │  │ Azure Skills      │                                    │  │
│  │  │ Plugin (optional)  │                                    │  │
│  │  │ azure-diagnostics  │                                    │  │
│  │  │ azure-observability│                                    │  │
│  │  └──────────────────┘                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  Alert fires → Engineer sees in Azure Portal/email/Teams      │
│  → Opens Copilot CLI → Uses skills + az CLI + GLPI tools      │
└──────────────────────────────────────────────────────────────┘
```

**Key difference from SRE Agent:** No automatic alert reception — the engineer sees the alert in Azure Portal, email, or Teams and brings the context to Copilot CLI for interactive investigation.

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **GitHub Copilot CLI** | Installed and authenticated (`gh copilot` or standalone) |
| **GitHub Copilot license** | Individual ($19/mo), Business ($19/user/mo), or Enterprise ($39/user/mo) |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |

## Step 1: Copy Skills

Copy the project's SRE skills to the Copilot CLI skills directory:

### Option A — Project-level skills (this repo only)

```bash
# From repository root
mkdir -p .github/skills
cp -r sre-skills/* .github/skills/
```

### Option B — User-level skills (all projects)

```bash
# Linux/macOS
cp -r sre-skills/* ~/.copilot/skills/

# Windows (PowerShell)
Copy-Item -Recurse sre-skills\* $env:USERPROFILE\.copilot\skills\
```

## Step 2 (Optional): Install the Azure Skills Plugin

The [Azure Skills Plugin](https://github.com/microsoft/azure-skills) adds **20 Azure skills and 200+ MCP tools** for Azure diagnostics and observability. It complements our custom Wintel skills — it does NOT replace them.

```
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

What this adds to alert triage:
- **`azure-diagnostics`** — AppLens troubleshooting, correlate alert signals from resource health
- **`azure-observability`** — query Log Analytics for Perf/Event data directly from Copilot

**Important:** For Arc Run Commands (restarting services, running diagnostics on servers) you still need `az connectedmachine` via the terminal. The plugin has no `connectedmachine` MCP namespace.

## Step 3: Verify Skills Are Loaded

```
/skills list
```

**Expected output:**

```
Available skills:
  wintel-health-check-investigation    Investigates Windows server health check failures...
  security-agent-troubleshooting       Troubleshoots Defender agent health issues...
  patch-validation                     Pre/post patch validation checks...
  compliance-investigation             Defender + Azure Policy compliance...
  vmware-bau-operations                Snapshot cleanup, VM health checks...
```

## Demo Walkthrough

### Example 1 — Show current Azure Monitor alerts

```
You: Show me current Azure Monitor alerts in rg-arcbox-itpro
```

```
Copilot: I'll query the active alerts in your resource group.

[Running] az graph query -q "alertsmanagementresources
  | where type == 'microsoft.alertsmanagement/alerts'
  | where properties.essentials.monitorCondition == 'Fired'
  | where properties.essentials.targetResourceGroup =~ 'rg-arcbox-itpro'
  | project alertName=name,
    severity=properties.essentials.severity,
    target=properties.essentials.targetResource,
    fired=properties.essentials.startDateTime
  | order by severity asc" -o table

Active alerts in rg-arcbox-itpro:

| Alert                     | Severity | Target          | Fired            |
|---------------------------|----------|-----------------|------------------|
| HighCPU-ArcBox-Win2K22    | Sev1     | ArcBox-Win2K22  | 2025-01-15 14:32 |
| W32Time-Stopped           | Sev2     | ArcBox-Win2K22  | 2025-01-15 14:35 |
| DiskSpaceLow-ArcBox-SQL   | Sev2     | ArcBox-SQL      | 2025-01-15 12:10 |

3 active alerts found. Shall I investigate any of these?
```

### Example 2 — Investigate a specific alert

```
You: Investigate the high CPU alert on ArcBox-Win2K22
```

```
Copilot: I'll investigate using the security-agent-troubleshooting skill.
Let me check the server's current state.

[Running] az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Perf | where TimeGenerated > ago(1h)
    | where Computer == 'ArcBox-Win2K22'
    | where CounterName == '% Processor Time'
    and InstanceName == '_Total'
    | summarize AvgCPU=round(avg(CounterValue),1),
      MaxCPU=round(max(CounterValue),1)
    by bin(TimeGenerated, 5m)
    | order by TimeGenerated desc | take 6"

CPU in the last 30 minutes:

| Time  | Avg CPU | Max CPU |
|-------|---------|---------|
| 14:55 | 82.3%   | 91.2%   |
| 14:50 | 85.1%   | 94.7%   |
| 14:45 | 79.8%   | 88.5%   |
| 14:40 | 88.2%   | 96.1%   |
| 14:35 | 91.5%   | 98.3%   |
| 14:30 | 45.2%   | 52.1%   |

📈 CPU spiked from ~45% to 85%+ starting at 14:32 — exactly when the
alert fired. Let me check what's consuming CPU.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "TopProcesses" \
  --location swedencentral \
  --script "Get-Process | Sort-Object CPU -Descending |
    Select-Object -First 5 Name, CPU, Id |
    ConvertTo-Json"

Top processes: MsMpEng (Defender AV scan), svchost, sqlservr, w3wp.
MsMpEng is consuming ~60% CPU — likely a scheduled or on-demand scan.
```

### Example 3 — Correlate multiple alerts

```
You: Correlate: ArcBox-Win2K22 has high CPU AND W32Time service stopped —
     are these related?
```

```
Copilot: Good question — let me check the timeline for both events.

[Running] az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Event | where Computer == 'ArcBox-Win2K22'
    | where TimeGenerated > ago(2h)
    | where Source in ('Service Control Manager','Microsoft-Windows-Time-Service')
    | project TimeGenerated, Source, EventID, RenderedDescription
    | order by TimeGenerated asc"

Timeline:
  14:30 — Defender AV scan started (MsMpEng high CPU begins)
  14:32 — CPU alert fires (Sev1)
  14:33 — W32Time service enters resource contention
  14:35 — W32Time service stops (Event 7036) → W32Time alert fires (Sev2)

🔗 Correlation: These two alerts share a single root cause — the Defender
antivirus scan is consuming CPU, which caused W32Time (a low-priority
service) to lose resource allocation and stop.

Recommendation:
1. Wait for the AV scan to complete (~10-15 min) — CPU should normalize
2. Restart W32Time after CPU drops below 60%
3. Consider scheduling Defender scans during off-peak hours

This is a P3 incident (auto-remediating once scan completes). Shall I
create a GLPI ticket?
```

### Example 4 — Create a GLPI ticket

```
You: Create a GLPI ticket for this incident with the root cause analysis
```

```
Copilot: I'll create a ticket with the full correlation analysis.

[Running] python sre-tools/python/glpi_tools.py \
  --title "[ALERT] ArcBox-Win2K22: High CPU + W32Time — Defender scan root cause" \
  --description "Root cause: Defender AV scan (MsMpEng) consuming ~60% CPU
    since 14:30. Caused W32Time service stop at 14:35 due to resource
    contention. Two correlated alerts reduced to one incident.
    Remediation: scan will self-complete; W32Time restart needed after.
    Recommendation: schedule Defender scans off-peak." \
  --priority 3

✅ Ticket created: GLPI #159
   Title: [ALERT] ArcBox-Win2K22: High CPU + W32Time — Defender scan root cause
   Priority: 3 (Medium)
   URL: http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=159
```

### Example 5 — Query Log Analytics for CPU trends

```
You: Check if this CPU pattern is normal — query Log Analytics for last 7 days
```

```
Copilot: I'll check the 7-day CPU baseline for ArcBox-Win2K22.

[Running] az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Perf | where TimeGenerated >= ago(7d)
    | where Computer == 'ArcBox-Win2K22'
    | where ObjectName == 'Processor'
    and CounterName == '% Processor Time'
    and InstanceName == '_Total'
    | summarize AvgCPU=round(avg(CounterValue),1),
    MaxCPU=round(max(CounterValue),1),
    P95CPU=round(percentile(CounterValue, 95),1)
    by bin(TimeGenerated, 1d)
    | order by TimeGenerated asc"

ArcBox-Win2K22 — 7-day CPU baseline:

| Day       | Avg CPU | Max CPU | P95 CPU |
|-----------|---------|---------|---------|
| Jan 9     | 32.1%   | 78.2%   | 65.3%   |
| Jan 10    | 35.4%   | 81.5%   | 68.1%   |
| Jan 11    | 33.8%   | 92.3%   | 67.9%   |
| Jan 12    | 31.2%   | 79.8%   | 64.5%   |
| Jan 13    | 34.7%   | 88.1%   | 69.2%   |
| Jan 14    | 36.2%   | 85.4%   | 70.1%   |
| Jan 15    | 67.9%   | 98.3%   | 91.5%   |

📊 Today (Jan 15) is a clear outlier — average CPU doubled compared to
the prior 6-day baseline (~33%). The daily max spikes to ~80-92% on other
days suggest periodic AV scans, but they don't sustain high averages.

Conclusion: Today's sustained high CPU is abnormal. The Defender scan may
be a full scan vs. the usual quick scan. Recommend verifying scan type
and adjusting the scheduled scan policy.
```

> **💡 Azure Skills Plugin:** If you have the [Azure Skills Plugin](https://github.com/microsoft/azure-skills) installed, the `azure-observability` skill can help with Log Analytics queries like these. The `azure-diagnostics` skill can also correlate resource health signals from AppLens to surface platform-level issues. This is additive — our custom skills still provide the Wintel-specific triage logic and GLPI integration.

## Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **No automatic alert reception** | Cannot ingest alerts from Azure Monitor automatically | Engineer monitors Portal/email/Teams, pastes alert context |
| **Interactive only** | Cannot run on a schedule or auto-respond to alerts | Use alongside `demo-alert-monitoring.ps1` for scheduled polling |
| **No persistent memory** | Doesn't remember past triage sessions or alert patterns | Use custom instructions file for persistent context |
| **Session-scoped** | Each new session starts from scratch | Reference previous findings explicitly in your prompts |
| **Requires human** | Someone must type the query and approve actions | Use for ad-hoc deep-dives, not 24/7 alert response |

## Comparison with SRE Agent

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify az CLI) |
| **Alert reception** | ✅ Automatic (Azure Monitor integration) | ❌ Manual (engineer initiates) |
| **Alert correlation** | ✅ Built-in | ⚠️ LLM reasoning (prompt-dependent) |
| **Skills** | Upload via UI | Copy to `.github/skills/` (identical content) |
| **Tool execution** | Built-in `RunAzCliWriteCommands` | Direct terminal (az CLI, Python, curl) |
| **Scheduling** | ✅ Built-in | ❌ Interactive only |
| **Memory** | ✅ Cross-session | ⚠️ Session-only |
| **Auto-remediation** | ✅ Built-in | ✅ Terminal commands (human-approved) |
| **Best for** | 24/7 automated triage | Ad-hoc investigation by engineers |
| **Cost** | Azure Agent Units | Copilot license ($19–39/user/mo) |

## See Also

- [Scenario B — Alert Triage (all options)](../scenario-b-alert-triage.md) — comparison of all 4 options
- [`sre-skills/security-agent-troubleshooting/SKILL.md`](../../../sre-skills/security-agent-troubleshooting/SKILL.md) — skill definition
- [`scripts/demo-alert-monitoring.ps1`](../../../scripts/demo-alert-monitoring.ps1) — deterministic alert polling script
- [Azure Skills Plugin](https://github.com/microsoft/azure-skills) — optional add-on for Azure diagnostics and observability
- [GitHub Copilot CLI documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
