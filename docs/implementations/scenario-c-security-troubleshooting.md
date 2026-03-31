# Scenario C: Security Agent Troubleshooting — Implementation Comparison (All 4 Options)

> **Automation ratio:** 60% deterministic scripts / 40% AI reasoning
>
> **What the 60% handles:** Detect unhealthy Defender agent (Azure Monitor alert or Defender for Cloud recommendation), check service status, test connectivity, restart service, force definition update.
>
> **What the 40% AI adds:** Interpret Windows Event Log patterns (correlate Event IDs with known Defender issues), structured multi-step diagnosis following SOP, determine if network/firewall issue vs. local failure, decide whether to escalate or auto-fix, produce contextualized GLPI ticket with full diagnostic narrative.

This document compares how all four AI tier options implement the security agent troubleshooting scenario using the same `security-agent-troubleshooting` skill, tools, and environment. If you're unsure which option to pick, see the [decision tree in ai-tier-options.md](../ai-tier-options.md#recommendation-decision-tree).

## Shared Environment

| Component | Value |
|-----------|-------|
| **Resource group** | `rg-arcbox-itpro` |
| **Region** | `swedencentral` |
| **Windows VMs** | `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL` |
| **Log Analytics workspace** | `f98fca75-7479-45e5-bf0c-87b56a9f9e8c` |
| **GLPI instance** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **Defender services** | `MdCoreSvc` (Defender core), `Sense` (EDR telemetry) |
| **Defender endpoints** | `winatp-gw-eus.microsoft.com`, `winatp-gw-neu.microsoft.com`, `us-v20.events.data.microsoft.com` |

## The Skill — `security-agent-troubleshooting`

All four options use the same [`sre-skills/security-agent-troubleshooting/SKILL.md`](../../sre-skills/security-agent-troubleshooting/SKILL.md). The skill defines:

```yaml
name: security-agent-troubleshooting
version: 1.0.0
description: Diagnoses and remediates Microsoft Defender for Endpoint agent issues.
triggers:
  - Defender for Cloud alert: "Agent health issue detected"
  - Defender device health shows "not reporting" for >30 minutes
  - User reports Defender not working on a server
tools:
  - RunAzCliReadCommands
  - RunAzCliWriteCommands
  - glpi-create-ticket
  - glpi-query-cmdb
```

**Investigation flow (identical across all options):**

| Step | Action | Tool |
|------|--------|------|
| 1 | Get Defender agent health status | `az CLI` → Defender API |
| 2 | Check local services (`MdCoreSvc`, `Sense`) via Arc | Arc Run Command |
| 3 | Test network connectivity to Defender endpoints | Arc Run Command (PowerShell) |
| 4 | Remediate based on root cause | Arc Run Command (restart) or escalate |
| 5 | Verify remediation (re-check health) | `az CLI` → Defender API |
| 6 | Create GLPI ticket with full diagnostic output | GLPI REST API |

## Capability Comparison

| Capability | What's Needed | SRE Agent (Option 0) | Agent Framework (Option A) | Foundry Agent (Option B) | Copilot CLI (Option C) |
|---|---|---|---|---|---|
| **Detect unhealthy agent** | Azure Monitor alert or Defender recommendation | ✅ Built-in alert reception | Webhook handler + alert poll | Logic App trigger → agent | ❌ Manual (engineer sees alert) |
| **Structured diagnosis** | Multi-step check (services, logs, connectivity, disk) | Skill auto-loaded → step-by-step | Skill via `SkillsProvider` → step-by-step | Skill in `instructions` → step-by-step | Skill auto-loaded → step-by-step |
| **Interpret event logs** | LLM correlates Event IDs with known issues | Skill references guide interpretation | Skill context + LLM reasoning | Agent instructions + LLM reasoning | Skill context + LLM reasoning |
| **Safe remediation** | Restart service, force definition update | Built-in `RunAzCliWriteCommands` | `FunctionTool` wrapping `az CLI` | Function tool wrapping `az CLI` | Terminal (`az connectedmachine run-command`) |
| **Escalate with context** | Create GLPI ticket with full diagnostic output | Custom Python tool (`glpi-create-ticket`) | `FunctionTool` (same GLPI code) | Function tool (same GLPI code) | Terminal (`python glpi_tools.py` / `curl`) |
| **Check disk space** | Ensure Defender has room for signatures | Arc Run Command | `FunctionTool` → Arc Run Command | Function tool → Arc Run Command | Terminal `az connectedmachine run-command` |

## Skills Reusability

