# Option C: GitHub Copilot CLI — Security Agent Troubleshooting Implementation

The simplest option — copy skills, authenticate `az CLI`, and start diagnosing Defender for Endpoint issues interactively.

> **When to use:** Security engineers who need to troubleshoot Defender agent health on Arc-enrolled servers from the terminal. Great as a complement to SRE Agent or for ad-hoc investigation when an agent goes unhealthy.

> **Automation ratio:** 60% deterministic scripts / 40% AI reasoning via Copilot CLI

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
│  │  │ security-agent-   │   │ │ az connectedmachine     │ │  │  │
│  │  │ troubleshooting/  │   │ │   run-command            │ │  │  │
│  │  │ SKILL.md          │   │ │ Get-Service (via Arc)   │ │  │  │
│  │  │ (auto-loaded)     │   │ │ Test-NetConnection      │ │  │  │
│  │  └──────────────────┘   │ │ Get-WinEvent (via Arc)  │ │  │  │
│  │                          │ │ python glpi_tools.py    │ │  │  │
│  │  ┌──────────────────┐   │ └────────────────────────┘ │  │  │
│  │  │ Azure Skills      │   └────────────────────────────┘  │  │
│  │  │ Plugin (optional)  │                                    │  │
│  │  │ azure-diagnostics  │                                    │  │
│  │  │ azure-observability│                                    │  │
│  │  └──────────────────┘                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  az CLI authenticated ──→ Azure Arc, Defender, Log Analytics  │
│                                                               │
│  NOTE: Engineer sees alert in Portal/email, initiates triage  │
│        manually in the terminal.                              │
└──────────────────────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **GitHub Copilot CLI** | Installed and authenticated (`gh copilot` or standalone) |
| **GitHub Copilot license** | Individual ($19/mo), Business ($19/user/mo), or Enterprise ($39/user/mo) |
| **Azure CLI** | Authenticated (`az login`) with access to `rg-arcbox-itpro` |
| **Azure CLI extensions** | `az extension add --name connectedmachine --upgrade` |
| **Defender services** | `MdCoreSvc` (Defender core), `Sense` (EDR telemetry) on target servers |

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

