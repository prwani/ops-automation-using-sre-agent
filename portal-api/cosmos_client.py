"""Cosmos DB client — shared async client for all routers."""

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from .config import settings

_client: CosmosClient | None = None


def get_cosmos_client() -> CosmosClient:
    global _client
    if _client is None:
        credential = DefaultAzureCredential()
        _client = CosmosClient(url=settings.cosmos_endpoint, credential=credential)
    return _client