| Platform | How `security-agent-troubleshooting` Loads |
|---|---|
| **SRE Agent** | Upload `SKILL.md` via Builder → Skills UI — auto-activates on "Defender" / "agent health" triggers |
| **Agent Framework** | `SkillsProvider(skill_paths=["./sre-skills"])` — auto-discovers and injects when trigger matches |
| **Foundry Agent** | `SKILL.md` content read and injected as agent `instructions` parameter |
| **Copilot CLI** | Copy to `.github/skills/security-agent-troubleshooting/SKILL.md` — auto-discovers on load |

---

## Option 0: SRE Agent (Recommended)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Defender for Cloud                                          │
│  Alert: "Agent health issue — ArcBox-Win2K22 not reporting" │
└──────────────────────────────┬──────────────────────────────┘
                               │ auto-trigger
                        ┌──────▼──────────────────────────┐
                        │      Azure SRE Agent              │
                        │                                   │
                        │  Skill: security-agent-           │
                        │         troubleshooting            │
                        │  (auto-loaded by trigger match)   │
                        │                                   │
                        │  Step 1: Defender API health      │
                        │  Step 2: Arc → check services     │
                        │  Step 3: Arc → test connectivity  │
                        │  Step 4: Arc → remediate          │
                        │  Step 5: Verify health restored   │
                        │  Step 6: Create GLPI ticket       │
                        │                                   │
                        │  Tools:                           │
                        │  • RunAzCliReadCommands            │
                        │  • RunAzCliWriteCommands           │
                        │  • glpi-create-ticket              │
                        │  • glpi-query-cmdb                 │
                        └───────┬─────────┬────────┬────────┘
                                │         │        │
                          Azure Arc    GLPI     Defender
                       (Run Command)  (Ticket)   (API)
```

### How Alerts Are Handled

SRE Agent auto-receives the Defender for Cloud alert and activates the `security-agent-troubleshooting` skill:

```
Trigger match: "Agent health issue detected" → SKILL.md triggers[0]
```

The agent then follows the 6-step investigation procedure from the skill without human intervention.

### How the `security-agent-troubleshooting` Skill Is Loaded

Upload via **Builder → Skills → Upload SKILL.md**. The skill's triggers are:

```yaml
triggers:
  - Defender for Cloud alert: "Agent health issue detected"
  - Defender device health shows "not reporting" for >30 minutes
  - User reports Defender not working on a server
```

When an incoming alert or user query matches any trigger, the full skill content (investigation steps, remediation table, tool references) is injected into the agent's context.

### Example Interaction

> **Defender for Cloud Alert → SRE Agent (automatic)**
>
> Alert: "Defender device health — ArcBox-Win2K22 not reporting for 45 minutes"

**Agent Response:**

> **🔒 Security Agent Troubleshooting — ArcBox-Win2K22**
>
> **Step 1 — Defender API Health Check:**
> - `onboardingStatus`: Onboarded ✅
> - `healthStatus`: Inactive ❌
> - `lastSeen`: 2025-01-15T13:15:00Z (45 min ago)
> - `agentVersion`: 10.8990.22621.1105
>
> **Step 2 — Local Service Check (via Arc Run Command):**
> - `MdCoreSvc`: Running ✅
> - `Sense`: Stopped ❌
> - `LastBoot`: 2025-01-12T08:00:00Z (3 days ago — not a reboot issue)
>
> **Step 3 — Network Connectivity:**
> - `winatp-gw-eus.microsoft.com:443` → Reachable ✅
> - `winatp-gw-neu.microsoft.com:443` → Reachable ✅
> - `us-v20.events.data.microsoft.com:443` → Reachable ✅
>
> **Step 4 — Root Cause & Remediation:**
> - Diagnosis: `Sense` service stopped while `MdCoreSvc` is running. Network OK.
> - Event Log: Event ID 7036 — "The Windows Defender Advanced Threat Protection Service service entered the stopped state" at 13:15 UTC.
> - Likely cause: Service crash (no network or disk issue detected).
> - **Remediation:** Restarted `Sense` service via Arc Run Command → Status: **Running** ✅
>
> **Step 5 — Verification (after 5-min wait):**
> - `healthStatus`: Active ✅
> - `lastSeen`: 2025-01-15T14:05:00Z (just now)
>
> **Step 6 — Ticket Created:**
> [GLPI #160 — [Security] Defender agent issue resolved: ArcBox-Win2K22](http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id=160) (P3 — auto-remediated)

### What Makes SRE Agent Unique

| Feature | SRE Agent | Others |
|---------|-----------|--------|
| **Auto-triggered by Defender alert** | ✅ Built-in | ❌ Must build trigger chain |
| **Follows SKILL.md step-by-step** | ✅ Native skill execution | ✅ But requires code to load skill |
| **Memory of past agent issues** | ✅ Remembers resolution patterns | ❌ Must implement state |
| **No custom code** | ✅ Portal only | ❌ Python code required |

---

## Option A: Microsoft Agent Framework

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Defender for Cloud Alert ──→ Action Group ──→ Webhook       │
└──────────────────────────────────┬───────────────────────────┘
                                   │ HTTP POST
┌──────────────────────────────────▼───────────────────────────┐
│  Your host (Azure Container Apps / local dev)                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         security_agent_troubleshoot.py                   │  │
│  │                                                          │  │
│  │  ┌──────────────┐   ┌──────────────────────────────┐    │  │
│  │  │ SkillsProvider│   │ FunctionTools                 │    │  │
│  │  │ (auto-loads   │   │ ┌──────────────────────────┐ │    │  │
│  │  │  security-    │   │ │check_defender_health     │ │    │  │
│  │  │  agent-       │   │ │check_services_via_arc    │ │    │  │
│  │  │  trouble-     │   │ │test_connectivity_via_arc │ │    │  │
│  │  │  shooting)    │   │ │check_event_logs_via_arc  │ │    │  │
│  │  └──────────────┘   │ │restart_service_via_arc   │ │    │  │
│  │                      │ │force_definition_update   │ │    │  │
│  │  ┌──────────────┐   │ │check_disk_space_via_arc  │ │    │  │
│  │  │ AzureOpenAI  │   │ │create_glpi_ticket        │ │    │  │
│  │  │ Responses API│   │ └──────────────────────────┘ │    │  │
│  │  └──────────────┘   └──────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Key Code — Diagnostic Tools

```python
"""Security Agent Troubleshooting — Microsoft Agent Framework implementation."""

