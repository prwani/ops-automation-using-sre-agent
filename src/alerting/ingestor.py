"""Alert ingestor — polls Defender for Cloud alerts, deduplicates, and routes them."""

import os
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.adapters.base import DefenderAdapterBase, ItsmsAdapterBase, TicketPriority

log = structlog.get_logger(__name__)

_SEVERITY_PRIORITY: dict[str, TicketPriority] = {
    "high": TicketPriority.P2,
    "critical": TicketPriority.P1,
}


class AlertIngestor:
    """Ingests Defender for Cloud alerts and routes them by severity."""

    def __init__(
        self,
        defender_adapter: DefenderAdapterBase,
        itsm_adapter: ItsmsAdapterBase,
        subscription_id: str,
        sre_agent_url: str | None = None,
    ) -> None:
        self._defender = defender_adapter
        self._itsm = itsm_adapter
        self._subscription_id = subscription_id
        self._sre_agent_url = sre_agent_url or os.environ.get("SRE_AGENT_WEBHOOK_URL", "")
        self._processed_ids: set[str] = set()

    async def ingest_alerts(self) -> dict[str, Any]:
        """Poll Defender for Cloud, deduplicate, and route new alerts."""
        log.info("alerting.ingest_alerts", subscription_id=self._subscription_id)
        all_alerts = await self._defender.get_security_alerts(self._subscription_id)
        new_alerts = await self._deduplicate(all_alerts)
        log.info("alerting.ingest_alerts.new", count=len(new_alerts))

        results = {"total": len(all_alerts), "new": len(new_alerts), "routed": []}
        for alert in new_alerts:
            routing = await self.route_alert(alert)
            results["routed"].append(routing)

        return results

    async def route_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        """Route a single alert based on severity."""
        props = alert.get("properties", {})
        severity = props.get("severity", "low").lower()
        alert_id = alert.get("name", alert.get("id", "unknown"))
        alert_name = props.get("alertDisplayName", "Security Alert")

        log.info("alerting.route_alert", alert_id=alert_id, severity=severity)

        action = "logged"
        ticket_id = None

        if severity in ("high",):
            ticket = await self._itsm.create_ticket(
                title=f"[{severity.upper()}] {alert_name}",
                description=props.get("description", "") + f"\n\nAlert ID: {alert_id}",
                priority=_SEVERITY_PRIORITY[severity],
            )
            ticket_id = ticket.ticket_id
            action = "ticket_created"
        elif severity == "critical":
            ticket = await self._itsm.create_ticket(
                title=f"[CRITICAL] {alert_name}",
                description=props.get("description", "") + f"\n\nAlert ID: {alert_id}",
                priority=TicketPriority.P1,
            )
            ticket_id = ticket.ticket_id
            await self._call_sre_agent(alert)
            action = "ticket_created+sre_triggered"

        await self._mark_processed(alert_id)
        return {"alert_id": alert_id, "severity": severity, "action": action, "ticket_id": ticket_id}

    async def _deduplicate(self, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out alerts already processed in this session."""
        return [a for a in alerts if a.get("name", a.get("id", "")) not in self._processed_ids]

    async def _mark_processed(self, alert_id: str) -> None:
        """Record an alert ID locally so it won't be re-processed."""
        self._processed_ids.add(alert_id)
        log.info("alerting.mark_processed", alert_id=alert_id)

    async def _call_sre_agent(self, alert: dict[str, Any]) -> None:
        """Post a critical alert to the SRE Agent webhook endpoint."""
        if not self._sre_agent_url:
            log.warning("alerting.sre_agent.no_url")
            return
        props = alert.get("properties", {})
        payload = {
            "alert_id": alert.get("name"),
            "title": props.get("alertDisplayName"),
            "severity": props.get("severity"),
            "description": props.get("description"),
            "resource": props.get("compromisedEntity"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(self._sre_agent_url, json=payload)
                response.raise_for_status()
            log.info("alerting.sre_agent.triggered", alert_id=alert.get("name"))
        except Exception as exc:
            log.error("alerting.sre_agent.failed", error=str(exc))
