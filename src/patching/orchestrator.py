"""Patch orchestrator — manages multi-wave monthly patch deployments."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from src.adapters.base import (
    ArcAdapterBase,
    ItsmsAdapterBase,
    PatchAdapterBase,
    PatchClassification,
    TicketPriority,
)

log = structlog.get_logger(__name__)

_DEFAULT_CLASSIFICATIONS = [
    PatchClassification.CRITICAL,
    PatchClassification.SECURITY,
]


class PatchOrchestrator:
    """Coordinates multi-wave Windows patch deployments via Azure Update Manager."""

    def __init__(
        self,
        patch_adapter: PatchAdapterBase,
        arc_adapter: ArcAdapterBase,
        itsm_adapter: ItsmsAdapterBase,
        cosmos_client: Any,
    ) -> None:
        self._patch = patch_adapter
        self._arc = arc_adapter
        self._itsm = itsm_adapter
        self._cosmos = cosmos_client

    async def run_monthly_assessment(self, server_ids: list[str]) -> dict[str, Any]:
        """Trigger patch assessment for all servers and store results."""
        log.info("patching.run_monthly_assessment", server_count=len(server_ids))
        now = datetime.now(timezone.utc)
        results = await asyncio.gather(
            *[self._patch.assess_server(sid) for sid in server_ids],
            return_exceptions=True,
        )

        assessment: dict[str, Any] = {
            "run_id": f"assessment-{now.strftime('%Y%m%d-%H%M%S')}",
            "timestamp": now.isoformat(),
            "servers": {},
        }
        for sid, result in zip(server_ids, results):
            if isinstance(result, Exception):
                assessment["servers"][sid] = {"error": str(result)}
            else:
                assessment["servers"][sid] = {
                    "patch_count": len(result),  # type: ignore[arg-type]
                    "patches": [
                        {
                            "kb_id": p.kb_id,
                            "title": p.title,
                            "classification": p.classification.value,
                            "severity": p.severity,
                        }
                        for p in result  # type: ignore[union-attr]
                    ],
                }

        try:
            container = self._cosmos.get_container_client("patch-assessments")
            container.upsert_item({**assessment, "id": assessment["run_id"]})
        except Exception as exc:
            log.warning("patching.assessment.cosmos_error", error=str(exc))

        log.info("patching.run_monthly_assessment.done")
        return assessment

    async def create_patch_plan(self, server_ids: list[str]) -> dict[str, list[str]]:
        """Group servers into waves by environment tag."""
        servers = await asyncio.gather(
            *[self._arc.get_server(sid) for sid in server_ids], return_exceptions=True
        )
        waves: dict[str, list[str]] = {"dev_test": [], "non_critical_prod": [], "critical_prod": []}
        for sid, server in zip(server_ids, servers):
            if isinstance(server, Exception) or server is None:
                waves["non_critical_prod"].append(sid)
                continue
            env = (server.tags or {}).get("Environment", "").lower()
            criticality = (server.tags or {}).get("Criticality", "").lower()
            if env in ("dev", "test"):
                waves["dev_test"].append(sid)
            elif criticality in ("high", "critical"):
                waves["critical_prod"].append(sid)
            else:
                waves["non_critical_prod"].append(sid)
        log.info(
            "patching.create_patch_plan",
            dev_test=len(waves["dev_test"]),
            non_critical_prod=len(waves["non_critical_prod"]),
            critical_prod=len(waves["critical_prod"]),
        )
        return waves

    async def execute_wave(
        self,
        server_ids: list[str],
        wave_name: str,
        schedule_time: datetime | None = None,
        require_approval: bool = True,
        classifications: list[PatchClassification] | None = None,
    ) -> dict[str, Any]:
        """Schedule a patch deployment wave."""
        if not server_ids:
            return {"wave": wave_name, "skipped": True, "reason": "No servers"}

        if require_approval:
            log.info("patching.execute_wave.awaiting_approval", wave=wave_name)

        schedule = schedule_time or datetime.now(timezone.utc)
        clss = classifications or _DEFAULT_CLASSIFICATIONS

        ticket = await self._itsm.create_ticket(
            title=f"Patch Wave: {wave_name} — {schedule.strftime('%Y-%m-%d')}",
            description=f"Automated patch deployment for {len(server_ids)} servers.\n"
            f"Wave: {wave_name}\nScheduled: {schedule.isoformat()}",
            priority=TicketPriority.P3,
        )

        deployment_id = await self._patch.schedule_deployment(server_ids, schedule, clss)
        log.info("patching.execute_wave.scheduled", wave=wave_name, deployment_id=deployment_id)

        result = {
            "wave": wave_name,
            "server_count": len(server_ids),
            "deployment_id": deployment_id,
            "ticket_id": ticket.ticket_id,
            "scheduled_at": schedule.isoformat(),
        }
        return result

    async def validate_post_patch(self, server_ids: list[str]) -> dict[str, Any]:
        """Check patch assessment results after patching to confirm installation."""
        log.info("patching.validate_post_patch", server_count=len(server_ids))
        results: dict[str, Any] = {}
        for sid in server_ids:
            try:
                patches = await self._patch.assess_server(sid)
                critical_remaining = [
                    p for p in patches
                    if not p.installed and p.classification in (
                        PatchClassification.CRITICAL, PatchClassification.SECURITY
                    )
                ]
                results[sid] = {
                    "remaining_patches": len(patches),
                    "critical_remaining": len(critical_remaining),
                    "validated": len(critical_remaining) == 0,
                }
            except Exception as exc:
                results[sid] = {"error": str(exc), "validated": False}
        return results