The [Azure Skills Plugin](https://github.com/microsoft/azure-skills) adds **20 Azure skills and 200+ MCP tools** for Azure diagnostics and observability. It complements our custom security skill — it does NOT replace it.

```
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

What this adds to security troubleshooting:
- **`azure-diagnostics`** — AppLens troubleshooting, surface resource health insights for Arc machines
- **`azure-observability`** — query Log Analytics for Defender-related events and service health data

**Important:** The core remediation mechanism — running `Get-Service`, `Restart-Service`, `Test-NetConnection`, and `Get-WinEvent` on Arc-enrolled servers via `az connectedmachine run-command` — still requires `az CLI` in the terminal. The plugin has no `connectedmachine` MCP namespace.

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

The `security-agent-troubleshooting` skill is the primary skill for this scenario. When you mention "Defender", "agent health", "not reporting", "MdCoreSvc", or "Sense service", Copilot matches against the skill's triggers and loads the full 6-step investigation procedure.

## Demo Walkthrough

### Example 1 — Check Defender health across all Arc servers

```
You: Check if Defender for Endpoint is healthy on all my Arc servers
```

```
Copilot: I'll check the Defender agent health status across your Arc fleet.

[Running] az graph query -q "Resources
  | where type == 'microsoft.hybridcompute/machines'
  | where resourceGroup == 'rg-arcbox-itpro'
  | project name, os=properties.osName,
    mdeStatus=properties.detectedProperties.mdeDeviceHealthStatus,
    lastSeen=properties.detectedProperties.mdeLastSeen,
    agentVersion=properties.detectedProperties.mdeAgentVersion" -o table

Defender for Endpoint status:

| Server           | OS          | MDE Status | Last Seen     | Agent Version |
|------------------|-------------|------------|---------------|---------------|
| ArcBox-Win2K22   | Windows     | Inactive   | 45 min ago    | 10.8760.19041 |
| ArcBox-Win2K25   | Windows     | Active     | 2 min ago     | 10.8760.19041 |
| ArcBox-SQL       | Windows     | Active     | 1 min ago     | 10.8760.19041 |
| ArcBox-Ubuntu-01 | Linux       | Active     | 3 min ago     | 101.24032.007 |
| ArcBox-Ubuntu-02 | Linux       | Active     | 2 min ago     | 101.24032.007 |

🔴 ArcBox-Win2K22 — Inactive, last seen 45 minutes ago
🟢 All other servers — Active and reporting normally

Shall I diagnose ArcBox-Win2K22 using the security-agent-troubleshooting skill?
```

### Example 2 — Full skill-driven diagnosis

```
You: Use the /security-agent-troubleshooting skill to diagnose ArcBox-Win2K22
```

```
Copilot: I'll follow the security-agent-troubleshooting skill's 6-step
procedure to diagnose this.

**Step 1 — Defender API health check:**

[Running] az graph query -q "Resources
  | where type == 'microsoft.hybridcompute/machines'
  | where name == 'ArcBox-Win2K22'
  | project name, properties.detectedProperties.mdeDeviceHealthStatus,
    properties.detectedProperties.mdeLastSeen"

→ healthStatus: Inactive, lastSeen: 45 min ago

**Step 2 — Check local services via Arc Run Command:**

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "CheckDefenderSvc" \
  --location swedencentral \
  --script "$svc = Get-Service MdCoreSvc -EA SilentlyContinue;
    $mde = Get-Service Sense -EA SilentlyContinue;
    @{MdCoreSvc=$svc.Status.ToString(); Sense=$mde.Status.ToString();
    LastBoot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime} |
    ConvertTo-Json"

→ MdCoreSvc: Running ✅, Sense: Stopped ❌

**Step 3 — Network connectivity test:**

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "TestDefenderConnectivity" \
  --location swedencentral \
  --script "@('winatp-gw-eus.microsoft.com','winatp-gw-neu.microsoft.com',
    'us-v20.events.data.microsoft.com') | % {
    [PSCustomObject]@{Endpoint=$_;
    Reachable=(Test-NetConnection $_ -Port 443 -InformationLevel Quiet)}} |
    ConvertTo-Json"

→ All endpoints reachable ✅

**Step 4 — Root cause identified:**
Sense stopped, MdCoreSvc running, network OK. Matches skill's remediation
table: "Sense stopped → Restart service." Restarting now.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "RestartSense" \
  --location swedencentral \
  --script "Restart-Service Sense -Force; Start-Sleep 5;
    Get-Service Sense | Select Status | ConvertTo-Json"

→ Sense: Running ✅

**Step 5 — Verification (after 5 min):**

[Running] az graph query -q "Resources | where name == 'ArcBox-Win2K22'
  | project properties.detectedProperties.mdeDeviceHealthStatus,
    properties.detectedProperties.mdeLastSeen"

→ healthStatus: Active ✅, lastSeen: just now ✅

✅ Defender agent restored. Shall I create a GLPI ticket for the audit trail?
```

### Example 3 — Check event logs for Defender errors

```
You: Check event logs on ArcBox-Win2K22 for Defender-related errors
```

```
Copilot: I'll query the System and Application event logs for Defender-
related entries via Arc Run Command.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "CheckEventLogs" \
  --location swedencentral \
  --script "Get-WinEvent -FilterHashtable @{LogName='System';
    Level=1,2,3; StartTime=(Get-Date).AddHours(-6)} -MaxEvents 20 |
    Where-Object {$_.Message -match 'Defender|Sense|MdCoreSvc'} |
    Select-Object TimeCreated, Id, Message | ConvertTo-Json"

Event log entries (last 6 hours):

