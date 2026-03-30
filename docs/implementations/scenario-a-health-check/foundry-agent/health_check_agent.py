"""Health Check Agent — Azure AI Foundry Agent Service implementation.

This agent replicates the SRE Agent's health-check investigation skill using
Azure AI Foundry Agent Service.  The SKILL.md content is loaded as agent
instructions, and Azure Arc / Log Analytics / GLPI operations are exposed as
function-calling tools.

Usage:
    python health_check_agent.py                     # interactive mode
    python health_check_agent.py --prompt "..."      # single-shot mode
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Foundry SDK imports
# ---------------------------------------------------------------------------
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    FunctionTool,
    ToolSet,
    CodeInterpreterTool,
)
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4o")

RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "rg-arcbox-itpro")
LOCATION = os.environ.get("AZURE_LOCATION", "swedencentral")
WORKSPACE_ID = os.environ.get(
    "LOG_ANALYTICS_WORKSPACE_ID", "f98fca75-7479-45e5-bf0c-87b56a9f9e8c"
)

GLPI_BASE = os.environ.get(
    "GLPI_BASE_URL",
    "http://glpi-opsauto-demo.swedencentral.azurecontainer.io",
)
GLPI_CLIENT_ID = os.environ.get("GLPI_CLIENT_ID", "YOUR_CLIENT_ID")
GLPI_CLIENT_SECRET = os.environ.get("GLPI_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
GLPI_USERNAME = os.environ.get("GLPI_USERNAME", "glpi")
GLPI_PASSWORD = os.environ.get("GLPI_PASSWORD", "YOUR_ADMIN_PASSWORD")

# Resolve SKILL.md relative to this file
SKILL_PATH = (
    Path(__file__).resolve().parent
    / ".." / ".." / ".." / ".."
    / "sre-skills" / "wintel-health-check-investigation" / "SKILL.md"
)

# ---------------------------------------------------------------------------
# Helper — run az CLI commands
# ---------------------------------------------------------------------------

def _az(args: list[str]) -> dict | list | str:
    """Execute an az CLI command and return parsed output."""
    result = subprocess.run(
        ["az"] + args + ["-o", "json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw_output": result.stdout.strip()}


# ---------------------------------------------------------------------------
# Tool implementations — called when the agent invokes a function tool
# ---------------------------------------------------------------------------

def query_arc_servers(resource_group: str = RESOURCE_GROUP) -> str:
    """List all Arc-enrolled servers and their connection status."""
    query = (
        "Resources "
        "| where type == 'microsoft.hybridcompute/machines' "
        f"  and resourceGroup == '{resource_group}' "
        "| project name, "
        "  status = tostring(properties.status), "
        "  osName = tostring(properties.osName), "
        "  osVersion = tostring(properties.osVersion)"
    )
    return json.dumps(_az(["graph", "query", "-q", query]))


def run_health_check(server_name: str) -> str:
    """Run health checks on an Arc server via Log Analytics (last 1 hour)."""
    kql = (
        "Perf "
        f"| where Computer == '{server_name}' "
        "| where TimeGenerated > ago(1h) "
        "| where ObjectName in ('Processor', 'Memory', 'LogicalDisk') "
        "| where CounterName in ("
        "    '% Processor Time', "
        "    '% Committed Bytes In Use', "
        "    '% Free Space'"
        "  ) "
        "| summarize AvgValue=round(avg(CounterValue),1), "
        "            MaxValue=round(max(CounterValue),1) "
        "    by CounterName, InstanceName"
    )
    return json.dumps(_az([
        "monitor", "log-analytics", "query",
        "--workspace", WORKSPACE_ID,
        "--analytics-query", kql,
    ]))


def query_perf_trends(
    server_name: str,
    metric: str = "cpu",
    hours_back: int = 168,
) -> str:
    """Query performance trends for a server over the specified time window."""
    metric_filter = {
        "cpu": "ObjectName == 'Processor' and CounterName == '% Processor Time' and InstanceName == '_Total'",
        "memory": "ObjectName == 'Memory' and CounterName == '% Committed Bytes In Use'",
        "disk": "ObjectName == 'LogicalDisk' and CounterName == '% Free Space' and InstanceName == 'C:'",
    }
    where_clause = metric_filter.get(metric, metric_filter["cpu"])

    kql = (
        "Perf "
        f"| where TimeGenerated >= ago({hours_back}h) "
        f"| where Computer == '{server_name}' "
        f"| where {where_clause} "
        "| summarize "
        "    AvgValue = round(avg(CounterValue), 1), "
        "    MaxValue = round(max(CounterValue), 1), "
        "    P95Value = round(percentile(CounterValue, 95), 1) "
        "  by bin(TimeGenerated, 1h), Computer, CounterName "
        "| order by TimeGenerated asc"
    )
    return json.dumps(_az([
        "monitor", "log-analytics", "query",
        "--workspace", WORKSPACE_ID,
        "--analytics-query", kql,
    ]))


def run_arc_command(server_name: str, script: str) -> str:
    """Execute a PowerShell script on an Arc-enrolled Windows server."""
    return json.dumps(_az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"FoundryAgent-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ]))


def create_glpi_ticket(
    title: str,
    description: str,
    priority: str = "3",
) -> str:
    """Create an incident ticket in GLPI via OAuth2 API."""
    import requests

    token_resp = requests.post(
        f"{GLPI_BASE}/api.php/token",
        data={
            "grant_type": "password",
            "client_id": GLPI_CLIENT_ID,
            "client_secret": GLPI_CLIENT_SECRET,
            "username": GLPI_USERNAME,
            "password": GLPI_PASSWORD,
            "scope": "api",
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["access_token"]

    ticket_resp = requests.post(
        f"{GLPI_BASE}/api.php/v2.2/Assistance/Ticket",
        json={
            "name": title,
            "content": description,
            "type": 1,
            "urgency": int(priority),
            "impact": int(priority),
            "priority": int(priority),
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    ticket_resp.raise_for_status()
    ticket_id = ticket_resp.json()["id"]

    return json.dumps({
        "ticket_id": ticket_id,
        "title": title,
        "priority": priority,
        "url": f"{GLPI_BASE}/front/ticket.form.php?id={ticket_id}",
        "status": "created",
    })


# ---------------------------------------------------------------------------
# Function-tool dispatch map
# ---------------------------------------------------------------------------
TOOL_FUNCTIONS = {
    "query_arc_servers": query_arc_servers,
    "run_health_check": run_health_check,
    "query_perf_trends": query_perf_trends,
    "run_arc_command": run_arc_command,
    "create_glpi_ticket": create_glpi_ticket,
}

# ---------------------------------------------------------------------------
# Foundry tool definitions (JSON Schema for function calling)
# ---------------------------------------------------------------------------
FUNCTION_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_arc_servers",
            "description": "List all Arc-enrolled servers and their connection status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_group": {
                        "type": "string",
                        "description": "Azure resource group containing Arc servers.",
                        "default": "rg-arcbox-itpro",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_health_check",
            "description": "Run health checks on an Arc server via Log Analytics (last 1 hour). Returns CPU, memory, and disk metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "Name of the Arc-enrolled server (e.g. ArcBox-SQL).",
                    }
                },
                "required": ["server_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_perf_trends",
            "description": "Query 7-day performance trends for a server. Returns hourly aggregates of CPU, memory, or disk metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "Arc server name (e.g. ArcBox-SQL).",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["cpu", "memory", "disk"],
                        "description": "Metric type.",
                    },
                    "hours_back": {
                        "type": "integer",
                        "description": "Hours of history (default 168 = 7 days).",
                        "default": 168,
                    },
                },
                "required": ["server_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_arc_command",
            "description": "Execute a PowerShell script on an Arc-enrolled Windows server via Arc Run Command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {
                        "type": "string",
                        "description": "Name of the Arc server.",
                    },
                    "script": {
                        "type": "string",
                        "description": "Inline PowerShell script to execute.",
                    },
                },
                "required": ["server_name", "script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_glpi_ticket",
            "description": "Create an incident ticket in GLPI ITSM. Use for CRITICAL or WARNING health check findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Ticket title (e.g. '[Health Check] ArcBox-SQL: Disk E: 91% CRITICAL').",
                    },
                    "description": {
                        "type": "string",
                        "description": "Full description with diagnostics and remediation steps.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["1", "2", "3", "4", "5"],
                        "description": "Priority 1-5 (1=very high). Default '3'.",
                        "default": "3",
                    },
                },
                "required": ["title", "description"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Agent creation
# ---------------------------------------------------------------------------

def build_agent(client: AIProjectClient):
    """Create the Foundry agent with SKILL.md as instructions."""
    # Load skill content
    skill_content = SKILL_PATH.read_text(encoding="utf-8")

    instructions = (
        "You are a Windows server health check specialist operating in the "
        "ArcBox for IT Pros demo environment.\n\n"
        "Use severity indicators: 🔴 CRITICAL  🟡 WARNING  🟢 OK\n\n"
        "Environment:\n"
        "  Resource group: rg-arcbox-itpro\n"
        "  Region: swedencentral\n"
        "  Windows VMs: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL\n"
        "  Linux VMs: ArcBox-Ubuntu-01, ArcBox-Ubuntu-02\n"
        "  Log Analytics workspace: f98fca75-7479-45e5-bf0c-87b56a9f9e8c\n"
        "  GLPI: http://glpi-opsauto-demo.swedencentral.azurecontainer.io\n\n"
        "--- Investigation Skill ---\n\n"
        f"{skill_content}"
    )

    # Build tool set
    toolset = ToolSet()
    toolset.add(FunctionTool(FUNCTION_TOOL_DEFINITIONS))
    toolset.add(CodeInterpreterTool())

    agent = client.agents.create_agent(
        model=MODEL,
        name="health-check-agent",
        instructions=instructions,
        toolset=toolset,
    )
    print(f"Created agent: {agent.id}")
    return agent


# ---------------------------------------------------------------------------
# Conversation loop with tool dispatch
# ---------------------------------------------------------------------------

def process_tool_calls(client, thread_id, run):
    """Handle function-calling tool calls from the agent."""
    while run.status == "requires_action":
        tool_outputs = []
        for call in run.required_action.submit_tool_outputs.tool_calls:
            fn_name = call.function.name
            fn_args = json.loads(call.function.arguments) if call.function.arguments else {}

            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn:
                try:
                    output = fn(**fn_args)
                except Exception as exc:
                    output = json.dumps({"error": str(exc)})
            else:
                output = json.dumps({"error": f"Unknown function: {fn_name}"})

            tool_outputs.append({"tool_call_id": call.id, "output": output})

        run = client.agents.submit_tool_outputs_to_run(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )
    return run


def run_single_prompt(prompt: str) -> str:
    """Run a single prompt through the agent (for scheduled execution)."""
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    agent = build_agent(client)
    thread = client.agents.create_thread()

    client.agents.create_message(
        thread_id=thread.id, role="user", content=prompt
    )
    run = client.agents.create_run(thread_id=thread.id, agent_id=agent.id)
    run = process_tool_calls(client, thread.id, run)

    messages = client.agents.list_messages(thread_id=thread.id)
    assistant_msg = next(
        (m for m in messages.data if m.role == "assistant"), None
    )
    result = assistant_msg.content[0].text.value if assistant_msg else "(no response)"

    # Cleanup
    client.agents.delete_agent(agent.id)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Health Check Agent (Foundry Agent Service)"
    )
    parser.add_argument(
        "--prompt", type=str, default=None,
        help="Single-shot prompt (skip interactive mode).",
    )
    args = parser.parse_args()

    if args.prompt:
        print(run_single_prompt(args.prompt))
        return

    # Interactive mode
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    agent = build_agent(client)
    thread = client.agents.create_thread()

    print("Health Check Agent (Foundry Agent Service) — type 'quit' to exit")
    print("━" * 63)
    print()

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            client.agents.create_message(
                thread_id=thread.id, role="user", content=user_input
            )
            run = client.agents.create_run(
                thread_id=thread.id, agent_id=agent.id
            )
            run = process_tool_calls(client, thread.id, run)

            messages = client.agents.list_messages(thread_id=thread.id)
            assistant_msg = next(
                (m for m in messages.data if m.role == "assistant"), None
            )
            if assistant_msg:
                print(f"\nAgent: {assistant_msg.content[0].text.value}\n")
            else:
                print("\nAgent: (no response)\n")
    finally:
        client.agents.delete_agent(agent.id)
        print("Agent cleaned up.")


if __name__ == "__main__":
    main()
