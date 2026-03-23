"""Cosmos DB tools for SRE Agent — run history and memory queries."""

import os
from datetime import datetime, timezone
from typing import Any

import structlog
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

log = structlog.get_logger()


class CosmosTools:
    """Cosmos DB query tools for SRE Agent."""

    def __init__(self) -> None:
        self.endpoint = os.environ["COSMOS_ENDPOINT"]
        self.database = os.environ.get("COSMOS_DATABASE", "ops-automation")

    async def _get_client(self) -> CosmosClient:
        credential = DefaultAzureCredential()
        return CosmosClient(url=self.endpoint, credential=credential)

    async def query_runs(
        self,
        task_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query automation run history from Cosmos DB."""
        conditions = ["SELECT * FROM c WHERE 1=1"]
        if task_type:
            conditions.append(f"AND c.taskType = '{task_type}'")
        if status:
            conditions.append(f"AND c.status = '{status}'")
        query = " ".join(conditions) + f" ORDER BY c._ts DESC OFFSET 0 LIMIT {limit}"

        async with await self._get_client() as client:
            db = client.get_database_client(self.database)
            container = db.get_container_client("runs")
            items = [item async for item in container.query_items(query=query)]
            log.info("cosmos_runs_queried", count=len(items), task_type=task_type)
            return items

    async def check_memories(
        self,
        server_id: str,
        check_type: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Check for active memory/suppression rules for a server."""
        now = datetime.now(timezone.utc).isoformat()
        query = f"""
            SELECT * FROM c 
            WHERE c.status = 'active'
            AND c.expiresAt > '{now}'
            AND (c.scope.serverFilter = '{server_id}' OR c.scope.serverFilter = '*')
        """
        if check_type:
            query += f" AND (c.scope.checkFilter = '{check_type}' OR c.scope.checkFilter = '*')"

        async with await self._get_client() as client:
            db = client.get_database_client(self.database)
            container = db.get_container_client("memories")
            items = [item async for item in container.query_items(query=query)]
            log.info("cosmos_memories_checked", server_id=server_id, count=len(items))
            return items
