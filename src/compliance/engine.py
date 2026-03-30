"""Compliance engine — collects Defender for Cloud data and generates daily report."""

from datetime import datetime, timezone
from typing import Any

import structlog

from src.adapters.base import DefenderAdapterBase

log = structlog.get_logger(__name__)

_FRAMEWORKS = [
    "CIS Windows Server 2022",
    "NIST SP 800-53 R5",
    "ISO 27001",
]


class ComplianceEngine:
    """Generates daily compliance reports from Defender for Cloud data."""

    def __init__(
        self,
        defender_adapter: DefenderAdapterBase,
    ) -> None:
        self._defender = defender_adapter

    async def run_daily_report(self, subscription_id: str) -> dict[str, Any]:
        """Collect compliance data and build the full daily report document."""
        log.info("compliance.run_daily_report", subscription_id=subscription_id)
        now = datetime.now(timezone.utc)

        secure_score = await self._defender.get_secure_score(subscription_id)

        framework_results: dict[str, list[dict[str, Any]]] = {}
        for framework in _FRAMEWORKS:
            try:
                controls = await self._defender.get_compliance_results(subscription_id, framework)
                framework_results[framework] = controls
            except Exception as exc:
                log.warning("compliance.framework_error", framework=framework, error=str(exc))
                framework_results[framework] = []

        summary = self._build_summary(secure_score, framework_results)
        failing_controls = self.get_failing_controls(framework_results, top_n=10)
        trend = await self.calculate_trend(subscription_id, days=7, current_score=secure_score)

        report: dict[str, Any] = {
            "run_id": f"compliance-{now.strftime('%Y%m%d-%H%M%S')}",
            "subscription_id": subscription_id,
            "timestamp": now.isoformat(),
            "secure_score": secure_score,
            "framework_summary": summary,
            "top_failing_controls": failing_controls,
            "trend_7d": trend,
        }

        log.info("compliance.run_daily_report.done", score=secure_score)
        return report

    def get_compliance_summary(
        self, secure_score: float, framework_results: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Return secure score and per-framework compliance percentage."""
        return self._build_summary(secure_score, framework_results)

    def _build_summary(
        self, secure_score: float, framework_results: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {"secure_score": secure_score, "frameworks": {}}
        for framework, controls in framework_results.items():
            if not controls:
                summary["frameworks"][framework] = {
                    "compliance_pct": None,
                    "passed": 0,
                    "failed": 0,
                    "total": 0,
                }
                continue
            passed = sum(
                1
                for c in controls
                if c.get("properties", {}).get("state", "").lower() == "passed"
            )
            total = len(controls)
            pct = round((passed / total) * 100, 1) if total else 0.0
            summary["frameworks"][framework] = {
                "compliance_pct": pct,
                "passed": passed,
                "failed": total - passed,
                "total": total,
            }
        return summary

    def get_failing_controls(
        self,
        framework_results: dict[str, list[dict[str, Any]]],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Return top N failing controls with server counts, across all frameworks."""
        failing: list[dict[str, Any]] = []
        for framework, controls in framework_results.items():
            for control in controls:
                props = control.get("properties", {})
                if props.get("state", "").lower() != "passed":
                    failing.append(
                        {
                            "framework": framework,
                            "control_id": control.get("name", ""),
                            "control_name": props.get("displayName", ""),
                            "failed_resources": props.get("failedResources", 0),
                            "state": props.get("state", ""),
                        }
                    )
        failing.sort(key=lambda x: x["failed_resources"], reverse=True)
        return failing[:top_n]

    async def calculate_trend(self, subscription_id: str, days: int = 7, current_score: float | None = None) -> dict[str, Any]:
        """Return trend stub — historical comparison requires previous report data."""
        log.info("compliance.calculate_trend", days=days)
        return {"days": days, "baseline_score": None, "delta": None}
