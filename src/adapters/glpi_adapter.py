"""GLPI adapter — implements both ItsmsAdapterBase and CmdbAdapterBase."""

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import (
    CmdbAdapterBase,
    CmdbRecord,
    ItsmsAdapterBase,
    Ticket,
    TicketPriority,
    TicketStatus,
)

log = structlog.get_logger(__name__)

# GLPI itilcategory / priority mappings
_PRIORITY_TO_GLPI: dict[TicketPriority, int] = {
    TicketPriority.P1: 5,  # Very High
    TicketPriority.P2: 4,  # High
    TicketPriority.P3: 3,  # Medium
    TicketPriority.P4: 2,  # Low
}
_GLPI_TO_PRIORITY: dict[int, TicketPriority] = {v: k for k, v in _PRIORITY_TO_GLPI.items()}

_STATUS_TO_GLPI: dict[TicketStatus, int] = {
    TicketStatus.NEW: 1,
    TicketStatus.IN_PROGRESS: 2,
    TicketStatus.RESOLVED: 5,
    TicketStatus.CLOSED: 6,
}
_GLPI_TO_STATUS: dict[int, TicketStatus] = {v: k for k, v in _STATUS_TO_GLPI.items()}


def _parse_ticket(data: dict[str, Any]) -> Ticket:
    created_raw = data.get("date_creation")
    updated_raw = data.get("date_mod")
    return Ticket(
        ticket_id=str(data["id"]),
        title=data.get("name", ""),
        description=data.get("content", ""),
        priority=_GLPI_TO_PRIORITY.get(data.get("priority", 3), TicketPriority.P3),
        status=_GLPI_TO_STATUS.get(data.get("status", 1), TicketStatus.NEW),
        server_id=data.get("items_id"),
        created_at=datetime.fromisoformat(created_raw) if created_raw else None,
        updated_at=datetime.fromisoformat(updated_raw) if updated_raw else None,
        url=data.get("links", [{}])[0].get("href") if data.get("links") else None,
    )


def _parse_computer(data: dict[str, Any]) -> CmdbRecord:
    updated_raw = data.get("date_mod")
    return CmdbRecord(
        ci_id=str(data["id"]),
        name=data.get("name", ""),
        serial_number=data.get("serial") or None,
        ip_address=data.get("ip") or None,
        os_version=data.get("os_version") or None,
        owner=data.get("users_id_tech") or None,
        environment=data.get("locations_id") or None,
        last_updated=datetime.fromisoformat(updated_raw) if updated_raw else None,
        extra={k: v for k, v in data.items() if k not in {"id", "name", "serial", "ip"}},
    )


