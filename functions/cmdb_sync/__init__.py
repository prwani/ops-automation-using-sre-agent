"""CMDB sync timer-triggered Azure Function — runs on the 1st of each month."""

import logging
import os
import sys

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.adapters.factory import get_arc_adapter, get_cmdb_adapter, get_itsm_adapter
from src.cmdb.reconciler import CmdbReconciler

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 8 1 * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def cmdb_sync(timer: func.TimerRequest) -> None:
    """Reconcile Azure Arc inventory with CMDB."""
    logging.info("CMDB sync function triggered")

    credential = ManagedIdentityCredential()
    cosmos_client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )

    reconciler = CmdbReconciler(
        arc_adapter=get_arc_adapter(),
        cmdb_adapter=get_cmdb_adapter(),
        itsm_adapter=get_itsm_adapter(),
        cosmos_client=cosmos_client,
    )

    import asyncio
    result = asyncio.run(reconciler.run_reconciliation())
    logging.info(
        "CMDB sync complete. Discrepancies: %d (Arc servers: %d, CMDB records: %d)",
        result.get("discrepancy_count", 0),
        result.get("arc_server_count", 0),
        result.get("cmdb_record_count", 0),
    )
