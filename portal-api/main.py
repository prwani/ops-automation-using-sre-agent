"""Operations Portal API — FastAPI backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import runs, chat, feedback, memories

app = FastAPI(
    title="Ops Automation Portal API",
    description="Backend for the Wintel Operations Portal",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(memories.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
