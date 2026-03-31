# Option C: GitHub Copilot CLI — Health Check Implementation

The simplest option — copy skills, authenticate `az CLI`, and start asking questions.

> **When to use:** Engineers who work in the terminal and want AI-assisted health checks without building or hosting anything. Great as a complement to SRE Agent or as a standalone tool for ad-hoc investigation.

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
│  │  │ SKILL.md      │   │ │ Python         │ │  │  │
│  │  └──────────────┘   │ │ curl           │ │  │  │
│  │                      │ └────────────────┘ │  │  │
│  │  ┌──────────────┐   └────────────────────┘  │  │
│  │  │ Azure Skills  │                           │  │
│  │  │ Plugin        │  (optional add-on)        │  │
│  │  │ ┌──────────┐ │                            │  │
│  │  │ │diagnostics│ │                            │  │
│  │  │ │observ.   │ │                            │  │
│  │  │ │compliance│ │                            │  │
│  │  │ │+200 MCP  │ │                            │  │
│  │  │ └──────────┘ │                            │  │
│  │  └──────────────┘                            │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │  Azure Arc   │  │Log Analytics│  │   GLPI   │ │
│  │  (az CLI)    │  │  (az CLI)   │  │(curl/Py) │ │
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

The [Azure Skills Plugin](https://github.com/microsoft/azure-skills) adds **20 Azure skills and 200+ MCP tools** for Azure infrastructure diagnostics, observability, and compliance. It complements our custom Wintel skills — it does NOT replace them.

```
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

What this adds to health checks:
- **`azure-diagnostics`** — AppLens troubleshooting, Azure Monitor KQL queries for resource health
- **`azure-observability`** — query Log Analytics for Perf/Event data, create alert rules, view Workbooks
- **Azure MCP Server (`monitor` namespace)** — run KQL queries against Log Analytics directly from Copilot

**Important:** For the core health check mechanism — running PowerShell on Arc-enrolled servers via `az connectedmachine run-command` — you still need `az CLI` in the terminal. The plugin has no `connectedmachine` MCP namespace, so Arc Run Commands are not covered. The layered approach is:

```
Copilot CLI health check workflow:
│
├── Azure Skills Plugin (azure-observability / azure-diagnostics)
│   └── Query Log Analytics for Perf counters, event logs, KQL trends
│       (replaces manual "az monitor log-analytics query" for some queries)
│
├── Our wintel-health-check-investigation skill (REQUIRED)
│   └── Wintel-specific thresholds, escalation logic, SOP procedures
│
└── az CLI in terminal (REQUIRED for Arc Run Commands)
    └── az connectedmachine run-command → execute PowerShell on servers
        (disk analysis, service checks, event log deep-dives)
```

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

All 5 skills from `sre-skills/` should appear.

## Step 4: Verify Azure CLI Access

```bash
# Confirm Arc servers are visible
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' and resourceGroup == 'rg-arcbox-itpro' | project name, properties.status" -o table

# Confirm Log Analytics access
az monitor log-analytics query \
  --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c \
  --analytics-query "Perf | take 1" -o json
```

## Step 5: Run Health Check Investigations

### Example 1 — Full estate health check

```
You: Check the health of all my Arc servers in rg-arcbox-itpro
```

Copilot CLI:
1. **Loads** `wintel-health-check-investigation` skill (auto-detected from your query)
2. **Runs** `az graph query` to list all Arc servers
3. **Runs** `az monitor log-analytics query` to pull current metrics per server
4. **Interprets** results using the skill's investigation steps and thresholds
5. **Reports** findings with severity indicators

**Example interaction:**

```
You: Check the health of all my Arc servers in rg-arcbox-itpro

Copilot: I'll check the health of your Arc servers using the health check
investigation skill.

[Running] az graph query -q "Resources | where type ==
  'microsoft.hybridcompute/machines' and resourceGroup == 'rg-arcbox-itpro'
  | project name, properties.status, properties.osName"

Found 5 Arc servers. Let me check their performance metrics.

[Running] az monitor log-analytics query --workspace f98fca75-7479-45e5-
  bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated > ago(1h)
  | where Computer in ('ArcBox-Win2K22','ArcBox-Win2K25','ArcBox-SQL')
  | where CounterName in ('% Processor Time','% Committed Bytes In Use',
  '% Free Space') | summarize avg(CounterValue) by Computer, CounterName"

Here's the health summary:

🔴 ArcBox-SQL
  - Disk E: 91.3% used (CRITICAL — threshold 90%)
  - Memory: 87.2% (WARNING — threshold 85%)
  - 14 event log errors in last 6h (CRITICAL — threshold 10)

🟡 ArcBox-Win2K22
  - Disk D: 88.5% used (WARNING — threshold 80%)
  - 3 event log errors (WARNING)

🟢 ArcBox-Win2K25 — All metrics healthy
🟢 ArcBox-Ubuntu-01 — All metrics healthy
🟢 ArcBox-Ubuntu-02 — All metrics healthy

Shall I investigate the ArcBox-SQL disk issue further or create a GLPI ticket?
```

### Example 2 — Invoke skill directly

```
You: Run the /wintel-health-check-investigation skill on ArcBox-Win2K22
```

Copilot CLI follows the skill's step-by-step procedure:
1. Queries Cosmos DB for recent health check runs (if available)
2. Runs live diagnostics via Arc Run Command
3. Evaluates against thresholds
4. Recommends action

### Example 3 — Query Log Analytics for trends

```
You: Query Log Analytics for CPU trends on ArcBox-SQL over the last 7 days
```

```
Copilot: I'll query the 7-day CPU trend for ArcBox-SQL.

[Running] az monitor log-analytics query --workspace f98fca75-7479-45e5-
  bf0c-87b56a9f9e8c --analytics-query "Perf | where TimeGenerated >= ago(7d)
  | where Computer == 'ArcBox-SQL' | where ObjectName == 'Processor'
  and CounterName == '% Processor Time' and InstanceName == '_Total'
  | summarize AvgCPU=round(avg(CounterValue),1),
  MaxCPU=round(max(CounterValue),1) by bin(TimeGenerated, 1d)
  | order by TimeGenerated asc"

ArcBox-SQL — 7-day CPU trend:

| Day       | Avg CPU | Max CPU |
|-----------|---------|---------|
| Jan 9     | 34.2%   | 62.1%   |
| Jan 10    | 38.5%   | 71.3%   |
| Jan 11    | 41.2%   | 78.9%   |
| Jan 12    | 55.3%   | 89.2%   |
| Jan 13    | 62.1%   | 91.5%   |
| Jan 14    | 58.7%   | 85.3%   |
| Jan 15    | 67.9%   | 92.1%   |

📈 CPU is trending upward — average increased from 34% to 68% over 7 days.
The spike starting Jan 12 may correlate with a workload change. This hasn't
breached the 80% WARNING threshold on average, but max values are
consistently above 85%.

Recommendation: Monitor for another 24-48 hours. If average exceeds 80%,
investigate top processes on the server.
```

> **💡 Azure Skills Plugin:** If you have the [Azure Skills Plugin](https://github.com/microsoft/azure-skills) installed, the `azure-observability` skill can help with Log Analytics queries like this. Copilot may use the plugin's `monitor` MCP namespace to run KQL queries directly, and the `azure-diagnostics` skill to correlate resource health signals from AppLens. This is additive — our `wintel-health-check-investigation` skill still provides the Wintel-specific thresholds and escalation logic that the plugin doesn't have.

### Example 4 — Create a GLPI ticket

```
You: Create a GLPI ticket for the disk warning on ArcBox-Win2K25
```

```
Copilot: I'll create a GLPI ticket for the disk warning.

[Running] curl -s -X POST \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token" \
  -d "grant_type=password&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET&username=glpi&password=..."

[Running] curl -s -X POST \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2.2/Assistance/Ticket" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"[Health Check] ArcBox-Win2K25: Disk D: 88.5% WARNING",
       "content":"Disk D: on ArcBox-Win2K25 is at 88.5% usage...",
       "type":1,"priority":3}'