from agent_framework import FunctionTool, SkillsProvider
from azure.ai.openai import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential

RESOURCE_GROUP = "rg-arcbox-itpro"
LOCATION = "swedencentral"
WORKSPACE_ID = "f98fca75-7479-45e5-bf0c-87b56a9f9e8c"

# Auto-load all skills
skills = SkillsProvider(skill_paths=["./sre-skills"])


@FunctionTool
def check_defender_health(server_name: str) -> dict:
    """Get Defender for Endpoint agent health from the Defender API."""
    return _az([
        "graph", "query", "-q",
        f"""Resources
        | where type == 'microsoft.hybridcompute/machines'
        | where name == '{server_name}'
        | project name, properties.status,
          defenderStatus=properties.detectedProperties.mdeDeviceHealthStatus,
          lastSeen=properties.detectedProperties.mdeLastSeen,
          onboarded=properties.detectedProperties.mdeOnboardingStatus"""
    ])


@FunctionTool
def check_services_via_arc(server_name: str) -> dict:
    """Check MdCoreSvc and Sense service status via Arc Run Command."""
    script = """
    $svc = Get-Service MdCoreSvc -ErrorAction SilentlyContinue
    $mde = Get-Service "Sense" -ErrorAction SilentlyContinue
    @{
        MdCoreSvc = if ($svc) { $svc.Status.ToString() } else { "NotFound" }
        SenseService = if ($mde) { $mde.Status.ToString() } else { "NotFound" }
        LastBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    } | ConvertTo-Json
    """
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"CheckDefenderSvc-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def test_connectivity_via_arc(server_name: str) -> dict:
    """Test network connectivity to Defender cloud endpoints via Arc."""
    script = """
    $endpoints = @(
        "winatp-gw-eus.microsoft.com",
        "winatp-gw-neu.microsoft.com",
        "us-v20.events.data.microsoft.com"
    )
    $results = $endpoints | ForEach-Object {
        $result = Test-NetConnection -ComputerName $_ -Port 443 -InformationLevel Quiet
        [PSCustomObject]@{ Endpoint = $_; Reachable = $result }
    }
    $results | ConvertTo-Json
    """
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"TestConnectivity-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def check_event_logs_via_arc(server_name: str, hours_back: int = 24) -> dict:
    """Query Windows Event Log for Defender-related events via Arc."""
    script = f"""
    $cutoff = (Get-Date).AddHours(-{hours_back})
    Get-WinEvent -FilterHashtable @{{
        LogName = 'System', 'Application'
        Level = 1,2,3  # Critical, Error, Warning
        StartTime = $cutoff
    }} -MaxEvents 50 -ErrorAction SilentlyContinue |
    Where-Object {{ $_.Message -match 'Defender|MdCoreSvc|Sense|Antimalware' }} |
    Select-Object TimeCreated, Id, LevelDisplayName, Message |
    ConvertTo-Json -Depth 3
    """
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"CheckEventLogs-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def restart_service_via_arc(server_name: str, service_name: str) -> dict:
    """Restart a Windows service on an Arc-enrolled server (safe remediation)."""
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"RestartSvc-{service_name}",
        "--location", LOCATION,
        "--script",
        f"Restart-Service '{service_name}' -Force; Start-Sleep 5; "
        f"Get-Service '{service_name}' | Select Name, Status | ConvertTo-Json",
        "--async-execution", "false",
    ])


