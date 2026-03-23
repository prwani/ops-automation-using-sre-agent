"""Microsoft Defender for Cloud adapter — implements DefenderAdapterBase."""

import asyncio
from typing import Any
from urllib.parse import quote

import httpx
import structlog
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import DefenderAdapterBase

log = structlog.get_logger(__name__)

_ARM_BASE = "https://management.azure.com"
_MDE_BASE = "https://api.securitycenter.microsoft.com"
_API_VERSION_SECURITY = "2020-01-01"


class DefenderAdapter(DefenderAdapterBase):
    """Defender for Cloud adapter using ARM REST and MDE APIs."""

    def __init__(self, credential, subscription_id: str) -> None:
        self._credential = credential
        self._subscription_id = subscription_id
        self._graph_client = ResourceGraphClient(credential)

    def _arm_token(self) -> str:
        token = self._credential.get_token("https://management.azure.com/.default")
        return token.token

    def _mde_token(self) -> str:
        token = self._credential.get_token("https://api.securitycenter.microsoft.com/.default")
        return token.token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_secure_score(self, subscription_id: str) -> float:
        """Get the overall secure score (0–100) from Defender for Cloud."""
        log.info("defender.get_secure_score", subscription_id=subscription_id)
        url = (
            f"{_ARM_BASE}/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Security/secureScores/ascScore"
            f"?api-version={_API_VERSION_SECURITY}"
        )
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._arm_token)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
            current = data.get("properties", {}).get("score", {}).get("current", 0.0)
            max_score = data.get("properties", {}).get("score", {}).get("max", 100.0)
            score = (current / max_score * 100) if max_score else 0.0
            log.info("defender.get_secure_score.done", score=score)
            return round(score, 2)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_compliance_results(
        self, subscription_id: str, standard: str
    ) -> list[dict[str, Any]]:
        """Get compliance control results for a regulatory standard."""
        log.info("defender.get_compliance_results", standard=standard)
        url = (
            f"{_ARM_BASE}/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Security/regulatoryComplianceStandards"
            f"/{quote(standard, safe='')}/controls?api-version=2019-01-01-preview"
        )
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._arm_token)
        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            next_url: str | None = url
            while next_url:
                response = await client.get(
                    next_url, headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("value", []))
                next_url = data.get("nextLink")
        log.info("defender.get_compliance_results.done", count=len(results))
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_security_alerts(
        self, subscription_id: str, severity: str | None = None
    ) -> list[dict[str, Any]]:
        """Get active security alerts from Defender for Cloud."""
        log.info("defender.get_security_alerts", severity=severity)
        url = (
            f"{_ARM_BASE}/subscriptions/{subscription_id}"
            f"/providers/Microsoft.Security/alerts?api-version=2022-01-01"
        )
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._arm_token)
        alerts: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            next_url: str | None = url
            while next_url:
                response = await client.get(
                    next_url, headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                data = response.json()
                alerts.extend(data.get("value", []))
                next_url = data.get("nextLink")

        if severity:
            alerts = [
                a
                for a in alerts
                if a.get("properties", {}).get("severity", "").lower() == severity.lower()
            ]
        log.info("defender.get_security_alerts.done", count=len(alerts))
        return alerts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_agent_health(self, server_id: str) -> dict[str, Any]:
        """Check Defender for Endpoint agent health via MDE device API."""
        machine_name = server_id.split("/")[-1]
        log.info("defender.get_agent_health", machine=machine_name)
        url = (
            f"{_MDE_BASE}/api/machines"
            f"?$filter=computerDnsName eq '{machine_name}'"
        )
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, self._mde_token)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
            devices = data.get("value", [])
            if not devices:
                log.warning("defender.get_agent_health.not_found", machine=machine_name)
                return {"onboarded": False, "machine": machine_name}
            device = devices[0]
            log.info(
                "defender.get_agent_health.done",
                machine=machine_name,
                health=device.get("healthStatus"),
            )
            return {
                "onboarded": True,
                "machine": machine_name,
                "health_status": device.get("healthStatus"),
                "onboarding_status": device.get("onboardingStatus"),
                "last_seen": device.get("lastSeen"),
                "agent_version": device.get("agentVersion"),
                "os_platform": device.get("osPlatform"),
            }
