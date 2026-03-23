"""Runs router — GET /api/runs and GET /api/runs/{run_id}."""

from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, Query
from ..auth import require_role
from ..cosmos_client import get_cosmos_client
from ..config import settings

router = APIRouter(tags=["runs"])


@router.get("/runs")
async def list_runs(
    task_type: str | None = Query(None),
    status: str | None = Query(None),
    run_date: date | None = Query(None, alias="date"),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_role("Viewer")),
) -> list[dict[str, Any]]:
    """List automation runs with optional filters."""
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("runs")

    conditions = ["SELECT * FROM c WHERE 1=1"]
    parameters: list[dict] = []
    if task_type:
        conditions.append("AND c.taskType = @taskType")
        parameters.append({"name": "@taskType", "value": task_type})
    if status:
        conditions.append("AND c.status = @status")
        parameters.append({"name": "@status", "value": status})
    if run_date:
        conditions.append("AND c.partitionKey = @partitionKey")
        parameters.append({"name": "@partitionKey", "value": run_date.isoformat()})
    query = " ".join(conditions) + f" ORDER BY c._ts DESC OFFSET 0 LIMIT {limit}"

    return [item async for item in container.query_items(query=query, parameters=parameters)]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: dict = Depends(require_role("Viewer")),
) -> dict[str, Any]:
    """Get a specific run by ID."""
    from fastapi import HTTPException
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("runs")
    query = "SELECT * FROM c WHERE c.id = @id"
    items = [item async for item in container.query_items(
        query=query, parameters=[{"name": "@id", "value": run_id}]
    )]
    if not items:
        raise HTTPException(status_code=404, detail="Run not found")
    return items[0]
