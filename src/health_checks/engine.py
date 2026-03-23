"""Health check engine — runs all checks on all Arc-enrolled servers."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from src.adapters.base import ArcAdapterBase, RunCommandResult

log = structlog.get_logger(__name__)

_SCRIPTS_DIR = Path(__file__).parent / "scripts"

CRITICAL_SERVICES = ["wuauserv", "WinRM", "EventLog", "MpsSvc", "MdCoreSvc"]


@dataclass
class HealthCheckThresholds:
    disk_warn: int = 80
    disk_critical: int = 90
    cpu_warn: int = 80
    cpu_critical: int = 95
    mem_warn: int = 85
    mem_critical: int = 95
    event_log_warn: int = 1
    event_log_critical: int = 10


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ServerHealthResult:
    server_id: str
    server_name: str
    status: HealthStatus
    checks: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _worst_status(*statuses: HealthStatus) -> HealthStatus:
    order = [HealthStatus.CRITICAL, HealthStatus.WARNING, HealthStatus.UNKNOWN, HealthStatus.HEALTHY]
    for s in order:
        if s in statuses:
            return s
    return HealthStatus.HEALTHY


class HealthCheckEngine:
    """Runs health checks on Arc-enrolled Windows servers."""

    def __init__(
        self,
        arc_adapter: ArcAdapterBase,
        log_analytics_client: Any,
        cosmos_client: Any,
        workspace_id: str = "",
        thresholds: HealthCheckThresholds | None = None,
        suppressions: dict[str, Any] | None = None,
    ) -> None:
        self._arc = arc_adapter
        self._la_client = log_analytics_client
        self._cosmos = cosmos_client
        self._workspace_id = workspace_id
        self._thresholds = thresholds or HealthCheckThresholds()
        self._suppressions = suppressions or {}

    async def run_all_servers(self) -> list[ServerHealthResult]:
        """Run health checks on all Arc-enrolled servers concurrently."""
        servers = await self._arc.list_servers()
        log.info("health.run_all_servers", count=len(servers))
        results = await asyncio.gather(
            *[self.run_server(s.server_id) for s in servers],
            return_exceptions=True,
        )
        out: list[ServerHealthResult] = []
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                log.error("health.run_server.exception", server=server.name, error=str(result))
                out.append(
                    ServerHealthResult(
                        server_id=server.server_id,
                        server_name=server.name,
                        status=HealthStatus.UNKNOWN,
                        checks={"error": str(result)},
                    )
                )
            else:
                out.append(result)  # type: ignore[arg-type]
        return out

    async def run_server(self, server_id: str) -> ServerHealthResult:
        """Run all health checks on a single server."""
        server = await self._arc.get_server(server_id)
        server_name = server.name if server else server_id

        if not server or not server.arc_connected:
            return ServerHealthResult(
                server_id=server_id,
                server_name=server_name,
                status=HealthStatus.UNKNOWN,
                checks={"heartbeat": {"status": HealthStatus.UNKNOWN, "reason": "Not connected"}},
            )

        # Run all checks concurrently
        disk_result, svc_result, event_result, perf_result = await asyncio.gather(
            self._check_disk(server_id),
            self._check_services(server_id),
            self._check_event_log(server_id),
            self._check_cpu_memory(server_id),
            return_exceptions=True,
        )

        checks: dict[str, Any] = {}

        def _safe(name: str, result: Any) -> None:
            if isinstance(result, Exception):
                checks[name] = {"status": HealthStatus.UNKNOWN, "error": str(result)}
            else:
                checks[name] = result

        _safe("disk", disk_result)
        _safe("services", svc_result)
        _safe("event_log", event_result)
        _safe("cpu_memory", perf_result)

        # Apply suppressions / threshold overrides
        checks = self._apply_suppressions(server_id, checks)

        overall = _worst_status(*[c.get("status", HealthStatus.UNKNOWN) for c in checks.values()])

        return ServerHealthResult(
            server_id=server_id,
            server_name=server_name,
            status=overall,
            checks=checks,
        )

    async def _check_disk(self, server_id: str) -> dict[str, Any]:
        script = (_SCRIPTS_DIR / "check_disk.ps1").read_text()
        result = await self._arc.run_command(server_id, script)
        if not result.success:
            return {"status": HealthStatus.UNKNOWN, "error": result.error}

        try:
            drives = json.loads(result.output)
        except (json.JSONDecodeError, ValueError):
            return {"status": HealthStatus.UNKNOWN, "raw": result.output}

        if isinstance(drives, dict):
            drives = [drives]

        t = self._thresholds
        worst = HealthStatus.HEALTHY
        for drive in drives:
            pct = drive.get("UsedPercent", 0)
            if pct >= t.disk_critical:
                worst = _worst_status(worst, HealthStatus.CRITICAL)
            elif pct >= t.disk_warn:
                worst = _worst_status(worst, HealthStatus.WARNING)

        return {"status": worst, "drives": drives}

    async def _check_services(self, server_id: str) -> dict[str, Any]:
        script = (_SCRIPTS_DIR / "check_services.ps1").read_text()
        result = await self._arc.run_command(server_id, script)
        if not result.success:
            return {"status": HealthStatus.UNKNOWN, "error": result.error}

        try:
            services = json.loads(result.output)
        except (json.JSONDecodeError, ValueError):
            return {"status": HealthStatus.UNKNOWN, "raw": result.output}

        if isinstance(services, dict):
            services = [services]

        stopped = [s for s in services if s.get("Status") not in ("Running",)]
        critical_stopped = [
            s for s in stopped if s.get("Name") in ("MdCoreSvc", "WinRM")
        ]

        if critical_stopped:
            status = HealthStatus.CRITICAL
        elif stopped:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY

        return {"status": status, "services": services, "stopped": stopped}

    async def _check_event_log(self, server_id: str) -> dict[str, Any]:
        script = (_SCRIPTS_DIR / "check_eventlog.ps1").read_text()
        result = await self._arc.run_command(server_id, script)
        if not result.success:
            return {"status": HealthStatus.UNKNOWN, "error": result.error}

        try:
            logs = json.loads(result.output)
        except (json.JSONDecodeError, ValueError):
            return {"status": HealthStatus.UNKNOWN, "raw": result.output}

        if isinstance(logs, dict):
            logs = [logs]

        total_errors = sum(entry.get("ErrorCount", 0) for entry in logs)
        t = self._thresholds
        if total_errors >= t.event_log_critical:
            status = HealthStatus.CRITICAL
        elif total_errors >= t.event_log_warn:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY

        return {"status": status, "logs": logs, "total_errors": total_errors}

    async def _check_cpu_memory(self, server_id: str) -> dict[str, Any]:
        """Query Log Analytics for 5-minute average CPU and memory."""
        server = await self._arc.get_server(server_id)
        if not server:
            return {"status": HealthStatus.UNKNOWN}

        kql = f"""
