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

    # Create ticket via v2 API (no "input" wrapper for v2)
    resp = requests.post(
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
        f"{GLPI_BASE}/api.php/v2.2/Assets/Computer",
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


# ============================================================
# Tool 3: glpi-list-open-tickets
# Description: List all open (New/Assigned) tickets in GLPI
# ============================================================


def main() -> dict:
    """List all open tickets from GLPI (status=New or Assigned).

    Returns tickets with id, name, content, status, priority, and date.
    """
    import requests

    GLPI_BASE = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
    CLIENT_ID = "your-client-id"
    CLIENT_SECRET = "your-client-secret"
    USERNAME = "glpi"
    PASSWORD = "your-admin-password"

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

    resp = requests.get(
        f"{GLPI_BASE}/api.php/v2.2/Assistance/Ticket",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    all_tickets = resp.json()

    # Filter for open tickets: status 1 (New) or 2 (Assigned)
    open_tickets = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "content": t.get("content", "")[:500],
            "status": t.get("status"),
            "priority": t.get("priority"),
            "date": t.get("date"),
        }
        for t in (all_tickets if isinstance(all_tickets, list) else [all_tickets])
        if t.get("status") in (1, 2)
    ]

    return {
        "total_open": len(open_tickets),
        "tickets": open_tickets,
    }


# ============================================================
# Tool 4: glpi-add-followup
# Description: Add a followup note to an existing GLPI ticket
# ============================================================


def main(ticket_id: str, content: str) -> dict:
    """Add a followup note to a GLPI ticket (v11 OAuth2 API).

    Args:
        ticket_id: The numeric ID of the GLPI ticket.
        content: The followup text (supports HTML).
    """
    import requests

    GLPI_BASE = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
    CLIENT_ID = "your-client-id"
    CLIENT_SECRET = "your-client-secret"
    USERNAME = "glpi"
    PASSWORD = "your-admin-password"

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

    # Try v2 API first
    url = f"{GLPI_BASE}/api.php/v2.2/Assistance/Ticket/{ticket_id}/ITILFollowup"
    resp = requests.post(
        url,
        json={"content": content},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    if resp.status_code in (200, 201):
        return {
            "ticket_id": ticket_id,
            "followup_added": True,
            "status": "success",
        }

    return {
        "ticket_id": ticket_id,
        "followup_added": False,
        "status": "error",
        "error": resp.text[:300],
    }


# ============================================================
# Tool 5: glpi-update-computer
# Description: Update a GLPI CMDB computer record
# ============================================================


def main(computer_id: str, comment: str) -> dict:
    """Update a computer CI record in GLPI CMDB (v11 OAuth2 API).

    Args:
        computer_id: The numeric ID of the GLPI computer record.
        comment: New comment/description for the computer record.
    """
    import requests

    GLPI_BASE = "http://glpi-opsauto-demo.swedencentral.azurecontainer.io"
    CLIENT_ID = "your-client-id"
    CLIENT_SECRET = "your-client-secret"
    USERNAME = "glpi"
    PASSWORD = "your-admin-password"

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

    resp = requests.patch(
        f"{GLPI_BASE}/api.php/v2.2/Assets/Computer/{computer_id}",
        json={"comment": comment},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    if resp.status_code in (200, 204):
        return {
            "computer_id": computer_id,
            "updated": True,
            "new_comment": comment[:200],
        }

    return {
        "computer_id": computer_id,
        "updated": False,
        "error": resp.text[:300],
    }