| Time          | Event ID | Message                                    |
|---------------|----------|--------------------------------------------|
| 14:15 UTC     | 7036     | Sense service entered the stopped state     |
| 14:15 UTC     | 7034     | Sense service terminated unexpectedly       |
| 14:58 UTC     | 7036     | Sense service entered the running state     |

🔍 The Sense service crashed at 14:15 (Event 7034 — unexpected
termination, not a graceful stop). No preceding errors indicate cause.
This is consistent with a transient crash.

The service was restarted at 14:58 via our remediation and is now
running normally.
```

> **⚠️ Arc Run Command limitation:** Copilot CLI runs diagnostics via `az connectedmachine run-command`, which executes PowerShell remotely through the Arc agent. This works well for `Get-Service`, `Get-WinEvent`, and `Test-NetConnection`. However, if the Arc agent itself is unhealthy or the server is unreachable, run commands will fail. **Workaround:** If you're on ArcBox-Client (the jump box), use `Invoke-Command -VMName ArcBox-Win2K22 -ScriptBlock { ... }` via Hyper-V direct connection as a fallback.

### Example 4 — Check Defender cloud endpoint connectivity

```
You: What's the connectivity status to Defender cloud endpoints from
     ArcBox-Win2K22?
```

```
Copilot: I'll run a comprehensive connectivity check against all required
Defender for Endpoint cloud endpoints.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "DefenderConnCheck" \
  --location swedencentral \
  --script "$endpoints = @(
    'winatp-gw-eus.microsoft.com',
    'winatp-gw-neu.microsoft.com',
    'us-v20.events.data.microsoft.com',
    'automatedirstrprdneu.blob.core.windows.net',
    'go.microsoft.com'
  );
  $results = $endpoints | ForEach-Object {
    $tcp = Test-NetConnection $_ -Port 443 -WarningAction SilentlyContinue;
    [PSCustomObject]@{
      Endpoint=$_;
      Reachable=$tcp.TcpTestSucceeded;
      Latency=$tcp.PingReplyDetails.RoundtripTime
    }
  };
  $results | ConvertTo-Json"

Defender endpoint connectivity from ArcBox-Win2K22:

| Endpoint                                   | Reachable | Latency |
|--------------------------------------------|-----------|---------|
| winatp-gw-eus.microsoft.com                | ✅ Yes    | 24 ms   |
| winatp-gw-neu.microsoft.com                | ✅ Yes    | 8 ms    |
| us-v20.events.data.microsoft.com           | ✅ Yes    | 22 ms   |
| automatedirstrprdneu.blob.core.windows.net | ✅ Yes    | 6 ms    |
| go.microsoft.com                           | ✅ Yes    | 18 ms   |

All Defender cloud endpoints reachable ✅. Network is not the issue —
this confirms the Sense crash was a local transient failure, not a
firewall or connectivity problem.

Note: If any endpoint showed Reachable=❌, that would indicate a firewall
rule change and require escalation to the network/firewall team (P2).
```

### Example 5 — Create a GLPI ticket for security team escalation

```
You: Create a GLPI ticket to escalate this to the security team with the
     full diagnosis
```

```
Copilot: I'll create a comprehensive ticket with the full diagnostic
timeline.

[Running] python sre-tools/python/glpi_tools.py \
  --title "[Security] Defender agent resolved: ArcBox-Win2K22 (Sense crash)" \
  --description "Incident: ArcBox-Win2K22 Defender agent inactive for 45 min.
    Diagnosis (6-step procedure):
    1. MDE API: healthStatus=Inactive, lastSeen=45 min ago
    2. Services: MdCoreSvc=Running, Sense=Stopped (unexpected termination)
    3. Network: All 5 Defender endpoints reachable (no firewall issue)
    4. Event logs: Event 7034 at 14:15 — Sense terminated unexpectedly
    5. Root cause: Transient Sense service crash (no external trigger)
    6. Remediation: Sense restarted via Arc Run Command at 14:58
    Current status: Active, reporting normally.
    Action: Monitor for recurrence over next 48h." \
  --priority 3