✅ Ticket created: GLPI #143
   Title: [Health Check] ArcBox-Win2K25: Disk D: 88.5% WARNING
   Priority: 3 (Medium)
   URL: http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=143
```

### Example 5 — Disk deep-dive with Arc Run Command

```
You: What's filling up disk E: on ArcBox-SQL? Run a check on the server.
```

```
Copilot: I'll run a disk analysis on ArcBox-SQL via Arc Run Command.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-SQL \
  --name "DiskAnalysis" \
  --location swedencentral \
  --script "Get-ChildItem E:\ -Directory | ForEach-Object {
    [PSCustomObject]@{
      Path = $_.FullName;
      SizeGB = [math]::Round((Get-ChildItem $_.FullName -Recurse -File |
        Measure-Object Length -Sum).Sum / 1GB, 2)
    }
  } | Sort-Object SizeGB -Descending | Select-Object -First 10 |
  ConvertTo-Json" \
  --async-execution false

Top directories on E: drive:

| Directory          | Size (GB) |
|--------------------|-----------|
| E:\MSSQL\Data      | 28.4      |
| E:\MSSQL\Log       | 18.7      |
| E:\MSSQL\Backup    | 8.2       |
| E:\Temp            | 3.1       |

🔍 The SQL transaction logs (E:\MSSQL\Log) are 18.7 GB. This is likely the
primary growth driver. Transaction logs may not be truncating after backups.