@FunctionTool
def force_definition_update(server_name: str) -> dict:
    """Force a Defender antimalware definition update via Arc."""
    script = 'Update-MpSignature -UpdateSource MicrosoftUpdateServer; Get-MpComputerStatus | Select AntivirusSignatureLastUpdated, AntivirusSignatureVersion | ConvertTo-Json'
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"ForceDefUpdate-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def check_disk_space_via_arc(server_name: str) -> dict:
    """Check available disk space on the server (Defender needs room for signatures)."""
    script = 'Get-CimInstance Win32_LogicalDisk | Where DeviceID -eq "C:" | Select DeviceID, @{N="FreeGB";E={[math]::Round($_.FreeSpace/1GB,1)}}, @{N="TotalGB";E={[math]::Round($_.Size/1GB,1)}} | ConvertTo-Json'
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"CheckDisk-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def create_glpi_ticket(title: str, description: str, priority: str = "3") -> dict:
    """Create an incident ticket in GLPI with full diagnostic context."""
    import requests
    # OAuth2 token flow — same as sre-tools/python/glpi_tools.py
    token = _get_glpi_token()
    resp = requests.post(
        f"{GLPI_BASE}/api.php/v2.2/Assistance/Ticket",
        json={"name": title, "content": description, "type": 1,
              "urgency": int(priority), "impact": int(priority),
              "priority": int(priority)},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    ticket_id = resp.json()["id"]
    return {"ticket_id": ticket_id, "title": title, "priority": priority,
            "url": f"{GLPI_BASE}/front/ticket.form.php?id={ticket_id}"}


# --- Agent ---

SYSTEM_INSTRUCTIONS = """\
You are a security agent troubleshooting specialist for the ArcBox environment.

When investigating Defender agent issues, follow the loaded skill's 6-step procedure:
1. Check Defender API health (onboarding status, health status, last seen).
2. Check local services (MdCoreSvc, Sense) via Arc Run Command.
3. Test network connectivity to Defender cloud endpoints.
4. Remediate based on root cause (see skill's remediation table).
5. Verify remediation after 5 minutes.
6. Always create a GLPI ticket (even for auto-remediated issues).

Interpret Event IDs: 7036=service state change, 1116=malware detected,
1006=scan error, 2001=definition update failed, 5007=config changed.

Environment:
  Resource group: rg-arcbox-itpro | Region: swedencentral
  Log Analytics workspace: f98fca75-7479-45e5-bf0c-87b56a9f9e8c
"""

agent = client.as_agent(
    model="gpt-4o",
    name="SecurityAgentTroubleshootAgent",
    instructions=SYSTEM_INSTRUCTIONS,
    tools=[
        check_defender_health, check_services_via_arc,
        test_connectivity_via_arc, check_event_logs_via_arc,
        restart_service_via_arc, force_definition_update,
        check_disk_space_via_arc, create_glpi_ticket,
    ],
    context_providers=[skills],  # Auto-loads security-agent-troubleshooting skill
)
```

### How the `security-agent-troubleshooting` Skill Is Loaded

```python
skills = SkillsProvider(skill_paths=["./sre-skills"])
```

`SkillsProvider` discovers `sre-skills/security-agent-troubleshooting/SKILL.md`, parses its triggers, and auto-injects the skill content when the user's query matches "Defender", "agent health", "not reporting", etc.

### Example Interaction

```
Security Agent Troubleshoot Agent (Agent Framework) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: ArcBox-Win2K22 shows "not reporting" in Defender for 45 minutes. Investigate.

Agent: Loading security-agent-troubleshooting skill. Following the 6-step procedure.

  → Step 1: check_defender_health("ArcBox-Win2K22")
    onboardingStatus: Onboarded ✅
    healthStatus: Inactive ❌
    lastSeen: 2025-01-15T13:15:00Z (45 min ago)

  → Step 2: check_services_via_arc("ArcBox-Win2K22")
    MdCoreSvc: Running ✅
    Sense: Stopped ❌
    LastBoot: 2025-01-12T08:00:00Z

  → Step 3: test_connectivity_via_arc("ArcBox-Win2K22")
    winatp-gw-eus.microsoft.com:443 → Reachable ✅
    winatp-gw-neu.microsoft.com:443 → Reachable ✅
    us-v20.events.data.microsoft.com:443 → Reachable ✅

  → check_event_logs_via_arc("ArcBox-Win2K22", hours_back=6)
    Event ID 7036 at 13:15 UTC: "Windows Defender Advanced Threat
    Protection Service entered the stopped state"
    No prior errors — likely a transient service crash.

  → Step 4: restart_service_via_arc("ArcBox-Win2K22", "Sense")
    Sense: Running ✅

  → Step 5: (waiting 5 min, then re-checking)
    check_defender_health("ArcBox-Win2K22")
    healthStatus: Active ✅
    lastSeen: 2025-01-15T14:05:00Z ✅

  → Step 6: create_glpi_ticket(
      title="[Security] Defender agent issue resolved: ArcBox-Win2K22",
      description="<full 6-step diagnostic output>",
      priority="3")
    Created GLPI #161

🔒 **Diagnosis Complete**

Root cause: Sense service crashed at 13:15 UTC (Event ID 7036). No
network or disk issues. MdCoreSvc was still running, indicating a
service-level failure rather than a system-wide problem.

Remediation: Restarted Sense service — now active and reporting.
GLPI #161 created (P3 — auto-remediated, no network/firewall issue).
```

### What's Different from SRE Agent

| Aspect | SRE Agent | Agent Framework |
|--------|-----------|-----------------|
| **Alert trigger** | ✅ Auto-receives Defender alerts | ⚠️ Must build webhook endpoint |
| **Skills** | Upload via UI | `SkillsProvider` (identical behavior) |
| **Diagnostic tools** | Built-in `RunAzCliReadCommands` | 8 custom `FunctionTool` wrappers |
| **Event log interpretation** | LLM + skill context | LLM + skill context (same) |
| **Memory** | ✅ Remembers past Defender issues | ⚠️ Must implement persistence |
| **Setup effort** | ~1 hour | ~2–3 weeks |

---

## Option B: Foundry Agent Service

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Defender for Cloud Alert ──→ Logic App ──→ Foundry Agent    │
└──────────────────────────────────┬───────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────┐
│             Azure AI Foundry Project                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         security-agent-troubleshoot                      │  │
│  │                                                          │  │
│  │  ┌──────────────────┐   ┌────────────────────────────┐  │  │
│  │  │ Instructions      │   │ Function Tools              │  │  │
│  │  │ (SKILL.md content │   │ ┌────────────────────────┐ │  │  │
│  │  │  + system prompt) │   │ │check_defender_health   │ │  │  │
│  │  └──────────────────┘   │ │check_services_via_arc  │ │  │  │
│  │                          │ │test_connectivity       │ │  │  │
│  │  ┌──────────────────┐   │ │check_event_logs        │ │  │  │
│  │  │ Code Interpreter  │   │ │restart_service         │ │  │  │
│  │  │ (log analysis)    │   │ │force_definition_update │ │  │  │
│  │  └──────────────────┘   │ │create_glpi_ticket      │ │  │  │
│  │                          │ └────────────────────────┘ │  │  │
│  │                          └────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Key Code — Agent Setup

```python
"""Security Agent Troubleshooting — Azure AI Foundry implementation."""

from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Load the skill content as agent instructions
skill_path = Path("./sre-skills/security-agent-troubleshooting/SKILL.md")
skill_content = skill_path.read_text(encoding="utf-8")

client = AIProjectClient(
    endpoint=FOUNDRY_ENDPOINT,
    credential=DefaultAzureCredential(),
)

# Define function tools (same operations as Agent Framework — different declaration)
tools = [
    {"type": "function", "function": {
        "name": "check_defender_health",
        "description": "Get Defender agent health status from Azure Resource Graph",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string", "description": "Arc server name"}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "check_services_via_arc",
        "description": "Check MdCoreSvc and Sense service status via Arc Run Command",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "test_connectivity_via_arc",
        "description": "Test network connectivity to Defender cloud endpoints",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "check_event_logs_via_arc",
        "description": "Query Windows Event Log for Defender-related events",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"},
            "hours_back": {"type": "integer", "default": 24}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "restart_service_via_arc",
        "description": "Restart a Windows service on an Arc server",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"},
            "service_name": {"type": "string"}
        }, "required": ["server_name", "service_name"]}
    }},
    {"type": "function", "function": {
        "name": "force_definition_update",
        "description": "Force Defender antimalware definition update",
        "parameters": {"type": "object", "properties": {
            "server_name": {"type": "string"}
        }, "required": ["server_name"]}
    }},
    {"type": "function", "function": {
        "name": "create_glpi_ticket",
        "description": "Create an incident ticket in GLPI with full diagnostic context",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "default": "3"}
        }, "required": ["title", "description"]}
    }},
    {"type": "code_interpreter"},
]

