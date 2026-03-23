"""Memories router — CRUD for /api/memories."""

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import require_role
from cosmos_client import get_cosmos_client
from config import settings

router = APIRouter(tags=["memories"])


class MemoryCreate(BaseModel):
    type: str  # suppression | escalation | knowledge | threshold_override | preference | approval_standing
    instruction: str
    server_filter: str = "*"
    task_type: str | None = None
    check_filter: str | None = None
    duration_days: int = 30


class MemoryUpdate(BaseModel):
    instruction: str | None = None
    status: str | None = None  # active | expired
    duration_days: int | None = None


@router.get("/memories")
async def list_memories(
    status: str = "active",
    user: dict = Depends(require_role("Viewer")),
) -> list[dict[str, Any]]:
    """List memories, optionally filtered by status."""
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("memories")
    user_id = user.get("preferred_username", user.get("oid", "unknown"))

    conditions = ["SELECT * FROM c WHERE c.userId = @userId"]
    parameters: list[dict] = [{"name": "@userId", "value": user_id}]
    if status != "all":
        conditions.append("AND c.status = @status")
        parameters.append({"name": "@status", "value": status})
    query = " ".join(conditions) + " ORDER BY c._ts DESC"
    return [
        item
        async for item in container.query_items(
            query=query,
            parameters=parameters,
            partition_key=user_id,
        )
    ]


@router.post("/memories", status_code=201)
async def create_memory(
    body: MemoryCreate,
    user: dict = Depends(require_role("Operator")),
) -> dict[str, Any]:
    """Create a new memory/instruction."""
    now = datetime.now(timezone.utc)
    user_id = user.get("preferred_username", user.get("oid", "unknown"))
    memory_id = f"mem-{uuid.uuid4().hex[:8]}"
    doc: dict[str, Any] = {
        "id": memory_id,
        "partitionKey": user_id,
        "userId": user_id,
        "type": body.type,
        "scope": {
            "taskType": body.task_type,
            "serverFilter": body.server_filter,
            "checkFilter": body.check_filter,
        },
        "instruction": body.instruction,
        "effectiveFrom": now.isoformat(),
        "expiresAt": (now + timedelta(days=body.duration_days)).isoformat(),
        "status": "active",
        "appliedToRuns": [],
    }
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("memories")
    await container.create_item(body=doc)
    return {"id": memory_id, "status": "active", "expiresAt": doc["expiresAt"]}


@router.put("/memories/{memory_id}")
async def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    user: dict = Depends(require_role("Operator")),
) -> dict[str, Any]:
    """Update a memory instruction or status."""
    user_id = user.get("preferred_username", user.get("oid", "unknown"))
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("memories")
    try:
        doc = await container.read_item(item=memory_id, partition_key=user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Memory not found")
    if body.instruction is not None:
        doc["instruction"] = body.instruction
    if body.status is not None:
        doc["status"] = body.status
    if body.duration_days is not None:
        effective_from = datetime.fromisoformat(doc["effectiveFrom"])
        doc["expiresAt"] = (effective_from + timedelta(days=body.duration_days)).isoformat()
    await container.replace_item(item=doc["id"], body=doc)
    return {"id": memory_id, "status": doc["status"]}


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    user: dict = Depends(require_role("Operator")),
) -> None:
    """Delete a memory. Users can only delete their own memories."""
    user_id = user.get("preferred_username", user.get("oid", "unknown"))
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("memories")
    try:
        await container.delete_item(item=memory_id, partition_key=user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Memory not found")
