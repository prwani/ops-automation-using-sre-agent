"""Alert ingestor timer-triggered Azure Function — runs every 5 minutes."""

import logging
import os
import sys

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.adapters.factory import get_defender_adapter, get_itsm_adapter
from src.alerting.ingestor import AlertIngestor


@func.timer_trigger(
    schedule="0 */5 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=False,
)
def alert_ingestor(timer: func.TimerRequest) -> None:
    """Ingest security alerts from Defender for Cloud and route them."""
    logging.info("Alert ingestor function triggered")

    credential = ManagedIdentityCredential()
    cosmos_client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )

    ingestor = AlertIngestor(
        defender_adapter=get_defender_adapter(),
        itsm_adapter=get_itsm_adapter(),
        cosmos_client=cosmos_client,
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        sre_agent_url=os.environ.get("SRE_AGENT_WEBHOOK_URL", ""),
    )

    import asyncio
    result = asyncio.run(ingestor.ingest_alerts())
    logging.info("Alert ingestor complete. New alerts: %d", result.get("new", 0))
