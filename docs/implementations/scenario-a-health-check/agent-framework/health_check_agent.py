"""Health Check Agent — Microsoft Agent Framework implementation.

This agent replicates the SRE Agent's health-check investigation skill using the
Microsoft Agent Framework with Azure OpenAI.  It auto-loads skills from
sre-skills/ via SkillsProvider and exposes Azure Arc / Log Analytics / GLPI
operations as FunctionTools.

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
# Agent Framework imports
# ---------------------------------------------------------------------------
from agent_framework import FunctionTool, SkillsProvider
from azure.ai.openai import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.environ.get(
    "AZURE_OPENAI_API_VERSION", "2025-03-01-preview"
)

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

# Resolve the sre-skills directory relative to this file.
# From agent-framework/ → ../../../../sre-skills
SKILLS_DIR = str(
    (Path(__file__).resolve().parent / ".." / ".." / ".." / ".." / "sre-skills")
)

# ---------------------------------------------------------------------------
# Helper — run az CLI commands and return parsed JSON
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
# Tools — each wraps an Azure / GLPI operation
# ---------------------------------------------------------------------------

@FunctionTool
def query_arc_servers(resource_group: str = RESOURCE_GROUP) -> dict:
    """List all Arc-enrolled servers and their connection status.

    Args:
        resource_group: Azure resource group containing Arc servers.
    """
    query = (
        "Resources "
        "| where type == 'microsoft.hybridcompute/machines' "
        f"  and resourceGroup == '{resource_group}' "
        "| project name, "
        "  status = tostring(properties.status), "
        "  osName = tostring(properties.osName), "
        "  osVersion = tostring(properties.osVersion), "
        "  lastStatusChange = tostring(properties.lastStatusChange)"
    )
    return _az(["graph", "query", "-q", query])


@FunctionTool
def run_health_check_on_server(server_name: str) -> dict:
    """Run health checks on an Arc server via Log Analytics (last 1 hour).

    Returns average values for CPU, memory, and disk metrics.

    Args:
        server_name: Name of the Arc-enrolled server (e.g. ArcBox-SQL).
    """
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
    return _az([
        "monitor", "log-analytics", "query",
        "--workspace", WORKSPACE_ID,
        "--analytics-query", kql,
    ])


@FunctionTool
def query_perf_trends(
    server_name: str,
    metric: str = "cpu",
    hours_back: int = 168,
) -> dict:
    """Query performance trends for a server over the specified time window.

    Args:
        server_name: Arc server name (e.g. ArcBox-SQL).
        metric: One of 'cpu', 'memory', or 'disk'.
        hours_back: How many hours of history to pull (default 168 = 7 days).
    """
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
    return _az([
        "monitor", "log-analytics", "query",
        "--workspace", WORKSPACE_ID,
        "--analytics-query", kql,
    ])


@FunctionTool
def run_arc_command(server_name: str, script: str) -> dict:
    """Execute a PowerShell script on an Arc-enrolled Windows server.

    Args:
        server_name: Name of the Arc server.
        script: Inline PowerShell script to execute.
    """
    return _az([
        "connectedmachine", "run-command", "create",
        "--resource-group", RESOURCE_GROUP,
        "--machine-name", server_name,
        "--name", f"AgentFramework-{server_name}",
        "--location", LOCATION,
        "--script", script,
        "--async-execution", "false",
    ])


@FunctionTool
def create_glpi_ticket(
    title: str,
    description: str,
    priority: str = "3",
) -> dict:
    """Create an incident ticket in GLPI via OAuth2 API.

    Args:
        title: Ticket title (e.g. '[Health Check] ArcBox-SQL: Disk E: 91% CRITICAL').
        description: Full description with diagnostics and remediation steps.
        priority: Priority 1-5 (1=very high, 5=very low). Default '3' (medium).
    """
    import requests

    # Obtain OAuth2 token
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

    # Create ticket
    ticket_resp = requests.post(
        f"{GLPI_BASE}/api.php/v2.2/Assistance/Ticket",
        json={
            "name": title,
            "content": description,
            "type": 1,  # Incident
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

    return {
        "ticket_id": ticket_id,
        "title": title,
        "priority": priority,
        "url": f"{GLPI_BASE}/front/ticket.form.php?id={ticket_id}",
        "status": "created",
    }


# ---------------------------------------------------------------------------
# Skills — auto-load from sre-skills/
# ---------------------------------------------------------------------------

skills = SkillsProvider(skill_paths=[SKILLS_DIR])

# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTIONS = """\
You are a Windows server health check specialist operating in the ArcBox for \
IT Pros demo environment.  Your job is to:

1. Run health checks on Arc-enrolled servers (CPU, memory, disk, services).
2. Query Log Analytics for performance trends (7-day history).
3. Identify anomalies — both threshold breaches AND slow-building trends.
4. Correlate issues across servers (e.g. simultaneous memory growth).
5. Project future state (e.g. 'disk will hit 95% in 5 days at current rate').
6. Create GLPI tickets for CRITICAL or WARNING findings.
7. Produce a concise natural-language summary (morning brief format).

Use severity indicators: 🔴 CRITICAL  🟡 WARNING  🟢 OK

Follow the investigation procedure in the loaded skill when available.

Environment:
  Resource group: rg-arcbox-itpro
  Region: swedencentral
  Windows VMs: ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL
  Linux VMs: ArcBox-Ubuntu-01, ArcBox-Ubuntu-02
  Log Analytics workspace: f98fca75-7479-45e5-bf0c-87b56a9f9e8c
  GLPI: http://glpi-opsauto-demo.swedencentral.azurecontainer.io
"""

client = AzureOpenAIResponsesClient(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    credential=DefaultAzureCredential(),
    api_version=AZURE_OPENAI_API_VERSION,
)

agent = client.as_agent(
    model=AZURE_OPENAI_DEPLOYMENT,
    name="HealthCheckAgent",
    instructions=SYSTEM_INSTRUCTIONS,
    tools=[
        query_arc_servers,
        run_health_check_on_server,
        query_perf_trends,
        run_arc_command,
        create_glpi_ticket,
    ],
    context_providers=[skills],
)

# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Health Check Agent (Agent Framework)")
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Single-shot prompt (skip interactive mode).",
    )
    args = parser.parse_args()

    if args.prompt:
        # Single-shot: run one prompt and exit (useful for scheduled execution).
        response = agent.run(args.prompt)
        print(response.content)
        return

    # Interactive conversation loop
    print("Health Check Agent (Agent Framework) — type 'quit' to exit")
    print("━" * 55)
    print()

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

        print()
        response = agent.run(user_input)
        print(f"Agent: {response.content}")
        print()


if __name__ == "__main__":
    main()
