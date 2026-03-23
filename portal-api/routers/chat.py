"""Chat router — POST /api/chat with Server-Sent Events streaming."""

import json
from typing import AsyncGenerator
import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from auth import require_role
from config import settings

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    thread_id: str | None = None


async def _stream_foundry_response(
    message: str, thread_id: str | None
) -> AsyncGenerator[str, None]:
    """Stream response from Azure AI Foundry Ops Chat agent."""
    if not settings.foundry_endpoint or not settings.foundry_api_key:
        # Fallback for development: echo response
        yield f"data: {json.dumps({'delta': 'AI chat is not configured. Set FOUNDRY_ENDPOINT and FOUNDRY_API_KEY.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    headers = {
        "api-key": settings.foundry_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [{"role": "user", "content": message}],
        "stream": True,
    }
    if thread_id:
        payload["thread_id"] = thread_id

    url = f"{settings.foundry_endpoint}/openai/agents/{settings.foundry_ops_chat_agent_id}/threads/runs"
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield f"{line}\n\n"


@router.post("/chat")
async def chat(
    body: ChatMessage,
    user: dict = Depends(require_role("Operator")),
) -> StreamingResponse:
    """Stream AI chat response from Ops Chat agent."""
    return StreamingResponse(
        _stream_foundry_response(body.message, body.thread_id),
        media_type="text/event-stream",
    )
