"""CMDB reconciler — compares Arc inventory against GLPI CMDB and reports drift."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

from src.adapters.base import (
    ArcAdapterBase,
    CmdbAdapterBase,
    CmdbRecord,
    ItsmsAdapterBase,
    ServerInfo,
    TicketPriority,
)

log = structlog.get_logger(__name__)


@dataclass
class Discrepancy:
    kind: str  # "new_in_arc" | "missing_from_arc" | "os_mismatch" | "ip_mismatch"
    server_name: str
    arc_value: str | None
    cmdb_value: str | None
    server_id: str | None = None
    cmdb_ci_id: str | None = None


class CmdbReconciler:
    """Reconciles Azure Arc server inventory against CMDB Computer CI records."""

    def __init__(
        self,
        arc_adapter: ArcAdapterBase,
        cmdb_adapter: CmdbAdapterBase,
        itsm_adapter: ItsmsAdapterBase,
        cosmos_client: Any,
    ) -> None:
        self._arc = arc_adapter
        self._cmdb = cmdb_adapter
        self._itsm = itsm_adapter
        self._cosmos = cosmos_client

    async def run_reconciliation(self) -> dict[str, Any]:
        """Compare Arc inventory vs CMDB and return discrepancies."""
        log.info("cmdb.run_reconciliation")
        arc_servers = await self._get_arc_inventory()
        cmdb_records = await self._get_cmdb_inventory()
        discrepancies = self._compare(arc_servers, cmdb_records)

        now = datetime.now(timezone.utc)
        report: dict[str, Any] = {
            "run_id": f"cmdb-reconcile-{now.strftime('%Y%m%d-%H%M%S')}",
            "timestamp": now.isoformat(),
            "arc_server_count": len(arc_servers),
            "cmdb_record_count": len(cmdb_records),
            "discrepancy_count": len(discrepancies),
            "discrepancies": [d.__dict__ for d in discrepancies],
        }
        log.info(
            "cmdb.run_reconciliation.done",
            discrepancies=len(discrepancies),
        )
        return report

    async def _get_arc_inventory(self) -> list[ServerInfo]:
        return await self._arc.list_servers()

    async def _get_cmdb_inventory(self) -> list[CmdbRecord]:
        return await self._cmdb.list_records()

    def _compare(
        self,
        arc_servers: list[ServerInfo],
        cmdb_records: list[CmdbRecord],
    ) -> list[Discrepancy]:
        discrepancies: list[Discrepancy] = []
        arc_by_name = {s.name.lower(): s for s in arc_servers}
        cmdb_by_name = {r.name.lower(): r for r in cmdb_records}

        # In Arc but not in CMDB → new server
        for name, server in arc_by_name.items():
            if name not in cmdb_by_name:
                discrepancies.append(
                    Discrepancy(
                        kind="new_in_arc",
                        server_name=server.name,
                        arc_value=server.server_id,
                        cmdb_value=None,
                        server_id=server.server_id,
                    )
                )
                continue

            cmdb = cmdb_by_name[name]

            # OS version mismatch
            arc_os = server.os_type
            cmdb_os = cmdb.os_version or ""
            if arc_os and cmdb_os and arc_os.lower() not in cmdb_os.lower():
                discrepancies.append(
                    Discrepancy(
                        kind="os_mismatch",
                        server_name=server.name,
                        arc_value=arc_os,
                        cmdb_value=cmdb_os,
                        server_id=server.server_id,
                        cmdb_ci_id=cmdb.ci_id,
                    )
                )

        # In CMDB but not in Arc → potentially decommissioned
        for name, record in cmdb_by_name.items():
            if name not in arc_by_name:
                discrepancies.append(
                    Discrepancy(
                        kind="missing_from_arc",
                        server_name=record.name,
                        arc_value=None,
                        cmdb_value=record.ci_id,
                        cmdb_ci_id=record.ci_id,
                    )
                )

        return discrepancies

    async def apply_updates(
        self,
        discrepancies: list[Discrepancy],
        auto_update: bool = False,
    ) -> dict[str, Any]:
        """Apply non-destructive CMDB updates and raise tickets for decommissions."""
        applied: list[str] = []
        tickets: list[str] = []

        for d in discrepancies:
            if d.kind == "os_mismatch" and auto_update and d.cmdb_ci_id:
                arc_server = await self._arc.get_server(d.server_id or "")
                if arc_server:
                    record = await self._cmdb.get_record(d.cmdb_ci_id)
                    if record:
                        record.os_version = arc_server.os_type
                        await self._cmdb.upsert_record(record)
                        applied.append(f"os_mismatch:{d.server_name}")

            elif d.kind == "missing_from_arc":
                ticket = await self._itsm.create_ticket(
                    title=f"Possible decommission: {d.server_name}",
                    description=(
                        f"Server '{d.server_name}' is present in CMDB (CI: {d.cmdb_ci_id}) "
                        "but is not found in Azure Arc. Please verify if it has been decommissioned."
                    ),
                    priority=TicketPriority.P3,
                )
                tickets.append(ticket.ticket_id)

        return {"applied_updates": applied, "tickets_raised": tickets}
