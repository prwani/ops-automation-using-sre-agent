"""Unit tests for the health check engine."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.base import RunCommandResult, ServerInfo
from src.health_checks.engine import (
    HealthCheckEngine,
    HealthCheckThresholds,
    HealthStatus,
    ServerHealthResult,
)


def _make_server(name: str = "srv-001", connected: bool = True) -> ServerInfo:
    return ServerInfo(
        server_id=f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.HybridCompute/machines/{name}",
        name=name,
        resource_group="rg",
        subscription_id="sub",
        os_type="Windows",
        arc_connected=connected,
        last_seen=datetime.now(timezone.utc),
    )


def _disk_output(pct: int) -> str:
    return json.dumps([{"Drive": "C:", "UsedPercent": pct, "FreeGB": 50.0, "TotalGB": 100.0}])


def _services_output(statuses: dict[str, str]) -> str:
    return json.dumps(
        [{"Name": k, "DisplayName": k, "Status": v, "StartType": "Automatic"} for k, v in statuses.items()]
    )


def _eventlog_output(errors: int) -> str:
    return json.dumps([{"Log": "System", "ErrorCount": errors, "Since": "2024-01-01T00:00:00Z"}])


def _perf_rows(cpu: float, mem: float) -> list:
    return [
        ["Processor", "% Processor Time", cpu],
        ["Memory", "% Committed Bytes In Use", mem],
    ]


def _make_engine(
    servers: list[ServerInfo],
    disk_pct: int = 50,
    service_statuses: dict[str, str] | None = None,
    event_errors: int = 0,
    cpu: float = 30.0,
    mem: float = 40.0,
    suppressions: dict | None = None,
) -> HealthCheckEngine:
    if service_statuses is None:
        service_statuses = {
            "wuauserv": "Running",
            "WinRM": "Running",
            "EventLog": "Running",
            "MpsSvc": "Running",
            "MdCoreSvc": "Running",
        }

    arc = AsyncMock()
    arc.list_servers.return_value = servers
    arc.get_server.return_value = servers[0] if servers else None
    arc.run_command.side_effect = [
        RunCommandResult(success=True, output=_disk_output(disk_pct)),
        RunCommandResult(success=True, output=_services_output(service_statuses)),
        RunCommandResult(success=True, output=_eventlog_output(event_errors)),
    ]

    la_table = MagicMock()
    la_table.rows = _perf_rows(cpu, mem)
    la_response = MagicMock()
    la_response.tables = [la_table]
    la_client = MagicMock()
    la_client.query_workspace.return_value = la_response

    return HealthCheckEngine(
        arc_adapter=arc,
        log_analytics_client=la_client,
        workspace_id="test-workspace-id",
        suppressions=suppressions or {},
    )


@pytest.mark.asyncio
async def test_all_healthy():
    server = _make_server()
    engine = _make_engine([server], disk_pct=50, event_errors=0, cpu=30.0, mem=40.0)
    result = await engine.run_server(server.server_id)
    assert result.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_disk_critical():
    server = _make_server()
    engine = _make_engine([server], disk_pct=95)
    result = await engine.run_server(server.server_id)
    assert result.status == HealthStatus.CRITICAL
    assert result.checks["disk"]["status"] == HealthStatus.CRITICAL


@pytest.mark.asyncio
async def test_disk_warning():
    server = _make_server()
    engine = _make_engine([server], disk_pct=85)
    result = await engine.run_server(server.server_id)
    assert result.checks["disk"]["status"] == HealthStatus.WARNING


@pytest.mark.asyncio
async def test_service_stopped_warning():
    server = _make_server()
    statuses = {
        "wuauserv": "Stopped",
        "WinRM": "Running",
        "EventLog": "Running",
        "MpsSvc": "Running",
        "MdCoreSvc": "Running",
    }
    engine = _make_engine([server], service_statuses=statuses)
    result = await engine.run_server(server.server_id)
    assert result.checks["services"]["status"] == HealthStatus.WARNING


@pytest.mark.asyncio
async def test_critical_service_stopped_raises_critical():
    server = _make_server()
    statuses = {
        "wuauserv": "Running",
        "WinRM": "Stopped",  # critical service
        "EventLog": "Running",
        "MpsSvc": "Running",
        "MdCoreSvc": "Running",
    }
    engine = _make_engine([server], service_statuses=statuses)
    result = await engine.run_server(server.server_id)
    assert result.checks["services"]["status"] == HealthStatus.CRITICAL


@pytest.mark.asyncio
async def test_server_unreachable_returns_unknown():
    server = _make_server(connected=False)
    arc = AsyncMock()
    arc.get_server.return_value = server
    engine = HealthCheckEngine(
        arc_adapter=arc,
        log_analytics_client=MagicMock(),
        workspace_id="test-workspace-id",
    )
    result = await engine.run_server(server.server_id)
    assert result.status == HealthStatus.UNKNOWN


@pytest.mark.asyncio
async def test_service_notfound_is_warning():
    """A service returning NotFound should be treated as stopped (WARNING)."""
    server = _make_server()
    statuses = {
        "wuauserv": "NotFound",  # service missing → should be treated as stopped
        "WinRM": "Running",
        "EventLog": "Running",
        "MpsSvc": "Running",
        "MdCoreSvc": "Running",
    }
    engine = _make_engine([server], service_statuses=statuses)
    result = await engine.run_server(server.server_id)
    assert result.checks["services"]["status"] == HealthStatus.WARNING


@pytest.mark.asyncio
async def test_critical_service_notfound_is_critical():
    """A critical service returning NotFound should trigger CRITICAL."""
    server = _make_server()
    statuses = {
        "wuauserv": "Running",
        "WinRM": "NotFound",  # critical service missing
        "EventLog": "Running",
        "MpsSvc": "Running",
        "MdCoreSvc": "Running",
    }
    engine = _make_engine([server], service_statuses=statuses)
    result = await engine.run_server(server.server_id)
    assert result.checks["services"]["status"] == HealthStatus.CRITICAL


@pytest.mark.asyncio
async def test_memory_suppression_rule_applied():
    """A disk suppression capping max_severity at WARNING should downgrade CRITICAL disk → WARNING."""
    server = _make_server()
    suppressions = {
        server.server_id: {
            "overrides": {
                "disk": {"max_severity": "warning"}
            }
        }
    }
    engine = _make_engine([server], disk_pct=95, suppressions=suppressions)
    result = await engine.run_server(server.server_id)
    assert result.checks["disk"]["status"] == HealthStatus.WARNING
    assert result.checks["disk"].get("suppressed") is True


@pytest.mark.asyncio
async def test_suppress_all():
    server = _make_server()
    suppressions = {server.server_id: {"suppress_all": True}}
    engine = _make_engine([server], disk_pct=95, event_errors=20, suppressions=suppressions)
    result = await engine.run_server(server.server_id)
    for check in result.checks.values():
        assert check["status"] == HealthStatus.HEALTHY
        assert check.get("suppressed") is True
