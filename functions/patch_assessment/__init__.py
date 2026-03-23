"""Patch assessment timer-triggered Azure Function — runs monthly on the 15th."""

import logging
import os
import sys
from typing import Any

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.adapters.factory import get_arc_adapter, get_itsm_adapter, get_patch_adapter
from src.patching.orchestrator import PatchOrchestrator


@func.timer_trigger(
    schedule="0 0 10 15 * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def patch_assessment(timer: func.TimerRequest) -> None:
    """Run monthly patch assessment for all Arc-enrolled servers."""
    logging.info("Patch assessment function triggered")

    credential = ManagedIdentityCredential()
    cosmos_client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=credential,
    )

    arc_adapter = get_arc_adapter()
    orchestrator = PatchOrchestrator(
        patch_adapter=get_patch_adapter(),
        arc_adapter=arc_adapter,
        itsm_adapter=get_itsm_adapter(),
        cosmos_client=cosmos_client,
    )

    import asyncio

    async def _run() -> dict[str, Any]:
        servers = await arc_adapter.list_servers()
        server_ids = [s.server_id for s in servers]
        return await orchestrator.run_monthly_assessment(server_ids=server_ids)

    result = asyncio.run(_run())
    logging.info(
        "Patch assessment complete. Servers assessed: %d, Total missing patches: %d",
        result.get("servers_assessed", 0),
        result.get("total_missing_patches", 0),
    )
