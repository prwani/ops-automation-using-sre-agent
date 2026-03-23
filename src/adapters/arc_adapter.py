"""Azure Arc adapter — implements ArcAdapterBase using the Azure SDK."""

import asyncio
from datetime import datetime, timezone

import structlog
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import ArcAdapterBase, RunCommandResult, ServerInfo

log = structlog.get_logger(__name__)

_ARC_QUERY = """
Resources
| where type == "microsoft.hybridcompute/machines"
| project
    id,
    name,
    resourceGroup,
    subscriptionId,
    properties.osType,
    properties.status,
    properties.lastStatusChange,
    tags
"""

_ARC_SINGLE_QUERY = """
Resources
| where type == "microsoft.hybridcompute/machines"
| where id == "{resource_id}"
| project
    id,
    name,
    resourceGroup,
    subscriptionId,
    properties.osType,
    properties.status,
    properties.lastStatusChange,
    tags
"""


def _parse_server(row: dict) -> ServerInfo:
    last_seen_raw = row.get("properties_lastStatusChange")
    last_seen: datetime | None = None
    if last_seen_raw:
        try:
            last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    return ServerInfo(
        server_id=row["id"],
        name=row["name"],
        resource_group=row["resourceGroup"],
        subscription_id=row["subscriptionId"],
        os_type=str(row.get("properties_osType", "Windows")),
        arc_connected=str(row.get("properties_status", "")).lower() == "connected",
        last_seen=last_seen,
        tags=row.get("tags") or {},
    )


class ArcAdapter(ArcAdapterBase):
    """Azure Arc adapter backed by Resource Graph and Compute Management Client."""

    def __init__(self, credential, subscription_id: str) -> None:
        self._credential = credential
        self._subscription_id = subscription_id
        self._graph_client = ResourceGraphClient(credential)
        self._compute_client = ComputeManagementClient(credential, subscription_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_servers(self) -> list[ServerInfo]:
        """List all Arc-enrolled servers via Resource Graph."""
        log.info("arc.list_servers", subscription_id=self._subscription_id)
        loop = asyncio.get_event_loop()
        request = QueryRequest(
            subscriptions=[self._subscription_id],
            query=_ARC_QUERY,
        )
        response = await loop.run_in_executor(
            None, lambda: self._graph_client.resources(request)
        )
        servers = [_parse_server(row) for row in response.data]
        log.info("arc.list_servers.done", count=len(servers))
        return servers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_server(self, server_id: str) -> ServerInfo | None:
        """Get details for a specific Arc server."""
        log.info("arc.get_server", server_id=server_id)
        loop = asyncio.get_event_loop()
        request = QueryRequest(
            subscriptions=[self._subscription_id],
            query=_ARC_SINGLE_QUERY.format(resource_id=server_id),
        )
        response = await loop.run_in_executor(
            None, lambda: self._graph_client.resources(request)
        )
        rows = response.data
        if not rows:
            log.warning("arc.get_server.not_found", server_id=server_id)
            return None
        return _parse_server(rows[0])

    async def run_command(
        self, server_id: str, script: str, timeout_seconds: int = 300
    ) -> RunCommandResult:
        """Execute a PowerShell script on a server via Arc Run Command."""
        log.info("arc.run_command", server_id=server_id, timeout=timeout_seconds)

        # Parse resource group and machine name from the Arc resource ID
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.HybridCompute/machines/{name}
        parts = server_id.split("/")
        try:
            rg_index = next(i for i, p in enumerate(parts) if p.lower() == "resourcegroups")
            resource_group = parts[rg_index + 1]
            machine_name = parts[-1]
        except (StopIteration, IndexError) as exc:
            return RunCommandResult(
                success=False,
                output="",
                error=f"Invalid server_id format: {server_id}",
                exit_code=-1,
            )

        loop = asyncio.get_event_loop()
        try:
            poller = await loop.run_in_executor(
                None,
                lambda: self._compute_client.machine_run_commands.begin_create_or_update(
                    resource_group_name=resource_group,
                    machine_name=machine_name,
                    run_command_name="ops-automation-run",
                    run_command_properties={
                        "source": {"script": script},
                        "timeoutInSeconds": timeout_seconds,
                        "asyncExecution": False,
                    },
                ),
            )
            result = await loop.run_in_executor(None, poller.result)
            instance_view = result.instance_view
            output = ""
            error = None
            exit_code = 0
            if instance_view and instance_view.execution_state:
                output = instance_view.output or ""
                error = instance_view.error or None
                exit_code = instance_view.exit_code or 0
            success = exit_code == 0
            log.info("arc.run_command.done", server_id=server_id, exit_code=exit_code)
            return RunCommandResult(success=success, output=output, error=error, exit_code=exit_code)
        except Exception as exc:
            log.error("arc.run_command.failed", server_id=server_id, error=str(exc))
            return RunCommandResult(success=False, output="", error=str(exc), exit_code=-1)
