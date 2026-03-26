# Azure SRE Agent — Setup & Configuration Guide

Step-by-step guide to deploy and configure Azure SRE Agent for the Wintel Ops Automation project. See [architecture.md](architecture.md) for the overall system design and [sre-skills.md](sre-skills.md) for the skill inventory.

## Prerequisites

- Azure subscription with the ArcBox demo environment deployed (`rg-arcbox-itpro`)
- Owner or Contributor role on the subscription
- Access to [sre.azure.com](https://sre.azure.com)

## Step 1: Create the SRE Agent Instance

1. Navigate to [sre.azure.com](https://sre.azure.com)
2. Click **Create a new agent**
3. Configure:
   - **Name:** `wintel-ops-agent`
   - **Subscription:** `31adb513-7077-47bb-9567-8e9d2a462bcf` (or your subscription)
   - **Region:** `Sweden Central` (same as ArcBox)
4. Click **Create** — this provisions a Container App + managed identity automatically

## Step 2: Add Managed Resource Groups

Instead of manual RBAC commands, add resource groups directly in the SRE Agent setup. The agent auto-assigns Reader, Log Analytics Reader, and Monitoring Reader roles to its managed identity.

1. In the SRE Agent portal, go to **Settings → Azure settings**
2. Click **Add resource group**
3. Add both resource groups:

| Resource Group | Purpose |
|---|---|
| `rg-arcbox-itpro` | ArcBox VMs + Arc-enrolled servers + Log Analytics |
| `rg-opsauto-sc` | Solution stack (SRE Agent, alerts) |

4. Click **Save**

The agent now has read access to all resources in both groups. For **write operations** (Arc Run Commands, remediation), you can either:
- Grant Contributor manually via CLI if needed for specific actions
- Or use the **on-behalf-of (OBO)** flow — the agent prompts you for approval when it needs elevated permissions

Verify: In the SRE Agent chat, ask *"What Arc-enabled servers are in resource group rg-arcbox-itpro?"* — you should see all 5 Arc servers.

> **Note:** If ArcBox-Client was deallocated (auto-shutdown), start it first: `az vm start --resource-group rg-arcbox-itpro --name ArcBox-Client`. Wait 3-5 minutes for nested VMs to boot and Arc agents to reconnect. Disable auto-shutdown during setup: `az vm auto-shutdown --resource-group rg-arcbox-itpro --name ArcBox-Client --off`

## Step 3: Connect Connectors (Outlook, Teams, MCP)

Before configuring incident response, set up the communication and data connectors your agent will use.

### 3a: Outlook Connector (Email Notifications)

1. Go to **Builder → Connectors**
2. Click **Outlook**
3. Sign in with your Microsoft 365 account
4. Grant permissions for sending emails on behalf of the agent
5. Click **Save**

The agent can now send investigation summaries, compliance reports, and incident notifications via email.

### 3b: Teams Connector (Channel Notifications)

1. Go to **Builder → Connectors**
2. Click **Teams**
3. Sign in and select the Teams channel for ops notifications (e.g., `#wintel-ops-alerts`)
4. Grant permissions for posting messages
5. Click **Save**

The agent can now post incident updates, health check summaries, and remediation results to your Teams channel.

### 3c: Azure Monitor (Incident Platform — Connected by Default)

Azure Monitor is connected **automatically** when you assign resource groups to the agent (Step 2). You don't need to select specific alert rules — **all alerts from your managed resource groups flow to the agent automatically**.

To verify:
1. Go to **Settings → Incident Platform**
2. Confirm **Azure Monitor** is shown as the active platform
3. Your 3 alert rules (`alert-heartbeat-loss`, `alert-high-cpu`, `alert-low-disk`) in `rg-opsauto-sc` will fire alerts that the agent receives automatically

> **Tip:** When an alert fires, it appears as a **rich incident card** in the agent's chat — showing severity, affected resource, timestamp, and description.

## Step 4: Upload Skills

Skills give the agent your team's specific procedures and should be uploaded **before** creating response plans, so you can reference them in the plan instructions.

For each skill in `sre-skills/`, go to **Builder → Skills → Create skill**:

### 4a: Health Check Investigation Skill

1. Go to **Builder → Skills**
2. Click **Create skill**
3. Name: `wintel-health-check-investigation`
4. Description: `Investigates Windows server health check failures and warnings reported by the automated health check system.`
5. Copy the contents of `sre-skills/wintel-health-check-investigation/SKILL.md` into the SKILL.md editor
6. Attach tools: `glpi-create-ticket` (custom — for escalation tickets)
7. Click **Save**

> **Note:** Built-in tools (Azure CLI, Log Analytics, diagnostics, remediation) are **automatically available** to all skills — you don't need to attach them. Only attach custom tools you created (GLPI, etc.).

### 4b: Security Agent Troubleshooting Skill

1. Create skill: `security-agent-troubleshooting`
2. Description: `Diagnoses and remediates Microsoft Defender for Endpoint agent issues on Windows servers.`
3. Copy contents of `sre-skills/security-agent-troubleshooting/SKILL.md`
4. Attach tools: `glpi-create-ticket`
5. Save

### 4c: Patch Validation Skill

1. Create skill: `patch-validation`
2. Description: `Validates server health before and after Windows patch deployment. Assesses rollback need.`
3. Copy contents of `sre-skills/patch-validation/SKILL.md`
4. Attach tools: `glpi-create-ticket`
5. Save

### 4d: Compliance Investigation Skill

1. Create skill: `compliance-investigation`
2. Description: `Investigates non-compliant controls found by Microsoft Defender for Cloud AND Azure Policy, correlates findings across both sources, and prioritizes remediation.`
3. Copy contents of `sre-skills/compliance-investigation/SKILL.md`
4. Attach tools: `glpi-create-ticket`
5. Save

### 4e: VMware BAU Operations Skill

1. Create skill: `vmware-bau-operations`
2. Description: `Performs VMware/Hyper-V BAU tasks including snapshot cleanup, resource monitoring, and VM health checks.`
3. Copy contents of `sre-skills/vmware-bau-operations/SKILL.md`
4. Attach tools: `glpi-create-ticket`
5. Save

## Step 5: Create Incident Response Plans

1. Go to **Automate → Incident response**
2. Click **New response plan**

### Plan A: Critical Incidents (Severity 0–1)

| Setting | Value |
|---|---|
| Name | `critical-incident-response` |
| Severity filter | Sev 0, Sev 1 |
| Run mode | **Semi-autonomous** (investigate + propose fix, wait for approval) |
| Instructions | "Investigate the incident by checking server health, recent changes, and correlating with other alerts. Use the wintel-health-check-investigation and security-agent-troubleshooting skills. Propose remediation but wait for human approval. Notify the #wintel-ops-alerts Teams channel with findings. Send email summary to the ops team via Outlook." |

### Plan B: Warning Incidents (Severity 2–3)

| Setting | Value |
|---|---|
| Name | `warning-incident-response` |
| Severity filter | Sev 2, Sev 3 |
| Run mode | **Autonomous** (investigate + auto-remediate) |
| Instructions | "Investigate and auto-remediate if safe. For high CPU: identify top process. For low disk: identify largest files. For agent issues: attempt service restart. Create a GLPI ticket with findings. Post a summary to the Teams channel." |

> **Tip:** Enable the **Quickstart response plan** when connecting Azure Monitor for an immediate default (Sev3 = autonomous). Then customize with the plans above.

## Step 6: Set Up KQL Reference Queries + Create Custom Tools

### 6a: Log Analytics Access (Built-in — No Kusto Connector Needed)

SRE Agent already has **built-in access to Log Analytics** via the managed resource groups added in Step 2. The agent's managed identity was automatically granted **Log Analytics Reader** when you added `rg-arcbox-itpro`.

> **Important:** Do NOT use the Kusto connector with `ade.loganalytics.io` ADX proxy URLs. The SRE Agent Kusto connector is designed for standalone Azure Data Explorer clusters, not Log Analytics workspaces. For Log Analytics queries, use one of the approaches below.

**How to run KQL queries against Log Analytics:**

- **Option 1 — Chat directly:** Paste KQL into the agent chat: *"Run this KQL against my Log Analytics workspace: `Perf | where Computer == 'ArcBox-Win2K22' | summarize avg(CounterValue) by CounterName`"*
- **Option 2 — `RunAzCliReadCommands` tool (recommended):** The built-in `RunAzCliReadCommands` tool can execute `az monitor log-analytics query` commands directly:
  ```
  az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query "<KQL>" -o json
  ```
  For Azure Resource Graph queries (e.g., compliance state), use:
  ```
  az graph query -q "<KQL>" --subscriptions <subscription_id> -o json
  ```

**No custom tools needed for KQL.** The built-in `RunAzCliReadCommands` tool (already attached to skills) handles all Log Analytics and Resource Graph queries. Custom Python tools wrapping `subprocess` + `az CLI` **will not work** in the SRE Agent sandbox (az CLI is not installed in the Python execution environment).

### 6b: KQL Reference Queries

The KQL files in `sre-tools/kusto/` serve as **reference queries** — they document the exact KQL the agent should run for common scenarios. You can:
- Paste them into skill instructions so the agent knows the query patterns
- Let the agent use them directly via `RunAzCliReadCommands`

| Reference Query | Source File | Execution Method | Purpose |
|---|---|---|---|
| Performance trends | `sre-tools/kusto/query-perf-trends.kql` | `az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c` | CPU/memory/disk trends over time |
| Security alerts | `sre-tools/kusto/query-security-alerts.kql` | `az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c` | Defender for Cloud security alerts |
| Compliance state | `sre-tools/kusto/query-compliance-state.kql` | `az graph query` (Resource Graph, not Log Analytics) | Regulatory compliance status |
| Update compliance | `sre-tools/kusto/query-update-compliance.kql` | `az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c` | Missing patches by classification |

> **Note:** `query-compliance-state` queries Azure Resource Graph, not Log Analytics. Use `az graph query -q "<KQL>"` instead of `az monitor log-analytics query`.

### 6c: Create Python Tools (GLPI Only)

Go to **Builder → Subagent builder → Create → Tool → Python tool**

Each tool must follow the SRE Agent pattern: a `main()` function with typed parameters returning a `dict`. See [Python tools docs](https://learn.microsoft.com/en-us/azure/sre-agent/python-code-execution).

| Tool Name | Description | Source | Parameters |
|---|---|---|---|
| `glpi-create-ticket` | Create an incident ticket in GLPI | `sre-tools/python/glpi_tools.py` (first `main()`) | `title` (str), `description` (str), `priority` (str) |
| `glpi-query-cmdb` | Query GLPI CMDB for server CI record | `sre-tools/python/glpi_tools.py` (second `main()`) | `server_name` (str) |

For each tool:
1. Click **Create → Tool → Python tool**
2. Enter the tool name and description
3. Paste the `main()` function code from the source file
4. Click **Test** with sample inputs to verify
5. Click **Create tool**

> **Note:** Each `.py` file contains multiple tool functions. Create each as a **separate** Python tool — paste only the relevant `main()` function for each tool.

## Step 7: Build Custom Subagents

Go to **Builder → Subagent builder**

### 7a: VM Diagnostics Subagent

| Setting | Value |
|---|---|
| Name | `vm-diagnostics` |
| Description | `Specialized in diagnosing Windows/Linux VM issues: performance, disk, services, event logs. Uses Arc Run Commands for remote investigation.` |
| Enable skills | ✅ Yes |
| Tools | `RunAzCliReadCommands`, `RunAzCliWriteCommands`, `glpi-create-ticket` |
| Instructions | "You are a VM diagnostics specialist. When investigating a server issue: 1) Check current health via Arc Run Commands, 2) Analyze performance trends via KQL, 3) Determine root cause, 4) Create GLPI ticket if human action needed." |

### 7b: Security Troubleshooting Subagent

| Setting | Value |
|---|---|
| Name | `security-troubleshooter` |
| Description | `Specialized in diagnosing Defender for Endpoint agent failures: checks agent health, connectivity, event logs, and attempts safe remediation.` |
| Enable skills | ✅ Yes |
| Tools | `RunAzCliReadCommands`, `RunAzCliWriteCommands`, `glpi-create-ticket` |
| Instructions | "You are a security agent specialist. When a Defender agent is unhealthy: 1) Check service status via Arc Run Command, 2) Review event logs for errors, 3) Test connectivity to Defender cloud endpoints, 4) Attempt safe remediation (restart service, force update), 5) If fix fails, escalate with full diagnostic context." |

Test each subagent in the **Playground** before going live.

## Step 8: Configure Scheduled Tasks

Go to **Schedule tasks** tab:

### 8a: Proactive Health Check

| Setting | Value |
|---|---|
| Task name | `proactive-health-scan` |
| Schedule | Every 6 hours (`0 */6 * * *`) |
| Instructions | "Run a proactive health scan across all Arc-enrolled servers in rg-arcbox-itpro. Check CPU, memory, disk, and critical services. Report any anomalies. If a server has a health issue, use the wintel-health-check-investigation skill to diagnose." |

### 8b: Security Posture Check

| Setting | Value |
|---|---|
| Task name | `security-posture-check` |
| Schedule | Daily at 07:00 UTC (`0 7 * * *`) |
| Instructions | "Check the security posture of all Arc-enrolled servers. Verify Defender for Endpoint agents are healthy and reporting. Check for new security alerts in the last 24 hours. Use the compliance-investigation skill if any non-compliance is found." |

## Step 9: Set Up MCP Server (Optional)

If you want SRE Agent to access GLPI directly:

1. Go to **Integrations → Connectors → MCP**
2. Click **Add MCP server**
3. Configure:
   - **Name:** `glpi-itsm`
   - **URL:** `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`
   - **Auth:** API token (configure in GLPI admin → API settings)
4. Once connected, SRE Agent auto-discovers GLPI tools (ticket CRUD, CMDB queries)
5. Assign `glpi-itsm/*` tools to your subagents

## Step 10: Verify Everything Works

### Test 1: Chat Query
In the SRE Agent chat, type:
> "What servers are in my environment and what's their health status?"

Expected: Agent uses `RunAzCliReadCommands` to query Arc servers, returns list with health info.

### Test 2: Trigger an Incident

RDP into ArcBox-Client (`arcdemo` / `ArcBoxD3mo2026!`) and run these commands in PowerShell to spike CPU and stop a service on ArcBox-Win2K22:

```powershell
# From ArcBox-Client PowerShell — connects to nested VM via Hyper-V PS Direct
$cred = New-Object PSCredential("arcdemo", (ConvertTo-SecureString "JS123!!" -AsPlainText -Force))

# Spike CPU on all cores for 10 minutes
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    $end = (Get-Date).AddMinutes(10)
    1..[Environment]::ProcessorCount | ForEach-Object {
        Start-Job -ScriptBlock {
            param($endTime)
            while ((Get-Date) -lt $endTime) { [math]::Sqrt(12345) }
        } -ArgumentList $end
    }
    Write-Output "CPU stress started: $([Environment]::ProcessorCount) cores for 10 min"
}

# Also stop a service to create a correlated alert
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    Stop-Service -Name W32Time -Force
    Write-Output "W32Time stopped: $((Get-Service W32Time).Status)"
}
```

> **Nested VM credentials:** Username `arcdemo`, password `JS123!!` (set by ArcBox bootstrap).

Verify CPU is spiking:
```powershell
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 3).CounterSamples |
        ForEach-Object { "CPU: $([math]::Round($_.CookedValue))%" }
}
```

Wait 5-10 minutes for the `alert-high-cpu` alert rule to fire → SRE Agent should auto-receive the incident and start investigating.

**Clean up after testing:**
```powershell
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    Get-Job | Stop-Job | Remove-Job
    Start-Service W32Time
    Write-Output "Cleaned up. CPU=$(Get-Counter '\Processor(_Total)\% Processor Time' -MaxSamples 1 | Select-Object -Expand CounterSamples | Select-Object -Expand CookedValue | ForEach-Object {[math]::Round($_)})% W32Time=$((Get-Service W32Time).Status)"
}
```

### Test 3: Security Agent Troubleshooting

From ArcBox-Client PowerShell, disable the Defender agent:

```powershell
$cred = New-Object PSCredential("arcdemo", (ConvertTo-SecureString "JS123!!" -AsPlainText -Force))

# Stop Windows Defender service
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    # Attempt to stop Defender — may require elevated/TrustedInstaller
    Stop-Service -Name WinDefend -Force -ErrorAction SilentlyContinue
    Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue
    Write-Output "Defender status: $((Get-Service WinDefend -ErrorAction SilentlyContinue).Status)"
    Write-Output "Realtime monitoring: $((Get-MpPreference).DisableRealtimeMonitoring)"
}
```

> **Note:** On some Windows Server versions, stopping WinDefend requires TrustedInstaller privileges. If the service doesn't stop, disabling real-time monitoring (`Set-MpPreference`) is sufficient — Defender for Cloud will still flag the server as unhealthy.

Defender for Cloud should detect the unhealthy agent within 15-30 minutes → SRE Agent picks it up and uses the `security-agent-troubleshooting` skill to diagnose.

**Alternatively**, ask SRE Agent to investigate proactively:
> "Check if Defender for Endpoint is healthy on all my Arc servers"

**Clean up after testing:**
```powershell
Invoke-Command -VMName ArcBox-Win2K22 -Credential $cred -ScriptBlock {
    Set-MpPreference -DisableRealtimeMonitoring $false
    Start-Service WinDefend -ErrorAction SilentlyContinue
    Write-Output "Restored: Defender=$((Get-Service WinDefend -ErrorAction SilentlyContinue).Status) RT=$(-not (Get-MpPreference).DisableRealtimeMonitoring)"
}
```

## Troubleshooting

| Issue | Solution |
|---|---|
| Agent can't see Arc servers | Verify RBAC: managed identity needs Reader on `rg-arcbox-itpro` |
| Incidents not arriving | Check Azure Monitor alert → Action Group → confirm SRE Agent integration is linked |
| Skills not loading | Ensure skill description matches the context. Skills are loaded automatically — don't use `/skill` command |
| Subagent not invoked | Type `/agent vm-diagnostics` to explicitly invoke. Check tools are attached. |
| KQL queries failing | Verify workspace ID `f98fca75-7479-45e5-bf0c-87b56a9f9e8c` is correct, managed identity has Log Analytics Reader role, and you're using `az monitor log-analytics query` (not the Kusto connector) |

