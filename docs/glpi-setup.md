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
3. Set **Enable Rest API** to **Yes**.
4. Click **Save**.

---

## 4. Create a User API Token

The user token authenticates API calls as a specific GLPI user.

1. Click the **user icon** (top-right) → **My settings**.
2. Scroll to the **Remote access keys** section.
3. Next to **API token**, click **Regenerate**.
4. Copy the generated token and store it securely. You will use it as `<user_token>`
   in API calls.
5. Click **Save**.

---

## 5. Create an Application (App) Token

App tokens identify the calling application and are required alongside the user token.

1. Navigate to **Setup → General → API**.
2. Under **API clients**, click **Add API client**.
3. Fill in:
   - **Name:** `ops-automation`
   - **Active:** Yes
   - **Filter access:** leave empty (allow all IPs) or restrict to your network
4. Click **Add**.
5. Copy the generated **App-Token** value and store it securely.

---

## 6. Test the API

Verify that both tokens work by initiating a session:

```bash
curl -s \
  -H "App-Token: <app_token>" \
  -H "Authorization: user_token <user_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

Expected response:

```json
{
  "session_token": "abc123def456..."
}
```

If you receive a `session_token`, the API is correctly configured. Use this token in
the `Session-Token` header for subsequent API calls.

To end the session:

```bash
curl -s \
  -H "App-Token: <app_token>" \
  -H "Session-Token: <session_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/killSession"
```

---

## 7. Seed the CMDB with ArcBox Servers

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
> the mismatch against Azure Resource Graph and corrects it — demonstrating the
> reconciliation workflow.

### Option B: Programmatic Seeding via the API

First, initiate a session:

```bash
SESSION=$(curl -s \
  -H "App-Token: <app_token>" \
  -H "Authorization: user_token <user_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession" \
  | python -c "import sys,json; print(json.load(sys.stdin)['session_token'])")
```

Then create each computer:

```bash
# ArcBox-Win2K22 — Application Server
curl -s -X POST \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"input": {"name": "ArcBox-Win2K22", "serial": "YOURSERIAL-WIN2K22", "operatingsystems_id": 1, "comment": "Application server - Windows Server 2022"}}' \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Computer"

# ArcBox-Win2K25 — File Server (deliberately stale OS for CMDB sync demo)
curl -s -X POST \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"input": {"name": "ArcBox-Win2K25", "serial": "YOURSERIAL-WIN2K25", "operatingsystems_id": 1, "comment": "File server - Windows Server 2022 (DELIBERATELY STALE - actual OS is 2025)"}}' \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Computer"

# ArcBox-SQL — Database Server
curl -s -X POST \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"input": {"name": "ArcBox-SQL", "serial": "YOURSERIAL-SQL", "operatingsystems_id": 1, "comment": "Database server - Windows Server 2022 + SQL Server 2022"}}' \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Computer"
```

Verify the records were created:

```bash
curl -s \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Computer?range=0-10" \
  | python -m json.tool
```

End the session when done:

```bash
curl -s \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/killSession"
```

---

## 8. Create Ticket Categories for Wintel Ops

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

### Option B: Programmatic Creation via the API

```bash
# Initiate session (reuse from Step 7, or create a new one)
SESSION=$(curl -s \
  -H "App-Token: <app_token>" \
  -H "Authorization: user_token <user_token>" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession" \
  | python -c "import sys,json; print(json.load(sys.stdin)['session_token'])")

# Create parent category: Wintel Ops
PARENT_ID=$(curl -s -X POST \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"input": {"name": "Wintel Ops", "comment": "Parent category for all Wintel operations"}}' \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/ITILCategory" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create sub-categories under Wintel Ops
for CAT in "Health Check:Daily health check alerts and reports" \
           "Security:Security agent issues (Defender for Cloud)" \
           "Compliance:Compliance deviations and audit findings" \
           "Patching:Monthly patching issues and rollback requests"; do
  NAME="${CAT%%:*}"
  COMMENT="${CAT#*:}"
  curl -s -X POST \
    -H "App-Token: <app_token>" \
    -H "Session-Token: $SESSION" \
    -H "Content-Type: application/json" \
    -d "{\"input\": {\"name\": \"$NAME\", \"itilcategories_id\": $PARENT_ID, \"comment\": \"$COMMENT\"}}" \
    "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/ITILCategory"
  echo ""
done

# End session
curl -s \
  -H "App-Token: <app_token>" \
  -H "Session-Token: $SESSION" \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/killSession"
```

---

## Quick Reference

| Item | Value |
|------|-------|
| **GLPI URL** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |
| **Default admin** | `glpi` / `glpi` |
| **API base** | `http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php` |
| **Init session** | `GET /apirest.php/initSession` |
| **Kill session** | `GET /apirest.php/killSession` |
| **Computers** | `GET/POST /apirest.php/Computer` |
| **Ticket categories** | `GET/POST /apirest.php/ITILCategory` |
| **Tickets** | `GET/POST /apirest.php/Ticket` |
