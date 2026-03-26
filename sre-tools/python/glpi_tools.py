"""GLPI tools for SRE Agent — each function follows the SRE Agent Python tool pattern.

SRE Agent Python tools require:
- A main() function with typed parameters
- JSON-serializable return values
- No persistent state between calls

Create each function as a SEPARATE Python tool in Builder > Tools > Python.
"""

# ============================================================
# Tool 1: glpi-create-ticket
# Description: Create an incident ticket in GLPI ITSM
# ============================================================


def main(title: str, description: str, priority: str = "3") -> dict:
    """Create an incident ticket in GLPI (v11 OAuth2 API).

    Args:
        title: Ticket title (e.g., "[Compliance] CIS Control 1.1 — 3 servers affected")
        description: Full description with remediation steps
        priority: Priority 1-5 (1=very high, 5=very low). Default "3" (medium).
    """
    import requests

    GLPI_BASE = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
    CLIENT_ID = "your-client-id"  # From Setup > OAuth Clients
    CLIENT_SECRET = "your-client-secret"
    USERNAME = "glpi"
    PASSWORD = "your-admin-password"

    # Get OAuth2 access token
    resp = requests.post(
        f"{GLPI_BASE}/api.php/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD,
            "scope": "api",
        },
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]

    # Create ticket via v2 API
    resp = requests.post(
        f"{GLPI_BASE}/api.php/v2/Ticket",
        json={
            "input": {
                "name": title,
                "content": description,
                "type": 1,  # Incident
                "urgency": int(priority),
                "impact": int(priority),
                "priority": int(priority),
            }
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    ticket_id = resp.json()["id"]

    return {
        "ticket_id": ticket_id,
        "title": title,
        "priority": priority,
        "url": f"http://glpi-opsauto-demo.swedencentral.azurecontainer.io/front/ticket.form.php?id={ticket_id}",
        "status": "created",
    }


# ============================================================
# Tool 2: glpi-query-cmdb
# Description: Query GLPI CMDB for a server CI record
# ============================================================


def main(server_name: str) -> dict:
    """Query GLPI CMDB for server configuration item (v11 OAuth2 API).

    Args:
        server_name: The server hostname to look up (e.g., "ArcBox-Win2K22")
    """
    import requests

    GLPI_BASE = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
    CLIENT_ID = "your-client-id"
    CLIENT_SECRET = "your-client-secret"
    USERNAME = "glpi"
    PASSWORD = "your-admin-password"

    # Get OAuth2 access token
    resp = requests.post(
        f"{GLPI_BASE}/api.php/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD,
            "scope": "api",
        },
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]

    # Search for computer by name via v2 API
    resp = requests.get(
        f"{GLPI_BASE}/api.php/v2/Computer",
        params={"filter": f"name=={server_name}"},
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        items = resp.json()
        if items:
            server = items[0] if isinstance(items, list) else items
            return {
                "found": True,
                "ci_id": str(server.get("id")),
                "name": server.get("name"),
                "serial": server.get("serial"),
                "comment": server.get("comment"),
                "last_update": server.get("date_mod"),
            }

    return {"found": False, "server_name": server_name, "message": "Not found in CMDB"}
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