# Create agent with SKILL.md injected as instructions
agent = client.agents.create(
    name="security-agent-troubleshoot",
    instructions=f"""\
You are a security agent troubleshooting specialist for the ArcBox environment.
Follow the investigation procedure below step by step.

Interpret Event IDs: 7036=service state change, 1116=malware detected,
1006=scan error, 2001=definition update failed, 5007=config changed.

Environment: rg-arcbox-itpro, swedencentral
Log Analytics: f98fca75-7479-45e5-bf0c-87b56a9f9e8c

{skill_content}
""",
    tools=tools,
    model="gpt-4o",
)
```

### How the `security-agent-troubleshooting` Skill Is Loaded

The SKILL.md content is read from disk and injected directly into the agent's `instructions`:

```python
skill_content = Path("./sre-skills/security-agent-troubleshooting/SKILL.md").read_text()
agent = client.agents.create(
    instructions=f"You are a security specialist.\n\n{skill_content}",
    ...
)
```

The full skill — triggers, 6 investigation steps, remediation table, and tool references — becomes part of every request's system prompt. Unlike `SkillsProvider`, there is no conditional loading — the skill is always present.

### Example Interaction

```
Security Agent Troubleshoot (Foundry) — type 'quit' to exit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: Defender shows ArcBox-Win2K25 health as inactive. Diagnose and fix.

