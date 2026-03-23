"""Unit tests for adapter implementations."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.base import CmdbRecord, Ticket, TicketPriority, TicketStatus
from src.adapters.glpi_adapter import GlpiAdapter, _parse_computer, _parse_ticket
from src.cmdb.reconciler import CmdbReconciler, Discrepancy


# ---------- GlpiAdapter — ticket creation ----------

@pytest.fixture()
def glpi() -> GlpiAdapter:
    adapter = GlpiAdapter(
        base_url="https://glpi.example.com",
        app_token="app-token-123",
        user_token="user-token-456",
    )
    adapter._session_token = "test-session"
    return adapter


_TICKET_JSON = {
    "id": 42,
    "name": "Test incident",
    "content": "Something broke",
    "priority": 4,  # High → P2
    "status": 1,    # New
    "items_id": None,
    "date_creation": "2024-06-01T10:00:00",
    "date_mod": "2024-06-01T10:05:00",
    "links": [{"href": "https://glpi.example.com/ticket/42"}],
}

_COMPUTER_JSON = {
    "id": 7,
    "name": "srv-win-001",
    "serial": "SN123456",
    "ip": "10.0.0.10",
    "os_version": "Windows Server 2022",
    "users_id_tech": "john.doe",
    "locations_id": "Production",
    "date_mod": "2024-06-01T08:00:00",
}


def test_parse_ticket_mapping():
    ticket = _parse_ticket(_TICKET_JSON)
    assert ticket.ticket_id == "42"
    assert ticket.title == "Test incident"
    assert ticket.priority == TicketPriority.P2
    assert ticket.status == TicketStatus.NEW


def test_parse_computer_mapping():
    record = _parse_computer(_COMPUTER_JSON)
    assert record.ci_id == "7"
    assert record.name == "srv-win-001"
    assert record.serial_number == "SN123456"
    assert record.ip_address == "10.0.0.10"
    assert record.os_version == "Windows Server 2022"
    assert record.environment == "Production"


@pytest.mark.asyncio
async def test_glpi_create_ticket(glpi: GlpiAdapter):
    """create_ticket should POST to GLPI and return a Ticket object."""
    with (
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # POST response for create
        create_response = MagicMock()
        create_response.status_code = 201
        create_response.json.return_value = {"id": 42}
        create_response.raise_for_status = MagicMock()

        # GET response for follow-up get_ticket
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = _TICKET_JSON
        get_response.raise_for_status = MagicMock()

        mock_client.post.return_value = create_response
        mock_client.get.return_value = get_response

        ticket = await glpi.create_ticket(
            title="Test incident",
            description="Something broke",
            priority=TicketPriority.P2,
        )

    assert ticket.ticket_id == "42"
    assert ticket.title == "Test incident"
    assert ticket.priority == TicketPriority.P2


@pytest.mark.asyncio
async def test_glpi_get_ticket_not_found(glpi: GlpiAdapter):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        not_found = MagicMock()
        not_found.status_code = 404
        not_found.raise_for_status = MagicMock()
        mock_client.get.return_value = not_found

        result = await glpi.get_ticket("9999")
    assert result is None


@pytest.mark.asyncio
async def test_glpi_cmdb_find_by_name(glpi: GlpiAdapter):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [_COMPUTER_JSON]
        resp.raise_for_status = MagicMock()
        mock_client.get.return_value = resp

        record = await glpi.find_by_name("srv-win-001")

    assert record is not None
    assert record.name == "srv-win-001"
    assert record.serial_number == "SN123456"