Recommendation:
1. Check SQL backup jobs — ensure log backups are completing
2. Shrink log files after confirming backup chain is intact
3. Consider moving backups to a separate volume
```

## How Copilot CLI Uses the Skill

When you ask a health-related question, Copilot CLI:

1. **Matches** your query against the `triggers` in `SKILL.md` frontmatter
2. **Loads** the matching skill's content as context
3. **Follows** the investigation steps defined in the skill
4. **Executes** commands directly in your terminal (no wrapper functions needed)
5. **Interprets** results using the skill's thresholds and escalation matrix

The key difference from the other options: Copilot CLI runs `az CLI` commands **directly in your terminal**. There's no need for function tools, SDK wrappers, or hosted endpoints — it has native access to everything your terminal has.

## Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **Interactive only** | Cannot run on a schedule or auto-respond to alerts | Use alongside scripts (`demo-health-check.ps1`) for scheduled checks |
| **No persistent memory** | Doesn't remember past investigations across sessions | Use custom instructions file for persistent context |
| **Session-scoped** | Each new session starts from scratch | Reference previous findings in your prompts |
| **Requires human** | Someone must type the query | Use for ad-hoc deep-dives, not routine checks |

## Recommended Usage Pattern

Copilot CLI works best as a **complement** to automated health checks, not a replacement:

```
                     Scheduled (4×/day)              Ad-hoc (as needed)
                    ┌──────────────┐              ┌──────────────────┐
                    │ PowerShell   │              │  Copilot CLI     │
                    │ scripts      │              │  (interactive)   │
                    │              │              │                  │
                    │ ✅ Collect    │  ─ flags ─▶  │ 🔍 Investigate   │
                    │ ✅ Evaluate   │  findings    │ 🔍 Correlate     │
                    │ ✅ Report     │              │ 🔍 Deep-dive     │
                    │ ✅ Ticket     │              │ 🔍 Project trends│
                    └──────────────┘              └──────────────────┘
```

1. **Scripts** run on schedule → collect data, evaluate thresholds, create tickets
2. **Copilot CLI** used by engineer → investigate flagged issues, correlate patterns, deep-dive

## Optional: MCP Server for GLPI

Instead of using `curl` for GLPI tickets, you can connect a GLPI MCP server:

```json
// .vscode/mcp.json or ~/.copilot/mcp-config.json
{
  "servers": {
    "glpi": {
      "type": "http",
      "url": "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

This gives Copilot CLI direct tool access to GLPI without manual `curl` commands.

## Comparison with SRE Agent

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify) |
| **Skills** | Upload via UI | Copy to `.github/skills/` |
| **Tools** | Built-in + custom | Terminal (az CLI, PowerShell, Python) |
| **Scheduling** | ✅ Built-in | ❌ Manual only |
| **Memory** | ✅ Built-in | ⚠️ Session-only |
| **Incident response** | ✅ Auto-trigger | ❌ Interactive only |
| **Deep investigation** | ✅ Good | ✅ Excellent (full terminal access) |
| **Cost** | Azure Agent Units | Copilot license ($19-39/user/mo) |

## See Also

- [README.md](README.md) — comparison of all 4 options
- [`sre-skills/wintel-health-check-investigation/SKILL.md`](../../../sre-skills/wintel-health-check-investigation/SKILL.md) — skill definition
- [Azure Skills Plugin](https://github.com/microsoft/azure-skills) — optional add-on for Azure diagnostics, observability, and compliance
- [GitHub Copilot CLI documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