Agent: Following the security-agent-troubleshooting skill procedure.

  → check_defender_health("ArcBox-Win2K25")
    healthStatus: Inactive, lastSeen: 50 min ago

  → check_services_via_arc("ArcBox-Win2K25")
    MdCoreSvc: Running, Sense: Running
    (Both services running — unexpected for inactive health)

  → test_connectivity_via_arc("ArcBox-Win2K25")
    winatp-gw-eus.microsoft.com:443 → Unreachable ❌
    winatp-gw-neu.microsoft.com:443 → Unreachable ❌
    us-v20.events.data.microsoft.com:443 → Reachable ✅

  → check_event_logs_via_arc("ArcBox-Win2K25", hours_back=6)
    Event ID 2001 at 13:00 UTC: "Failed to connect to Defender cloud"
    Event ID 5007 at 12:55 UTC: "Firewall configuration changed"

  → [Code Interpreter] Analyzing event timeline:
    12:55 — Firewall config changed (Event 5007)
    13:00 — Defender connectivity failed (Event 2001)
    13:10 — Health status changed to Inactive

🔒 **Diagnosis: Network/Firewall Issue**

Root cause: A firewall configuration change at 12:55 UTC blocked
outbound connectivity to Defender gateway endpoints (winatp-gw-*).
Both services are running but cannot reach the cloud.

This is a **network issue** — not safe to auto-remediate (requires
firewall team review).

  → create_glpi_ticket(
      title="[Security] Defender connectivity blocked: ArcBox-Win2K25 (firewall)",
      description="<full diagnostic with event timeline>",
      priority="2")
    Created GLPI #162 (P2 — escalation required)

**Action required:** Firewall team must review the rule change at
12:55 UTC and restore outbound access to *.winatp-gw-*.microsoft.com:443.
```

### What's Different from SRE Agent

| Aspect | SRE Agent | Foundry Agent |
|--------|-----------|---------------|
| **Alert trigger** | ✅ Automatic | ❌ Must build Logic App trigger |
| **Skills** | Upload via UI (auto-route) | Inject as `instructions` (always loaded) |
| **Code Interpreter** | ✅ Built-in | ✅ Built-in (event timeline analysis) |
| **Multi-skill** | ✅ Routes to correct skill | ❌ One skill per agent |
| **Memory** | ✅ Cross-session | ⚠️ Thread-scoped |
| **Setup effort** | ~1 hour | ~1–2 weeks |

---

## Option C: GitHub Copilot CLI

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Engineer's Terminal                                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         GitHub Copilot CLI                               │  │
│  │                                                          │  │
│  │  ┌──────────────────┐   ┌────────────────────────────┐  │  │
│  │  │ .github/skills/   │   │ Terminal Tools (native)     │  │  │
│  │  │ security-agent-   │   │                             │  │  │
│  │  │ troubleshooting/  │   │ • az graph query            │  │  │
│  │  │ SKILL.md          │   │ • az connectedmachine       │  │  │
│  │  │ (auto-loaded)     │   │   run-command                │  │  │
│  │  └──────────────────┘   │ • Get-Service (via Arc)     │  │  │
│  │                          │ • Test-NetConnection        │  │  │
│  │                          │ • Get-WinEvent (via Arc)    │  │  │
│  │                          │ • python glpi_tools.py      │  │  │
│  │                          └────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  az CLI authenticated ──→ Azure Arc, Defender, Log Analytics  │
│                                                               │
│  NOTE: Engineer sees alert in Portal/email, initiates triage  │
│        manually in the terminal.                              │
└──────────────────────────────────────────────────────────────┘
```

