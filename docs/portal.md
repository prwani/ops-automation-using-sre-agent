# Operations Portal

## Overview

A single responsive web application where the Wintel team can view automation run status, browse execution history, chat with AI, provide feedback, and manage persistent memories that shape how automation behaves.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + TypeScript + Fluent UI v2 | Microsoft look & feel, responsive, rich component library |
| Backend API | Python FastAPI | Same language as automation code; shares adapter layer; async support |
| Authentication | Microsoft Entra ID (MSAL.js + JWT) | SSO with corporate identity; role-based access control |
| Database | Azure Cosmos DB (NoSQL, serverless) | JSON-native for flexible run/feedback/memory documents |
| AI Chat | Azure AI Foundry Agent (Ops Chat) | Function-calling for live data queries; memory integration |
| Hosting | Azure App Service | Auto-scale, custom domain, SSL |
| Real-time | Server-Sent Events (SSE) | Stream AI chat responses; stream live run status updates |

## Pages

### 1. Dashboard (Today's Runs)

Shows real-time status of all automated tasks as summary cards with a chronological timeline:

- **Task cards** — Health Checks (✅ 3/4), Compliance (✅ 1/1), Alerts (⚠️ 12 new), Patching (⏳ scheduled), CMDB (⏳ next month), VMware (✅ OK)
- **Run timeline** — Chronological list of today's events with memory annotations and AI insights
- **Quick chat** — Input bar at the bottom to ask about today's runs

### 2. History (Execution History)

Paginated, filterable table of all past runs:

- **Filters** — Date range, task type, status (success/warning/failure), server
- **Columns** — Date, task, status, duration, notes (icons for memory applied, feedback, tickets, AI involvement)
- **Expandable rows** — Click to see full run detail with logs and AI analysis
- **Export** — CSV download for compliance evidence

### 3. Chat (AI Assistant)

Streaming conversational interface powered by the Ops Chat Foundry Agent:

- **Morning brief** — Auto-greeting with today's run summary and top 3 action items
- **Natural-language queries** — "Why did the health check fail on SRV-05?" → agent queries live data via function calling
- **Memory creation** — "Ignore disk warnings on SRV-A for 10 days" → agent extracts structured memory
- **Inline actions** — Buttons to view run details, view disk trends, edit memory duration
- **Chat history** — Persistent across sessions

### 4. Memories (User Instructions)

Manage the accumulated instructions that shape automation behavior:

- **Active memories** — Cards showing type, scope, expiration, affected run count
- **Expired memories** — Collapsible section with reactivate option
- **CRUD actions** — Edit, expire now, reactivate, delete
- **Create new** — Manual memory creation form (type, scope, duration, instruction)

## Cosmos DB Data Model

### Container: `runs`
Partition key: date (e.g., `2026-03-23`)

```json
{
  "id": "run-20260323-hc-0600",
  "partitionKey": "2026-03-23",
  "taskType": "health_check",
  "taskName": "Daily Health Check - 06:00",
  "status": "completed_with_warnings",
  "startedAt": "2026-03-23T06:00:00Z",
  "completedAt": "2026-03-23T06:02:34Z",
  "durationSeconds": 154,
  "triggeredBy": "timer",
  "summary": "5/6 servers healthy. ArcBox-Win2K22: disk at 92%.",
  "servers": [...],
  "aiInsight": "Disk usage on ArcBox-Win2K22 has grown 3% in 7 days...",
  "memoryApplied": [
    {"memoryId": "mem-001", "rule": "Ignore ArcBox-SQL", "effect": "Skipped"}
  ]
}
```

### Container: `feedback`
Partition key: date

```json
{
  "id": "fb-20260323-001",
  "partitionKey": "2026-03-23",
  "runId": "run-20260323-hc-0600",
  "userId": "prafulla@contoso.com",
  "feedbackType": "instruction",
  "message": "Ignore disk warnings on ArcBox-Win2K22 for 10 days.",
  "processedIntoMemory": true,
  "memoryId": "mem-002"
}
```

### Container: `memories`
Partition key: userId

```json
{
  "id": "mem-002",
  "userId": "prafulla@contoso.com",
  "type": "suppression",
  "scope": {
    "taskType": "health_check",
    "serverFilter": "ArcBox-Win2K22",
    "checkFilter": "disk"
  },
  "instruction": "Ignore disk warnings — planned data migration",
  "effectiveFrom": "2026-03-23T07:15:00Z",
  "expiresAt": "2026-04-02T07:15:00Z",
  "status": "active",
  "appliedToRuns": ["run-20260323-hc-1200", "run-20260323-hc-1800"]
}
```

## Memory Types

| Type | Example | Effect |
|---|---|---|
| **Suppression** | "Ignore disk warnings on SRV-A for 10 days" | Skips or downgrades alerts for that server/check |
| **Escalation** | "Always treat SRV-B alerts as P1" | SRE Agent/alert rules raise severity |
| **Knowledge** | "SRV-C batch job spikes CPU every Friday 2 AM" | SRE Agent suppresses CPU alerts during that window |
| **Threshold override** | "CPU warning for DB servers should be 90%" | Health check uses custom threshold |
| **Preference** | "Send compliance reports to alice@contoso.com too" | Report distribution list updated |
| **Approval standing** | "Auto-approve P4 patches for dev servers" | Patch workflow skips approval for matching patches |

## Memory Lifecycle

```
User Feedback → Foundry Agent extracts intent → Memory in Cosmos DB → Applied to next run
                                                    │
                                                    ├── Run record shows which memories applied
                                                    ├── Memories auto-expire
                                                    └── Users can edit/deactivate anytime
```

## Entra Authentication

| Step | Detail |
|---|---|
| 1 | User opens portal → MSAL.js redirects to Entra ID login |
| 2 | User authenticates (SSO if already logged in) |
| 3 | MSAL.js receives tokens with custom roles |
| 4 | Frontend sends access token as Bearer header |
| 5 | FastAPI validates JWT against Entra JWKS endpoint |
| 6 | RBAC middleware checks role: Viewer / Operator / Admin |

## API Endpoints

| Method | Path | Purpose | Auth Role |
|---|---|---|---|
| GET | `/api/runs` | List runs (date, taskType, status filters) | Viewer+ |
| GET | `/api/runs/:id` | Run detail with logs | Viewer+ |
| POST | `/api/chat` | Chat with AI (SSE streaming) | Operator+ |
| POST | `/api/feedback` | Submit feedback on a run | Operator+ |
| GET | `/api/memories` | List active/expired memories | Viewer+ |
| POST | `/api/memories` | Create memory manually | Operator+ |
| PUT | `/api/memories/:id` | Edit memory | Operator+ |
| DELETE | `/api/memories/:id` | Delete memory | Admin |
