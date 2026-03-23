"""Base adapter interfaces — all external integrations implement these contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class PatchClassification(str, Enum):
    CRITICAL = "Critical"
    SECURITY = "Security"
    DEFINITION = "Definition"
    UPDATE_ROLLUP = "UpdateRollup"
    SERVICE_PACK = "ServicePack"
    TOOL = "Tool"
    FEATURE_PACK = "FeaturePack"
    UPDATE = "Update"


class TicketPriority(str, Enum):
    P1 = "1"
    P2 = "2"
    P3 = "3"
    P4 = "4"


class TicketStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class ServerInfo:
    server_id: str
    name: str
    resource_group: str
    subscription_id: str
    os_type: str
    arc_connected: bool
    last_seen: datetime | None = None
    tags: dict[str, str] | None = None


@dataclass
class RunCommandResult:
    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0


@dataclass
class PatchInfo:
    patch_id: str
    kb_id: str
    title: str
    classification: PatchClassification
    severity: str
    server_id: str
    installed: bool
    installed_at: datetime | None = None


@dataclass
class Ticket:
    ticket_id: str
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    server_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    url: str | None = None


@dataclass
class CmdbRecord:
    ci_id: str
    name: str
    serial_number: str | None
    ip_address: str | None
    os_version: str | None
    owner: str | None
    environment: str | None
    last_updated: datetime | None = None
    extra: dict[str, Any] | None = None


class ArcAdapterBase(ABC):
    """Interface for Azure Arc operations."""

    @abstractmethod
    async def list_servers(self) -> list[ServerInfo]:
        """List all Arc-enrolled servers."""

    @abstractmethod
    async def run_command(
        self, server_id: str, script: str, timeout_seconds: int = 300
    ) -> RunCommandResult:
        """Execute a script on a server via Arc Run Command."""

    @abstractmethod
    async def get_server(self, server_id: str) -> ServerInfo | None:
        """Get details for a specific server."""


class DefenderAdapterBase(ABC):
    """Interface for Microsoft Defender for Cloud operations."""

    @abstractmethod
    async def get_secure_score(self, subscription_id: str) -> float:
        """Get the overall secure score (0-100)."""

    @abstractmethod
    async def get_compliance_results(
        self, subscription_id: str, standard: str
    ) -> list[dict[str, Any]]:
        """Get compliance results for a regulatory standard."""

    @abstractmethod
    async def get_security_alerts(
        self, subscription_id: str, severity: str | None = None
    ) -> list[dict[str, Any]]:
        """Get active security alerts."""

    @abstractmethod
    async def get_agent_health(self, server_id: str) -> dict[str, Any]:
        """Check Defender for Endpoint agent health on a server."""


class ItsmsAdapterBase(ABC):
    """Interface for ITSM ticket management."""

    @abstractmethod
    async def create_ticket(
        self,
        title: str,
        description: str,
        priority: TicketPriority,
        server_id: str | None = None,
        category: str | None = None,
    ) -> Ticket:
        """Create a new incident ticket."""

    @abstractmethod
    async def update_ticket(
        self, ticket_id: str, status: TicketStatus, notes: str | None = None
    ) -> Ticket:
        """Update ticket status and add notes."""

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Retrieve a ticket by ID."""

    @abstractmethod
    async def list_open_tickets(self, server_id: str | None = None) -> list[Ticket]:
        """List open tickets, optionally filtered by server."""


class CmdbAdapterBase(ABC):
    """Interface for CMDB operations."""

    @abstractmethod
    async def get_record(self, ci_id: str) -> CmdbRecord | None:
        """Get a CI record by ID."""

    @abstractmethod
    async def find_by_name(self, name: str) -> CmdbRecord | None:
        """Find a CI record by server name."""

    @abstractmethod
    async def upsert_record(self, record: CmdbRecord) -> CmdbRecord:
        """Create or update a CI record."""

    @abstractmethod
    async def list_records(self, environment: str | None = None) -> list[CmdbRecord]:
        """List all CI records, optionally filtered by environment."""


class PatchAdapterBase(ABC):
    """Interface for patch management (Azure Update Manager)."""

    @abstractmethod
    async def assess_server(self, server_id: str) -> list[PatchInfo]:
        """Get missing patches for a server."""

    @abstractmethod
    async def schedule_deployment(
        self,
        server_ids: list[str],
        schedule_time: datetime,
        classifications: list[PatchClassification],
    ) -> str:
        """Schedule a patch deployment. Returns deployment ID."""

    @abstractmethod
    async def get_deployment_status(self, deployment_id: str) -> dict[str, Any]:
        """Get status of a patch deployment."""
