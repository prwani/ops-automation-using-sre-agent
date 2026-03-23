"""Health check timer-triggered Azure Function — runs 4×/day."""

import logging
import os
import sys

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential
from azure.monitor.query import LogsQueryClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.adapters.factory import get_arc_adapter
from src.health_checks.engine import HealthCheckEngine

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 6,12,18,0 * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def health_check(timer: func.TimerRequest) -> None:
    """Run health checks on all Arc-enrolled servers."""
    logging.info("Health check function triggered")

    credential = ManagedIdentityCredential()
    arc_adapter = get_arc_adapter()

    cosmos_client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )
    logs_client = LogsQueryClient(credential=credential)

    engine = HealthCheckEngine(
        arc_adapter=arc_adapter,
        log_analytics_client=logs_client,
        cosmos_client=cosmos_client,
    )

    import asyncio
    results = asyncio.run(engine.run_all_servers())
    logging.info("Health check complete. Servers checked: %d", len(results))