Perf
| where Computer == "{server.name}"
| where TimeGenerated > ago(10m)
| where (ObjectName == "Processor" and CounterName == "% Processor Time")
    or (ObjectName == "Memory" and CounterName == "% Committed Bytes In Use")
| summarize avg(CounterValue) by ObjectName, CounterName
"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._la_client.query_workspace(
                    workspace_id=self._workspace_id,
                    query=kql,
                ),
            )
            rows = list(response.tables[0].rows) if response.tables else []
        except Exception as exc:
            return {"status": HealthStatus.UNKNOWN, "error": str(exc)}

        cpu_avg: float | None = None
        mem_avg: float | None = None
        for row in rows:
            obj, counter, avg_val = row[0], row[1], row[2]
            if "Processor" in obj:
                cpu_avg = float(avg_val)
            elif "Memory" in obj:
                mem_avg = float(avg_val)

        t = self._thresholds
        status = HealthStatus.HEALTHY
        if cpu_avg is not None:
            if cpu_avg >= t.cpu_critical:
                status = _worst_status(status, HealthStatus.CRITICAL)
            elif cpu_avg >= t.cpu_warn:
                status = _worst_status(status, HealthStatus.WARNING)
        if mem_avg is not None:
            if mem_avg >= t.mem_critical:
                status = _worst_status(status, HealthStatus.CRITICAL)
            elif mem_avg >= t.mem_warn:
                status = _worst_status(status, HealthStatus.WARNING)

        return {"status": status, "cpu_avg": cpu_avg, "mem_avg": mem_avg}

    def _apply_suppressions(self, server_id: str, checks: dict[str, Any]) -> dict[str, Any]:
        """Downgrade warnings if an active suppression or override exists."""
        suppression = self._suppressions.get(server_id, {})
        if suppression.get("suppress_all"):
            return {
                k: {**v, "status": HealthStatus.HEALTHY, "suppressed": True}
                for k, v in checks.items()
            }
        for check_name, override in suppression.get("overrides", {}).items():
            if check_name in checks:
                current = checks[check_name].get("status")
                max_severity = HealthStatus(override.get("max_severity", HealthStatus.CRITICAL))
                if current == HealthStatus.CRITICAL and max_severity == HealthStatus.WARNING:
                    checks[check_name] = {**checks[check_name], "status": HealthStatus.WARNING, "suppressed": True}
                elif current in (HealthStatus.WARNING, HealthStatus.CRITICAL) and max_severity == HealthStatus.HEALTHY:
                    checks[check_name] = {**checks[check_name], "status": HealthStatus.HEALTHY, "suppressed": True}
        return checks
