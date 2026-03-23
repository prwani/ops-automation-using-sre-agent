"""Feedback router — POST /api/feedback."""

from datetime import date, datetime, timezone
from typing import Any
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import require_role
from cosmos_client import get_cosmos_client
from config import settings

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    run_id: str
    feedback_type: str  # "instruction" | "correction" | "acknowledgement"
    message: str


@router.post("/feedback", status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    user: dict = Depends(require_role("Operator")),
) -> dict[str, Any]:
    """Submit feedback on an automation run."""
    today = date.today().isoformat()
    feedback_id = f"fb-{today.replace('-','')}-{uuid.uuid4().hex[:6]}"
    doc: dict[str, Any] = {
        "id": feedback_id,
        "partitionKey": today,
        "runId": body.run_id,
        "userId": user.get("preferred_username", user.get("oid", "unknown")),
        "feedbackType": body.feedback_type,
        "message": body.message,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "processedIntoMemory": False,
    }
    client = get_cosmos_client()
    db = client.get_database_client(settings.cosmos_database)
    container = db.get_container_client("feedback")
    await container.create_item(body=doc)
    return {"id": feedback_id, "status": "created"}
