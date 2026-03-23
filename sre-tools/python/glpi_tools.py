"""GLPI tools for SRE Agent — ticket creation and CMDB queries."""

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class GlpiTools:
    """GLPI REST API tools for SRE Agent."""

    def __init__(self) -> None:
        self.base_url = os.environ["GLPI_BASE_URL"].rstrip("/")
        self.app_token = os.environ["GLPI_APP_TOKEN"]
        self.user_token = os.environ["GLPI_USER_TOKEN"]
        self._session_token: str | None = None

    async def _get_session_token(self) -> str:
        if self._session_token:
            return self._session_token
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/initSession",
                headers={
                    "App-Token": self.app_token,
                    "Authorization": f"user_token {self.user_token}",
                },
            )
            resp.raise_for_status()
            self._session_token = resp.json()["session_token"]
            return self._session_token

    async def create_ticket(
        self,
        title: str,
        description: str,
        priority: str = "3",
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Create an incident ticket in GLPI."""
        session_token = await self._get_session_token()
        payload: dict[str, Any] = {
            "input": {
                "name": title,
                "content": description,
                "type": 1,  # Incident
                "urgency": int(priority),
                "impact": int(priority),
                "priority": int(priority),
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/Ticket",
                json=payload,
                headers={
                    "App-Token": self.app_token,
                    "Session-Token": session_token,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            ticket_id = resp.json()["id"]
            log.info("glpi_ticket_created", ticket_id=ticket_id, title=title)
            return {
                "ticket_id": ticket_id,
                "title": title,
                "url": f"{self.base_url}/front/ticket.form.php?id={ticket_id}",
            }

    async def query_cmdb(self, server_name: str) -> dict[str, Any] | None:
        """Query GLPI CMDB for a server CI record."""
        session_token = await self._get_session_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/Computer",
                params={"searchText[1]": server_name, "range": "0-1"},
                headers={
                    "App-Token": self.app_token,
                    "Session-Token": session_token,
                },
            )
            if resp.status_code in (200, 206):
                items = resp.json()
                if items:
                    return {
                        "ci_id": str(items[0]["id"]),
                        "name": items[0].get("name"),
                        "raw": items[0],
                    }
            return None
