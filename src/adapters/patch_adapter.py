"""Azure Update Manager adapter — implements PatchAdapterBase."""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import PatchAdapterBase, PatchClassification, PatchInfo

log = structlog.get_logger(__name__)

_ARM_BASE = "https://management.azure.com"
_UPDATE_MANAGER_API = "2023-09-01-preview"
_MAINTENANCE_API = "2023-04-01"


class PatchAdapter(PatchAdapterBase):
    """Azure Update Manager adapter using ARM REST API."""

    def __init__(self, credential, subscription_id: str) -> None:
        self._credential = credential
        self._subscription_id = subscription_id

    def _token(self) -> str:
        return self._credential.get_token("https://management.azure.com/.default").token

    def _parse_patch(self, item: dict[str, Any], server_id: str) -> PatchInfo:
        props = item.get("properties", {})
        classification_raw = props.get("classifications", ["Update"])[0]
        try:
            classification = PatchClassification(classification_raw)
        except ValueError:
            classification = PatchClassification.UPDATE
        return PatchInfo(
            patch_id=item.get("id", ""),
            kb_id=props.get("kbId", ""),
            title=props.get("patchName", props.get("name", "")),
            classification=classification,
            severity=props.get("msrcSeverity", "Unspecified"),
            server_id=server_id,
            installed=props.get("installationState", "NotInstalled") == "Installed",
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def assess_server(self, server_id: str) -> list[PatchInfo]:
        """Trigger a patch assessment and return missing patches."""
        log.info("patch.assess_server", server_id=server_id)
        loop = asyncio.get_event_loop()

        # Trigger on-demand assessment
        assess_url = (
            f"{_ARM_BASE}{server_id}/assessPatches"
            f"?api-version={_UPDATE_MANAGER_API}"
        )
        import httpx

        token = await loop.run_in_executor(None, self._token)
        async with httpx.AsyncClient(timeout=60) as client:
            # Kick off assessment
            response = await client.post(
                assess_url,
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            if response.status_code not in (200, 202):
                log.warning("patch.assess_server.failed", status=response.status_code)
                return []

            # Retrieve pending patches from the assessment results
            patches_url = (
                f"{_ARM_BASE}{server_id}/patchAssessmentResults/latest/softwarePatches"
                f"?api-version={_UPDATE_MANAGER_API}"
            )
            patches_response = await client.get(
                patches_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            if patches_response.status_code != 200:
                return []
            data = patches_response.json()

        patches = [self._parse_patch(item, server_id) for item in data.get("value", [])]
        log.info("patch.assess_server.done", server_id=server_id, count=len(patches))
        return patches

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def schedule_deployment(
        self,
        server_ids: list[str],
        schedule_time: datetime,
        classifications: list[PatchClassification],
    ) -> str:
        """Create a one-time maintenance configuration to install patches."""
        import httpx

        log.info("patch.schedule_deployment", server_count=len(server_ids))
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._token)

        config_name = f"ops-auto-{schedule_time.strftime('%Y%m%d-%H%M')}"
        url = (
            f"{_ARM_BASE}/subscriptions/{self._subscription_id}"
            f"/providers/Microsoft.Maintenance/maintenanceConfigurations/{config_name}"
            f"?api-version={_MAINTENANCE_API}"
        )
        payload = {
            "location": "global",
            "properties": {
                "maintenanceScope": "InGuestPatch",
                "installPatches": {
                    "windowsParameters": {
                        "classificationsToInclude": [c.value for c in classifications],
                        "rebootSetting": "IfRequired",
                    }
                },
                "maintenanceWindow": {
                    "startDateTime": schedule_time.strftime("%Y-%m-%d %H:%M"),
                    "duration": "02:00",
                    "timeZone": "UTC",
                    "recurEvery": "1Day",
                },
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                url, json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            config_id = response.json().get("id", config_name)

            # Associate each server with the maintenance configuration
            for server_id in server_ids:
                assign_url = (
                    f"{_ARM_BASE}{server_id}"
                    f"/providers/Microsoft.Maintenance/configurationAssignments/{config_name}"
                    f"?api-version={_MAINTENANCE_API}"
                )
                await client.put(
                    assign_url,
                    json={"properties": {"maintenanceConfigurationId": config_id}},
                    headers={"Authorization": f"Bearer {token}"},
                )

        log.info("patch.schedule_deployment.done", config_id=config_id)
        return config_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_deployment_status(self, deployment_id: str) -> dict[str, Any]:
        """Get the status of a maintenance configuration / deployment run."""
        import httpx

        log.info("patch.get_deployment_status", deployment_id=deployment_id)
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._token)
        url = f"{_ARM_BASE}{deployment_id}?api-version={_MAINTENANCE_API}"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
        props = data.get("properties", {})
        return {
            "deployment_id": deployment_id,
            "status": props.get("lastRunStatus", {}).get("status", "Unknown"),
            "last_run": props.get("lastRunStatus", {}).get("startTime"),
            "properties": props,
        }
