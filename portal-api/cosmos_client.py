"""Cosmos DB client — shared async client for all routers."""

from __future__ import annotations
import logging
from config import settings

logger = logging.getLogger(__name__)

_client = None


def get_cosmos_client():
    """Return a CosmosClient instance, or None when Cosmos is not configured."""
    global _client
    if _client is not None:
        return _client
    if not settings.cosmos_endpoint:
        logger.warning("COSMOS_ENDPOINT is not set — Cosmos DB is unavailable.")
        return None
    try:
        from azure.cosmos.aio import CosmosClient
        from azure.identity.aio import DefaultAzureCredential
        credential = DefaultAzureCredential()
        _client = CosmosClient(url=settings.cosmos_endpoint, credential=credential)
    except Exception:
        logger.exception("Failed to create Cosmos DB client")
        return None
    return _client
