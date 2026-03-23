"""Unit tests for the CMDB reconciler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.base import CmdbRecord, ServerInfo, TicketPriority
from src.cmdb.reconciler import CmdbReconciler, Discrepancy


def _server(name: str, server_id: str | None = None, os_type: str = "Windows") -> ServerInfo:
    return ServerInfo(
        server_id=server_id or f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.HybridCompute/machines/{name}",
        name=name,
        resource_group="rg",
        subscription_id="sub",
        os_type=os_type,
        arc_connected=True,
        last_seen=datetime.now(timezone.utc),
    )


def _record(name: str, ci_id: str = "1", os_version: str = "Windows Server 2022") -> CmdbRecord:
    return CmdbRecord(
        ci_id=ci_id,
        name=name,
        serial_number="SN001",
        ip_address="10.0.0.1",
        os_version=os_version,
        owner="ops-team",
        environment="Production",
    )


@pytest.fixture()
def reconciler() -> CmdbReconciler:
    arc = AsyncMock()
    cmdb = AsyncMock()
    itsm = AsyncMock()
    cosmos = MagicMock()

    mock_ticket = MagicMock()
    mock_ticket.ticket_id = "TICKET-001"
    itsm.create_ticket.return_value = mock_ticket

    return CmdbReconciler(
        arc_adapter=arc,
        cmdb_adapter=cmdb,
        itsm_adapter=itsm,
        cosmos_client=cosmos,
    )


def test_server_in_arc_not_in_cmdb(reconciler: CmdbReconciler):
    """A server present in Arc but absent from CMDB should be flagged as new_in_arc."""
    arc_servers = [_server("new-server")]
    cmdb_records: list[CmdbRecord] = []

    discrepancies = reconciler._compare(arc_servers, cmdb_records)

    assert len(discrepancies) == 1
    assert discrepancies[0].kind == "new_in_arc"
    assert discrepancies[0].server_name == "new-server"


def test_server_in_cmdb_not_in_arc(reconciler: CmdbReconciler):
    """A CMDB record with no corresponding Arc machine should be flagged as missing_from_arc."""
    arc_servers: list[ServerInfo] = []
    cmdb_records = [_record("decom-server", ci_id="99")]

    discrepancies = reconciler._compare(arc_servers, cmdb_records)

    assert len(discrepancies) == 1
    assert discrepancies[0].kind == "missing_from_arc"
    assert discrepancies[0].server_name == "decom-server"
    assert discrepancies[0].cmdb_ci_id == "99"


def test_os_version_mismatch(reconciler: CmdbReconciler):
    """Differing OS types between Arc and CMDB should be flagged as os_mismatch."""
    arc_servers = [_server("srv-001", os_type="Linux")]
    cmdb_records = [_record("srv-001", os_version="Windows Server 2022")]

    discrepancies = reconciler._compare(arc_servers, cmdb_records)

    os_mismatches = [d for d in discrepancies if d.kind == "os_mismatch"]
    assert len(os_mismatches) == 1
    assert os_mismatches[0].arc_value == "Linux"
    assert os_mismatches[0].cmdb_value == "Windows Server 2022"


def test_no_discrepancies_when_in_sync(reconciler: CmdbReconciler):
    """Matching Arc and CMDB records should produce no discrepancies."""
    arc_servers = [_server("srv-match", os_type="Windows")]
    cmdb_records = [_record("srv-match", os_version="Windows Server 2022")]

    discrepancies = reconciler._compare(arc_servers, cmdb_records)
    assert len(discrepancies) == 0


def test_multiple_discrepancy_types(reconciler: CmdbReconciler):
    """Multiple discrepancy types should all be reported."""
    arc_servers = [
        _server("new-one"),
        _server("os-drift", os_type="Linux"),
    ]
    cmdb_records = [
        _record("decom-one", ci_id="10"),
        _record("os-drift", ci_id="20", os_version="Windows Server 2022"),
    ]

    discrepancies = reconciler._compare(arc_servers, cmdb_records)
    kinds = {d.kind for d in discrepancies}
    assert "new_in_arc" in kinds
    assert "missing_from_arc" in kinds
    assert "os_mismatch" in kinds


@pytest.mark.asyncio
async def test_apply_updates_raises_ticket_for_decommission(reconciler: CmdbReconciler):
    """apply_updates should create an ITSM ticket for missing_from_arc discrepancies."""
    discrepancies = [
        Discrepancy(
            kind="missing_from_arc",
            server_name="decom-server",
            arc_value=None,
            cmdb_value="99",
            cmdb_ci_id="99",
        )
    ]
    result = await reconciler.apply_updates(discrepancies)
    assert "TICKET-001" in result["tickets_raised"]
    reconciler._itsm.create_ticket.assert_called_once()
    call_kwargs = reconciler._itsm.create_ticket.call_args.kwargs
    assert "decom-server" in call_kwargs["title"]
    assert call_kwargs["priority"] == TicketPriority.P3
