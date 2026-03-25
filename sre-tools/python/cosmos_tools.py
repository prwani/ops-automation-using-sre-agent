"""Cosmos DB tools for SRE Agent — each function follows the SRE Agent Python tool pattern.

SRE Agent Python tools require:
- A main() function with typed parameters
- JSON-serializable return values
- No persistent state between calls

Create each function as a SEPARATE Python tool in Builder > Tools > Python.
Enable Azure Identity in the Identity tab when creating each tool.
"""

# ============================================================
# Tool 1: cosmos-query-runs
# Description: Query automation run history from Cosmos DB
# Identity: Enable ARM scope (for managed identity auth)
# ============================================================


def main(date: str = "", task_type: str = "", status: str = "") -> dict:
    """Query automation run history from Cosmos DB.

    Args:
        date: Filter by date (YYYY-MM-DD format, e.g. "2026-03-25"). Empty = all dates.
        task_type: Filter by task type (e.g. "health_check", "compliance", "alert"). Empty = all.
        status: Filter by status (e.g. "completed", "failed", "completed_with_warnings"). Empty = all.
    """
    from azure.cosmos import CosmosClient
    from azure.identity import ManagedIdentityCredential

    COSMOS_ENDPOINT = "https://cosmos-opsauto-dev-sc.documents.azure.com:443/"
    DATABASE = "ops-automation"

    credential = ManagedIdentityCredential()
    client = CosmosClient(url=COSMOS_ENDPOINT, credential=credential)
    db = client.get_database_client(DATABASE)
    container = db.get_container_client("runs")

    conditions = ["SELECT TOP 20 * FROM c WHERE 1=1"]
    params = []
    if date:
        conditions.append("AND c.partitionKey = @date")
        params.append({"name": "@date", "value": date})
    if task_type:
        conditions.append("AND c.taskType = @taskType")
        params.append({"name": "@taskType", "value": task_type})
    if status:
        conditions.append("AND c.status = @status")
        params.append({"name": "@status", "value": status})

    query = " ".join(conditions) + " ORDER BY c._ts DESC"

    items = list(container.query_items(
        query=query, parameters=params, enable_cross_partition_query=True
    ))

    return {
        "count": len(items),
        "runs": [
            {
                "id": item.get("id"),
                "taskType": item.get("taskType"),
                "status": item.get("status"),
                "summary": item.get("summary", ""),
                "startedAt": item.get("startedAt"),
                "durationSeconds": item.get("durationSeconds"),
            }
            for item in items
        ],
    }


# ============================================================
# Tool 2: cosmos-check-memories
# Description: Check active memory/suppression rules for a server
# Identity: Enable ARM scope (for managed identity auth)
# ============================================================


def main(server_name: str, task_type: str = "") -> dict:
    """Check active memory/suppression rules for a server.

    Args:
        server_name: Server hostname (e.g. "ArcBox-Win2K22")
        task_type: Optional task type filter (e.g. "health_check"). Empty = all tasks.
    """
    from datetime import datetime, timezone
    from azure.cosmos import CosmosClient
    from azure.identity import ManagedIdentityCredential

    COSMOS_ENDPOINT = "https://cosmos-opsauto-dev-sc.documents.azure.com:443/"
    DATABASE = "ops-automation"

    credential = ManagedIdentityCredential()
    client = CosmosClient(url=COSMOS_ENDPOINT, credential=credential)
    db = client.get_database_client(DATABASE)
    container = db.get_container_client("memories")

    now = datetime.now(timezone.utc).isoformat()
    query = """
        SELECT * FROM c
        WHERE c.status = 'active'
        AND c.expiresAt > @now
        AND (c.scope.serverFilter = @server OR c.scope.serverFilter = '*')
    """
    params = [
        {"name": "@now", "value": now},
        {"name": "@server", "value": server_name},
    ]
    if task_type:
        query += " AND c.scope.taskType = @taskType"
        params.append({"name": "@taskType", "value": task_type})

    items = list(container.query_items(
        query=query, parameters=params, enable_cross_partition_query=True
    ))

    return {
        "server": server_name,
        "active_memories": len(items),
        "memories": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "instruction": item.get("instruction"),
                "expiresAt": item.get("expiresAt"),
                "scope": item.get("scope"),
            }
            for item in items
        ],
    }