### Key Code — Skill Setup

```bash
# Copy skills to project directory (one-time setup)
cp -r sre-skills/* .github/skills/

# Verify
# In Copilot CLI:
/skills list
# → security-agent-troubleshooting  v1.0.0  ✅
```

No agent code to write. Copilot CLI has native access to `az CLI`, PowerShell, and Python in the terminal — the same tools SRE Agent uses, just executed directly.

### How the `security-agent-troubleshooting` Skill Is Loaded

Place the skill in `.github/skills/` or `~/.copilot/skills/`:

```
.github/skills/
└── security-agent-troubleshooting/
    └── SKILL.md    ← auto-discovered and loaded when query matches triggers
```

When you mention "Defender", "agent health", "not reporting", or "MdCoreSvc", Copilot matches against the skill's triggers and loads the full investigation procedure.

### Example Interaction

```
> ArcBox-Win2K22 Defender agent shows "not reporting" for 45 minutes.
  Troubleshoot it using the security-agent-troubleshooting skill.

Copilot: I'll follow the security-agent-troubleshooting skill's 6-step
procedure to diagnose this.

**Step 1 — Defender API health check:**

[Running] az graph query -q "Resources
  | where type == 'microsoft.hybridcompute/machines'
  | where name == 'ArcBox-Win2K22'
  | project name, properties.detectedProperties.mdeDeviceHealthStatus,
    properties.detectedProperties.mdeLastSeen"

→ healthStatus: Inactive, lastSeen: 45 min ago

**Step 2 — Check local services via Arc:**

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
    [PSCustomObject]@{Endpoint=$_; Reachable=
    (Test-NetConnection $_ -Port 443 -InformationLevel Quiet)}} |
    ConvertTo-Json"

→ All endpoints reachable ✅

**Step 4 — Root cause identified:**

Sense service stopped while MdCoreSvc is running and network is fine.
This matches the skill's remediation table: "Sense stopped → Restart
service." Let me check event logs first.

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "CheckEventLogs" \
  --location swedencentral \
  --script "Get-WinEvent -FilterHashtable @{LogName='System';
    Level=1,2,3; StartTime=(Get-Date).AddHours(-6)} -MaxEvents 20 |
    Where {$_.Message -match 'Defender|Sense|MdCoreSvc'} |
    Select TimeCreated, Id, Message | ConvertTo-Json"

→ Event ID 7036 at 13:15 UTC: Sense entered Stopped state.
  No preceding errors — transient crash.

Restarting Sense service:

[Running] az connectedmachine run-command create \
  --resource-group rg-arcbox-itpro \
  --machine-name ArcBox-Win2K22 \
  --name "RestartSense" \
  --location swedencentral \
  --script "Restart-Service Sense -Force; Start-Sleep 5;
    Get-Service Sense | Select Status | ConvertTo-Json"

→ Sense: Running ✅

**Step 5 — Verification:**

I'll wait 5 minutes, then verify.

[Running] az graph query -q "Resources | where name == 'ArcBox-Win2K22'
  | project properties.detectedProperties.mdeDeviceHealthStatus,
    properties.detectedProperties.mdeLastSeen"

→ healthStatus: Active ✅, lastSeen: just now ✅

**Step 6 — Creating GLPI ticket:**

[Running] python sre-tools/python/glpi_tools.py \
  --title "[Security] Defender agent resolved: ArcBox-Win2K22" \
  --description "Sense service crashed at 13:15 (Event 7036).
    Restarted via Arc. Health restored." \
  --priority 3

→ Created GLPI #163 (P3)

**Summary:** Sense service had a transient crash. Restarted via Arc —
Defender now active. GLPI #163 logged for audit.
```

### What's Different from SRE Agent