class GlpiAdapter(ItsmsAdapterBase, CmdbAdapterBase):
    """GLPI REST API adapter for ITSM tickets and CMDB computer CIs."""

    def __init__(self, base_url: str, app_token: str, user_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._app_token = app_token
        self._user_token = user_token
        self._session_token: str | None = None

    async def _ensure_session(self) -> str:
        if self._session_token:
            return self._session_token
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/initSession",
                headers={
                    "App-Token": self._app_token,
                    "Authorization": f"user_token {self._user_token}",
                },
            )
            response.raise_for_status()
            self._session_token = response.json()["session_token"]
            return self._session_token

    def _headers(self, session_token: str) -> dict[str, str]:
        return {
            "App-Token": self._app_token,
            "Session-Token": session_token,
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_ticket(
        self,
        title: str,
        description: str,
        priority: TicketPriority,
        server_id: str | None = None,
        category: str | None = None,
    ) -> Ticket:
        log.info("glpi.create_ticket", title=title, priority=priority)
        session_token = await self._ensure_session()
        payload: dict[str, Any] = {
            "input": {
                "name": title,
                "content": description,
                "priority": _PRIORITY_TO_GLPI[priority],
                "status": _STATUS_TO_GLPI[TicketStatus.NEW],
                "type": 1,  # Incident
            }
        }
        if server_id:
            payload["input"]["items_id"] = server_id
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/apirest.php/Ticket",
                json=payload,
                headers=self._headers(session_token),
            )
            response.raise_for_status()
            created = response.json()
            ticket_id = str(created.get("id", created.get("0", {}).get("id", "")))
        ticket = await self.get_ticket(ticket_id)
        assert ticket is not None
        log.info("glpi.create_ticket.done", ticket_id=ticket_id)
        return ticket

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def update_ticket(
        self, ticket_id: str, status: TicketStatus, notes: str | None = None
    ) -> Ticket:
        log.info("glpi.update_ticket", ticket_id=ticket_id, status=status)
        session_token = await self._ensure_session()
        payload: dict[str, Any] = {
            "input": {"status": _STATUS_TO_GLPI[status]}
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                f"{self._base_url}/apirest.php/Ticket/{ticket_id}",
                json=payload,
                headers=self._headers(session_token),
            )
            response.raise_for_status()
            if notes:
                await client.post(
                    f"{self._base_url}/apirest.php/Ticket/{ticket_id}/ITILFollowup",
                    json={"input": {"content": notes, "is_private": 0}},
                    headers=self._headers(session_token),
                )
        ticket = await self.get_ticket(ticket_id)
        assert ticket is not None
        return ticket

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        session_token = await self._ensure_session()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/Ticket/{ticket_id}",
                headers=self._headers(session_token),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _parse_ticket(response.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_open_tickets(self, server_id: str | None = None) -> list[Ticket]:
        session_token = await self._ensure_session()
        params: dict[str, Any] = {
            "searchText[status]": f"{_STATUS_TO_GLPI[TicketStatus.NEW]},{_STATUS_TO_GLPI[TicketStatus.IN_PROGRESS]}",
            "range": "0-200",
        }
        if server_id:
            params["searchText[items_id]"] = server_id
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/Ticket",
                params=params,
                headers=self._headers(session_token),
            )
            response.raise_for_status()
            return [_parse_ticket(t) for t in response.json()]

    # --- CmdbAdapterBase ---

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_record(self, ci_id: str) -> CmdbRecord | None:
        session_token = await self._ensure_session()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/Computer/{ci_id}",
                headers=self._headers(session_token),
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _parse_computer(response.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def find_by_name(self, name: str) -> CmdbRecord | None:
        session_token = await self._ensure_session()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/Computer",
                params={"searchText[name]": name, "range": "0-1"},
                headers=self._headers(session_token),
            )
            response.raise_for_status()
            items = response.json()
            if not items:
                return None
            return _parse_computer(items[0])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def upsert_record(self, record: CmdbRecord) -> CmdbRecord:
        log.info("glpi.upsert_record", name=record.name)
        session_token = await self._ensure_session()
        payload: dict[str, Any] = {
            "input": {
                "name": record.name,
                "serial": record.serial_number or "",
                "os_version": record.os_version or "",
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            if record.ci_id and record.ci_id != "":
                response = await client.put(
                    f"{self._base_url}/apirest.php/Computer/{record.ci_id}",
                    json=payload,
                    headers=self._headers(session_token),
                )
                response.raise_for_status()
                return await self.get_record(record.ci_id) or record
            else:
                response = await client.post(
                    f"{self._base_url}/apirest.php/Computer",
                    json=payload,
                    headers=self._headers(session_token),
                )
                response.raise_for_status()
                new_id = str(response.json().get("id", ""))
                return await self.get_record(new_id) or record

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_records(self, environment: str | None = None) -> list[CmdbRecord]:
        session_token = await self._ensure_session()
        params: dict[str, Any] = {"range": "0-500"}
        if environment:
            params["searchText[locations_id]"] = environment
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/apirest.php/Computer",
                params=params,
                headers=self._headers(session_token),
            )
            response.raise_for_status()
            return [_parse_computer(item) for item in response.json()]
