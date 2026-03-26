# GLPI First-Time Setup

Step-by-step guide to configure the GLPI instance used by the ops-automation demo
environment. GLPI provides both **ITSM** (ticket management) and **CMDB**
(configuration items) through a single deployment with a full REST API.

**GLPI URL:** `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

---

## 1. Complete the First-Time Setup Wizard

1. Open your browser and navigate to:
   ```
   http://glpi-opsauto-demo.swedencentral.azurecontainer.io
   ```
2. Select your language and click **OK**.
3. Accept the licence agreement.
4. Click **Install** (not Upgrade).
5. The wizard checks PHP extensions and directory permissions — all should pass on the
   pre-built container. Click **Continue**.
6. Enter the database connection details (these are pre-configured in the container):

   > **Important:** Use `127.0.0.1` (NOT `localhost`) as the SQL server address. The `localhost` hostname attempts a Unix socket connection which does not exist in the ACI container environment.

   - **SQL server:** `127.0.0.1`
   - **SQL user:** `glpi`
   - **SQL password:** `glpi`
7. Select the **glpi** database and click **Continue**.
8. Wait for the schema initialisation to complete, then click **Use GLPI**.
9. Log in with the default administrator credentials:
   - **Username:** `glpi`
   - **Password:** `glpi`

---

## 2. Change the Admin Password

> **Important:** Change the default password immediately — even in a demo environment.

1. Click the **user icon** (top-right) → **My settings**.
2. In the **Password** field enter a new password and confirm it.
3. Click **Save**.

---

## 3. Enable the REST API

1. Navigate to **Setup → General**.
2. Select the **API** tab.
3. Set **Enable API** to **Yes**.
4. Set **Enable Legacy REST API** to **Yes** (needed for legacy endpoints used by some tools).
5. Click **Save**.

---

## 4. Create an OAuth Client (GLPI 11 uses OAuth2)

GLPI 11 uses **OAuth2** for API authentication (replacing the old App-Token/User-Token approach).

1. Navigate to **Setup → OAuth Clients**.
2. Click **+ Add**.
3. Fill in:
   - **Name:** `ops-automation`
   - **Active:** Yes
   - **Grants:** check **Password** (for automated scripts)
   - **Scopes:** check **api** (required for all API operations)
4. Click **Add**.
5. Copy the generated **Client ID** and **Client Secret** — store them securely.

---

## 5. Test the API (OAuth2 Password Grant)

### Step 1: Get an access token

```bash
curl -s -X POST \
  -d "grant_type=password" \
  -d "client_id=<client_id>" \
  -d "client_secret=<client_secret>" \
  -d "username=glpi" \
  -d "password=<your_admin_password>" \
  -d "scope=api" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token"
```

Expected response:

```json
{
  "token_type": "Bearer",
  "expires_in": 3600,
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGci..."
}
```

### Step 2: Use the token for API calls

```bash
# List computers (CMDB)
curl -s \
  -H "Authorization: Bearer <access_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2.2/Assets/Computer" \
  | python -m json.tool

# Create a ticket
curl -s -X POST \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test ticket", "content": "Testing API", "type": 1}' \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2.2/Assistance/Ticket"
```

> **Note:** GLPI 11 has two API versions:
> - **New API (v2):** `http://.../api.php/v2/` — uses OAuth2 Bearer tokens
> - **Legacy API:** `http://.../apirest.php/` — uses App-Token + Session-Token (still works if legacy API is enabled)

### Legacy API (Alternative)

If tools require the legacy App-Token/User-Token flow:

1. Navigate to your user settings → look for **Remote access keys** → **API token** → Regenerate
2. The legacy `initSession` endpoint still works:

