"""Compliance report timer-triggered Azure Function — runs daily at 07:00 UTC."""

import logging
import os
import sys

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.adapters.factory import get_defender_adapter
from src.compliance.engine import ComplianceEngine

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 7 * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def compliance_report(timer: func.TimerRequest) -> None:
    """Generate daily compliance report from Defender for Cloud."""
    logging.info("Compliance report function triggered")

    try:
        credential = ManagedIdentityCredential()
        cosmos_client = CosmosClient(
            url=os.environ["COSMOS_ENDPOINT"],
            credential=credential,
        )

        engine = ComplianceEngine(
            defender_adapter=get_defender_adapter(),
            cosmos_client=cosmos_client,
            cosmos_database=os.environ.get("COSMOS_DATABASE", "ops-automation"),
        )

        import asyncio
        report = asyncio.run(engine.run_daily_report(subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"]))
        logging.info("Compliance report complete. Secure score: %.1f", report.get("secure_score", 0))
    except Exception:
        logging.exception("Compliance report function failed")