✅ Ticket created: GLPI #163
   Title: [Security] Defender agent resolved: ArcBox-Win2K22 (Sense crash)
   Priority: 3 (Medium — auto-remediated)
   URL: http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=163
```

## How Copilot CLI Uses the Skill

When you mention Defender, agent health, or security troubleshooting, Copilot CLI:

1. **Matches** your query against the `triggers` in `security-agent-troubleshooting/SKILL.md`
2. **Loads** the skill's 6-step investigation procedure into context
3. **Follows** the steps: API health → service check → connectivity → event logs → remediate → verify
4. **Executes** `az connectedmachine run-command` directly in your terminal
5. **Interprets** results using the skill's root-cause → remediation decision matrix

The key difference from other options: Copilot CLI runs `az CLI` commands **directly in your terminal** — no wrapper functions, SDK code, or hosted endpoints needed.

## Arc Run Command Considerations

The `az connectedmachine run-command` extension is the primary mechanism for remote diagnostics. Key notes:

| Scenario | Works? | Notes |
|---|---|---|
| `Get-Service` / `Restart-Service` | ✅ | Core diagnostic and remediation |
| `Get-WinEvent` (event log query) | ✅ | For Defender-related event analysis |
| `Test-NetConnection` (port check) | ✅ | Defender endpoint connectivity |
| Arc agent itself is down | ❌ | Run command requires healthy Arc agent |
| Server is offline | ❌ | No connectivity path |

**Workaround for Arc agent issues:** If you're on the ArcBox-Client jump box, use Hyper-V direct connection:

```powershell
# From ArcBox-Client terminal (not via Copilot CLI)
Invoke-Command -VMName ArcBox-Win2K22 -ScriptBlock {
    Get-Service Sense, MdCoreSvc | Select Name, Status
} -Credential $cred
```

## Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| **No automatic alert trigger** | Cannot auto-respond when Defender reports unhealthy | Use alongside monitoring scripts for scheduled checks |
| **Interactive only** | Requires engineer to initiate investigation | Use SRE Agent for 24/7 automated remediation |
| **No persistent memory** | Doesn't remember past incidents or patterns | Use custom instructions file for persistent context |
| **Arc agent dependency** | Cannot diagnose if Arc agent itself is down | Use `Invoke-Command -VMName` from ArcBox-Client |
| **Session-scoped** | Each session starts from scratch | Reference previous findings in your prompts |

## Comparison with SRE Agent

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify az CLI) |
| **Alert trigger** | ✅ Automatic | ❌ Manual (engineer initiates) |
| **Skills** | Upload via UI | Copy to `.github/skills/` (identical content) |
| **Tool execution** | Built-in `RunAzCliReadCommands` | Direct terminal (az CLI, no wrapper code) |
| **Event log interpretation** | LLM + skill | LLM + skill (same reasoning quality) |
| **Scheduling** | ✅ Built-in | ❌ Interactive only |
| **Memory** | ✅ Cross-session | ⚠️ Session-only |
| **Auto-remediation** | ✅ Built-in | ✅ Terminal commands (human-approved) |
| **Best for** | 24/7 automated remediation | Ad-hoc investigation by security engineers |
| **Cost** | Azure Agent Units | Copilot license ($19–39/user/mo) |

## See Also

- [Scenario C — Security Troubleshooting (all options)](../scenario-c-security-troubleshooting.md) — comparison of all 4 options
- [`sre-skills/security-agent-troubleshooting/SKILL.md`](../../../sre-skills/security-agent-troubleshooting/SKILL.md) — skill definition
- [Azure Skills Plugin](https://github.com/microsoft/azure-skills) — optional add-on for Azure diagnostics and observability
- [GitHub Copilot CLI documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)