> **💡 Tip:** Install the [Azure Skills Plugin](https://github.com/microsoft/azure-skills) for additional Azure diagnostics, observability, and compliance capabilities. The plugin provides 20 Azure skills + 200+ MCP tools that complement our custom Wintel ops skills. For security troubleshooting, `azure-diagnostics` can surface AppLens insights and `azure-observability` can query Log Analytics for Defender-related events. However, the core remediation mechanism — Arc Run Commands to restart services on servers — still requires `az connectedmachine` via the terminal.

| Aspect | SRE Agent | Copilot CLI |
|--------|-----------|-------------|
| **Alert trigger** | ✅ Automatic | ❌ Manual (engineer initiates) |
| **Skills** | Upload via UI | Copy to `.github/skills/` (identical content) |
| **Tools** | Built-in `RunAzCliReadCommands` | Direct `az CLI` in terminal (no wrapper code) |
| **Code required** | None | None (just `az CLI` + existing scripts) |
| **Event log interpretation** | LLM + skill | LLM + skill (same reasoning) |
| **Scheduling** | ✅ Built-in | ❌ Interactive only |
| **Memory** | ✅ Cross-session | ⚠️ Session-only |
| **Best for** | 24/7 automated remediation | Ad-hoc investigation by security engineers |
| **Setup effort** | ~1 hour (portal) | ~1 day (copy skills + verify az CLI) |

---

## Root Cause → Remediation Decision Matrix

This matrix applies to **all four options** — the decision logic comes from the SKILL.md and is identical regardless of platform:

| Finding | Automated Remediation | Escalation |
|---|---|---|
| `Sense` stopped, network OK | ✅ Restart service via Arc | P3 ticket (auto-remediated) |
| `MdCoreSvc` stopped | ✅ Restart service via Arc | P3 ticket (auto-remediated) |
| Network unreachable (firewall) | ❌ Cannot auto-fix | **P2 ticket** — escalate to firewall team |
| Agent not onboarded | ❌ Requires onboarding package | **P2 ticket** — escalate to security team |
| Agent version outdated | ⚠️ Trigger Update Manager | P3 ticket |
| Disk space < 1 GB | ⚠️ Clean temp files | P3 ticket (if cleanup insufficient → P2) |
| Definition update failed | ✅ Force `Update-MpSignature` | P3 ticket (if still failing → P2) |

The AI's role (40%) is interpreting **which row applies** by correlating service status, event logs, connectivity results, and disk space into a coherent diagnosis.

---

## Summary Comparison

| Dimension | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|-----------|-----------|-----------------|---------------|-------------|
| **Setup effort** | ~1 hour | ~2–3 weeks | ~1–2 weeks | ~1 day |
| **Alert trigger** | ✅ Automatic | ⚠️ Build webhook | ⚠️ Build Logic App | ❌ Manual |
| **Skill loading** | Upload UI (auto-route) | `SkillsProvider` | Inject instructions | `.github/skills/` |
| **Diagnostic tools** | Built-in `RunAzCli*` | 8 `FunctionTool` wrappers | 8 function definitions | Direct `az CLI` |
| **Event log interpretation** | LLM + skill context | LLM + skill context | LLM + skill + Code Interpreter | LLM + skill context |
| **Safe remediation** | Built-in Arc commands | FunctionTool | Function tool | Terminal command |
| **Escalation ticket** | GLPI Python tool | GLPI FunctionTool | GLPI function tool | Terminal script |
| **Memory** | ✅ Built-in | ⚠️ Custom | ⚠️ Thread-scoped | ❌ Session-only |
| **Scheduling** | ✅ Built-in | ❌ External | ❌ External | ❌ None |
| **Hosting** | Managed SaaS | Self-hosted | Managed Foundry | Local terminal |
| **Best for** | 24/7 auto-remediation | Full customization | Foundry-native teams | Terminal engineers |

## See Also

- [Scenario B — Alert Triage](scenario-b-alert-triage.md) — related alert handling scenario
- [Scenario A — Health Check implementations](scenario-a-health-check/README.md) — same pattern, different scenario
- [AI tier options comparison](../ai-tier-options.md) — cross-scenario platform comparison
- [`sre-skills/security-agent-troubleshooting/SKILL.md`](../../sre-skills/security-agent-troubleshooting/SKILL.md) — the skill definition
- [`sre-tools/python/glpi_tools.py`](../../sre-tools/python/glpi_tools.py) — GLPI tool reference
- [`sre-tools/kusto/query-security-alerts.kql`](../../sre-tools/kusto/query-security-alerts.kql) — KQL query for security alerts
- [Architecture overview](../architecture.md) — system design and data flow
