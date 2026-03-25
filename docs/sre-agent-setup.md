# Azure SRE Agent — Setup & Configuration Guide

Step-by-step guide to deploy and configure Azure SRE Agent for the Wintel Ops Automation project.

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
| `rg-opsauto-sc` | Solution stack (Cosmos DB, Functions, Portal API, alerts) |

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
4. Description: `Use when investigating health check failures or warnings on Windows servers. Covers CPU, memory, disk, services, and event log analysis for Arc-enrolled servers.`
5. Copy the contents of `sre-skills/wintel-health-check-investigation/SKILL.md` into the SKILL.md editor
6. Attach tools:
   - `RunAzCliReadCommands` (built-in)
   - `query-perf-trends` (custom Kusto — create in Step 6 first, or attach later)
7. Click **Save**

### 4b: Security Agent Troubleshooting Skill

1. Create skill: `security-agent-troubleshooting`
2. Description: `Use when a security agent (Defender for Endpoint) is unhealthy, disconnected, or non-compliant. Diagnoses root cause and attempts safe remediation via Arc Run Commands.`
3. Copy contents of `sre-skills/security-agent-troubleshooting/SKILL.md`
4. Attach tools: `RunAzCliReadCommands`, `RunAzCliWriteCommands`, `query-security-alerts`
5. Save

### 4c: Patch Validation Skill

1. Create skill: `patch-validation`
2. Description: `Use before and after Windows patching to validate server health. Runs pre-checks, post-checks, and recommends rollback if needed.`
3. Copy contents of `sre-skills/patch-validation/SKILL.md`
4. Attach tools: `RunAzCliReadCommands`, `query-update-compliance`
5. Save

### 4d: Compliance Investigation Skill

1. Create skill: `compliance-investigation`
2. Description: `Use when investigating non-compliant servers found by Defender for Cloud regulatory compliance assessments.`
3. Copy contents of `sre-skills/compliance-investigation/SKILL.md`
4. Attach tools: `RunAzCliReadCommands`, `query-compliance-state`
5. Save

### 4e: VMware BAU Operations Skill

1. Create skill: `vmware-bau-operations`
2. Description: `Use for VMware/Hyper-V BAU operations: snapshot management, resource monitoring, VM health checks.`
3. Copy contents of `sre-skills/vmware-bau-operations/SKILL.md`
4. Attach tools: `RunAzCliReadCommands`, `RunAzCliWriteCommands`
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

## Step 6: Create Custom Tools

### 6a: Kusto Tools

Go to **Builder → Tools → Create tool → Kusto**

| Tool Name | KQL Query File | Target |
|---|---|---|
| `query-perf-trends` | `sre-tools/kusto/query-perf-trends.kql` | law-arcbox-itpro-sc |
| `query-security-alerts` | `sre-tools/kusto/query-security-alerts.kql` | law-arcbox-itpro-sc |
| `query-compliance-state` | `sre-tools/kusto/query-compliance-state.kql` | law-arcbox-itpro-sc |
| `query-update-compliance` | `sre-tools/kusto/query-update-compliance.kql` | law-arcbox-itpro-sc |

For each:
1. Click **Create tool → Kusto**
2. Enter the tool name
3. Paste the KQL query from the corresponding `.kql` file
4. Set the target workspace to `law-arcbox-itpro-sc`
5. Define parameters (e.g., `server_name`, `time_range`) as specified in the query comments
6. Save

### 6b: Python Tools

Go to **Builder → Tools → Create tool → Python**

| Tool Name | Source File | Purpose |
|---|---|---|
| `glpi-create-ticket` | `sre-tools/python/glpi_tools.py` (create_ticket function) | Create GLPI incident |
| `glpi-query-cmdb` | `sre-tools/python/glpi_tools.py` (query_cmdb function) | Query CMDB for server info |
| `cosmos-query-runs` | `sre-tools/python/cosmos_tools.py` (query_runs function) | Query automation run history |
| `cosmos-check-memories` | `sre-tools/python/cosmos_tools.py` (check_memories function) | Check active suppression rules |

For each:
1. Click **Create tool → Python**
2. Enter the tool name and description
3. Paste the function code from the source file
4. Add pip dependencies: `httpx` (for GLPI), `azure-cosmos` (for Cosmos)
5. Define input parameters
6. Save

## Step 7: Build Custom Subagents

Go to **Builder → Subagent builder**

### 7a: VM Diagnostics Subagent

| Setting | Value |
|---|---|
| Name | `vm-diagnostics` |
| Description | `Specialized in diagnosing Windows/Linux VM issues: performance, disk, services, event logs. Uses Arc Run Commands for remote investigation.` |
| Enable skills | ✅ Yes |
| Tools | `RunAzCliReadCommands`, `RunAzCliWriteCommands`, `query-perf-trends`, `glpi-create-ticket`, `cosmos-check-memories` |
| Instructions | "You are a VM diagnostics specialist. When investigating a server issue: 1) Check current health via Arc Run Commands, 2) Analyze performance trends via KQL, 3) Check if any memory/suppression rules apply, 4) Determine root cause, 5) Create GLPI ticket if human action needed." |

### 7b: Security Troubleshooting Subagent

| Setting | Value |
|---|---|
| Name | `security-troubleshooter` |
| Description | `Specialized in diagnosing Defender for Endpoint agent failures: checks agent health, connectivity, event logs, and attempts safe remediation.` |
| Enable skills | ✅ Yes |
| Tools | `RunAzCliReadCommands`, `RunAzCliWriteCommands`, `query-security-alerts`, `glpi-create-ticket` |
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
On ArcBox-Client, stress-test a VM:
```powershell
# Spike CPU on ArcBox-Win2K22 via Arc Run Command
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name stressCPU \
  --script "while (\$true) { [math]::Sqrt(12345) }" \
  --async-execution true
```

Wait for the `alert-high-cpu` to fire → SRE Agent should auto-receive the incident and start investigating.

### Test 3: Security Agent Troubleshooting
```powershell
# Stop Defender service on a VM
az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name stopDefender \
  --script "Stop-Service -Name 'WinDefend' -Force"
```

Defender for Cloud should flag the agent as unhealthy → SRE Agent picks it up and uses the security-agent-troubleshooting skill.

## Troubleshooting

| Issue | Solution |
|---|---|
| Agent can't see Arc servers | Verify RBAC: managed identity needs Reader on `rg-arcbox-itpro` |
| Incidents not arriving | Check Azure Monitor alert → Action Group → confirm SRE Agent integration is linked |
| Skills not loading | Ensure skill description matches the context. Skills are loaded automatically — don't use `/skill` command |
| Subagent not invoked | Type `/agent vm-diagnostics` to explicitly invoke. Check tools are attached. |
| KQL tools failing | Verify Log Analytics workspace ID is correct and managed identity has Log Analytics Reader role |