```bash
curl -s \
  -H "Authorization: user_token <user_api_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

---

## 6. Seed the CMDB with ArcBox Servers

The demo scenarios (especially [Scenario F — CMDB Sync](demos/scenario-f-cmdb-sync.md))
require GLPI's CMDB to contain computer records for the ArcBox environment. Some
entries are **deliberately stale** so the sync demo can detect and fix discrepancies.

### Option A: Manual Entry via the UI

1. Navigate to **Assets → Computers**.
2. Click **+ Add**.
3. Create the following entries:

| Name | Serial Number | OS | Comment |
|------|---------------|----|---------|
| `ArcBox-Win2K22` | `YOURSERIAL-WIN2K22` | Windows Server 2022 | Application server |
| `ArcBox-Win2K25` | `YOURSERIAL-WIN2K25` | Windows Server 2022 *(deliberately wrong — should be 2025)* | File server — stale OS version for CMDB sync demo |
| `ArcBox-SQL` | `YOURSERIAL-SQL` | Windows Server 2022 | Database server — SQL Server 2022 |

> **Why the stale data?** `ArcBox-Win2K25` is intentionally recorded as Windows
> Server 2022 instead of 2025. When you run Scenario F, the CMDB sync function detects
> the mismatch against Azure Resource Graph and corrects it.

### Option B: Programmatic Seeding via the API (OAuth2)

First, get an access token:

```bash
TOKEN=$(curl -s -X POST \
  -d "grant_type=password" \
  -d "client_id=<client_id>" \
  -d "client_secret=<client_secret>" \
  -d "username=glpi" \
  -d "password=<your_admin_password>" \
  -d "scope=api" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Then create each computer:

```bash
API="http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2"

# ArcBox-Win2K22 — Application Server
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "ArcBox-Win2K22", "serial": "YOURSERIAL-WIN2K22", "comment": "Application server - Windows Server 2022"}' \
  "$API/Computer"

# ArcBox-Win2K25 — File Server (deliberately stale OS for CMDB sync demo)
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "ArcBox-Win2K25", "serial": "YOURSERIAL-WIN2K25", "comment": "File server - Windows Server 2022 (DELIBERATELY STALE - actual OS is 2025)"}' \
  "$API/Computer"

# ArcBox-SQL — Database Server
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "ArcBox-SQL", "serial": "YOURSERIAL-SQL", "comment": "Database server - Windows Server 2022 + SQL Server 2022"}' \
  "$API/Computer"
```

Verify:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$API/Computer" | python -m json.tool
```

---

## 7. Create Ticket Categories for Wintel Ops

Ticket categories ensure that automated ticket creation (Scenarios A, B, C) routes
incidents to the correct queues.

### Option A: Manual Entry via the UI

1. Navigate to **Setup → Dropdowns**.
2. Under **ITIL**, click **Categories**.
3. Click **+ Add** and create the following categories:

| Category Name | As child of | Comment |
|---------------|------------|---------|
| `Wintel Ops` | *(root)* | Parent category for all Wintel operations |
| `Health Check` | `Wintel Ops` | Daily health check alerts and reports |
| `Security` | `Wintel Ops` | Security agent issues (Defender for Cloud) |
| `Compliance` | `Wintel Ops` | Compliance deviations and audit findings |
| `Patching` | `Wintel Ops` | Monthly patching issues and rollback requests |

### Option B: Programmatic Creation via the API (OAuth2)

```bash
# Get token (reuse from Step 6, or get a new one)
TOKEN=$(curl -s -X POST \
  -d "grant_type=password&client_id=<client_id>&client_secret=<client_secret>&username=glpi&password=<password>&scope=api" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/token" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

API="http://glpi-opsauto-demo.swedencentral.azurecontainer.io/api.php/v2"

# Create parent category: Wintel Ops
PARENT_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Wintel Ops", "comment": "Parent category for all Wintel operations"}' \
  "$API/ITILCategory" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create sub-categories under Wintel Ops
for CAT in "Health Check:Daily health check alerts and reports" \
           "Security:Security agent issues (Defender for Cloud)" \
           "Compliance:Compliance deviations and audit findings" \
           "Patching:Monthly patching issues and rollback requests"; do
  NAME="${CAT%%:*}"
  COMMENT="${CAT#*:}"
  curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$NAME\", \"itilcategories_id\": $PARENT_ID, \"comment\": \"$COMMENT\"}" \
    "$API/ITILCategory"
  echo ""
done
```

---

## Quick Reference

| Item | Value |
|------|-------|
| **GLPI URL** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **Default admin** | `glpi` / `glpi` |
| **OAuth2 token endpoint** | `POST /api.php/token` (grant_type=password) |
| **New API (v2)** | `http://.../api.php/v2/` (uses Bearer token) |
| **Legacy API** | `http://.../apirest.php/` (uses App-Token + Session-Token) |
| **API docs (Swagger)** | `http://.../api.php/doc` |
| **Computers (CMDB)** | `GET/POST /api.php/v2.2/Assets/Computer` |
| **Tickets** | `GET/POST /api.php/v2.2/Assistance/Ticket` |
| **Ticket categories** | `GET/POST /api.php/v2.2/Assistance/ITILCategory` |
| **DB host (ACI)** | `127.0.0.1` (NOT `localhost`) |
| **DB credentials** | `glpi` / `GlpiPass2026!` / database `glpidb` |


