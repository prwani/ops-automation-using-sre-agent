---
name: ticket-driven-remediation
description: Reads open GLPI tickets under Wintel Ops category, classifies each ticket by type (CMDB, health, security, compliance, patching), performs the appropriate investigation using Azure Arc and Defender for Cloud, updates the ticket with findings, and marks it solved.
---

# Ticket-Driven Remediation

Read open ITSM tickets, investigate each one, take action, and close the loop. This skill demonstrates AI-driven triage — the agent reads a ticket written in natural language, decides what investigation is needed, executes it, and writes back the results.

Execute these steps IN ORDER. Do not skip steps.

## Prerequisites

Before starting, ask the user for GLPI connection details if not already known:

- **GLPI_URL** — e.g. `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`
- **GLPI_USERNAME** — default `glpi`
- **GLPI_PASSWORD** — admin password (default `glpi`)
- *(Optional)* **GLPI_CLIENT_ID** and **GLPI_CLIENT_SECRET** — for OAuth2 auth

If the user provides the URL and credentials in their prompt, use those directly. Otherwise, ask once and reuse for all subsequent calls.

## Step 1 — Authenticate to GLPI

Try **OAuth2** first. If it fails (HTTP 500 or connection error), fall back to the **legacy REST API**.

### Option A: OAuth2 (preferred)

```shell
curl.exe -s -X POST -d "grant_type=password&client_id=CLIENT_ID&client_secret=CLIENT_SECRET&username=USERNAME&password=PASSWORD&scope=api" "GLPI_URL/api.php/token"
```

If successful, the response contains `access_token`. Use `Authorization: Bearer TOKEN` for all subsequent calls. The ticket endpoint is `GLPI_URL/api.php/v2.2/Assistance/Ticket`.

### Option B: Legacy REST API (fallback)

If OAuth2 fails or no client_id/secret were provided, use HTTP Basic auth. Encode `username:password` as Base64 (e.g. `glpi:glpi` → `Z2xwaTpnbHBp`):

```shell
curl.exe -s -H "Content-Type: application/json" -H "Authorization: Basic BASE64_CREDENTIALS" "GLPI_URL/apirest.php/initSession"
```

Extract the `session_token` from the JSON response. Use `Session-Token: TOKEN` for all subsequent calls. The ticket endpoint is `GLPI_URL/apirest.php/Ticket`.

If **both** methods fail, report the error and stop.

## Step 2 — List open tickets

Retrieve all tickets from GLPI. Use the endpoint matching your auth method:

**OAuth2:**
```shell
curl.exe -s -H "Authorization: Bearer TOKEN" "GLPI_URL/api.php/v2.2/Assistance/Ticket"
```

**Legacy API:**
```shell
curl.exe -s -H "Session-Token: TOKEN" -H "Content-Type: application/json" "GLPI_URL/apirest.php/Ticket"
```

From the response, select tickets where `status` is 1 (New) or 2 (Assigned/Processing). If the user asked to process tickets from a specific category, filter by `itilcategories_id`.

If no open tickets are found, report that and stop.

Present the open tickets as a table:

| # | ID | Title | Priority | Status | Created |
|---|----|-------|----------|--------|---------|

## Step 3 — Classify each ticket

For each open ticket, read the `name` (title) and `content` (description) fields to determine the type of investigation needed. Use these classification rules:

| Keywords in title/content | Classification | Action |
|---------------------------|---------------|--------|
| "CMDB", "stale", "mismatch", "update inventory", "wrong OS", "configuration item" | **CMDB Update** | Compare Azure Arc truth vs GLPI CMDB record |
| "CPU", "memory", "disk", "health check", "performance", "high utilization", "unresponsive" | **Health Investigation** | Query Log Analytics metrics, run diagnostics |
| "MDE", "Defender", "security agent", "endpoint protection", "antivirus", "extension" | **Security Agent Check** | Verify Defender extensions and heartbeat |
| "compliance", "MCSB", "CIS", "NIST", "policy", "regulatory", "audit" | **Compliance Review** | Query Defender for Cloud and Azure Policy |
| "patch", "update", "KB", "missing update", "WSUS", "reboot pending" | **Patch Assessment** | Query Update Manager for missing patches |

If a ticket matches multiple categories, pick the primary one based on the title. If no keywords match, classify as **General** and report the ticket for manual review.

## Step 4 — Execute investigation per ticket type

Process each classified ticket. For all ticket types, first discover the Arc servers:

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | project name, resourceGroup, subscriptionId, status=tostring(properties.status), os=tostring(properties.osName), location, osVersion=tostring(properties.osProfile.windowsConfiguration.osVersion) | order by name" --first 1000 -o json
```

Then execute the investigation based on classification:

---

### 4a — CMDB Update

The ticket mentions a server with stale or incorrect CMDB data. The agent should:

1. **Extract the server name** from the ticket title/content.

2. **Get the current truth from Azure Arc** — the Resource Graph query above gives OS, version, location, status.

3. **Query GLPI CMDB** for the same server:

**OAuth2:**
```shell
curl.exe -s -H "Authorization: Bearer TOKEN" "GLPI_URL/api.php/v2.2/Assets/Computer"
```

**Legacy API:**
```shell
curl.exe -s -H "Session-Token: TOKEN" -H "Content-Type: application/json" "GLPI_URL/apirest.php/Computer"
```

Find the matching computer record by name. Compare the Azure Arc data with the GLPI record.

4. **Identify discrepancies** — report what differs (OS name, OS version, status, serial, comment).

5. **Update the GLPI record** with corrected data:

**OAuth2:**
```shell
curl.exe -s -X PATCH -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d "{\"comment\": \"UPDATED_COMMENT\"}" "GLPI_URL/api.php/v2.2/Assets/Computer/COMPUTER_ID"
```

**Legacy API:**
```shell
curl.exe -s -X PUT -H "Session-Token: TOKEN" -H "Content-Type: application/json" -d "{\"input\": {\"comment\": \"UPDATED_COMMENT\"}}" "GLPI_URL/apirest.php/Computer/COMPUTER_ID"
```

Replace `COMPUTER_ID` with the GLPI computer ID and `UPDATED_COMMENT` with the corrected information from Azure Arc (e.g., actual OS version, last connected timestamp, resource group).

6. **Record the findings** for Step 5 — note what was stale, what was corrected, and the new values.

---

### 4b — Health Investigation

The ticket reports a performance or health issue on a specific server. The agent should:

1. **Extract the server name** from the ticket.

2. **Discover the Log Analytics workspace**:

```shell
az graph query -q "Resources | where type == 'microsoft.operationalinsights/workspaces' | project name, resourceGroup, subscriptionId, workspaceId=tostring(properties.customerId)" --first 100 -o json
```

3. **Query CPU, Memory, Disk** from Log Analytics for the specific server (replace WORKSPACE_ID and SERVER_NAME):

```shell
az monitor log-analytics query --workspace WORKSPACE_ID --analytics-query "Perf | where TimeGenerated > ago(1h) | where Computer in~ ('SERVER_NAME') | where (ObjectName in ('Processor', 'Processor Information') and CounterName == '% Processor Time' and InstanceName == '_Total') or (ObjectName == 'Memory' and CounterName in ('% Committed Bytes In Use', '% Used Memory')) or (ObjectName in ('LogicalDisk', 'Logical Disk') and CounterName in ('% Free Space', '% Used Space') and InstanceName in ('C:', '/')) | summarize AvgValue=round(avg(CounterValue),1), MaxValue=round(max(CounterValue),1) by Computer, ObjectName, CounterName" -o table
```

4. **Evaluate thresholds**: CPU avg >85% = CRITICAL, >75% = WARNING. Memory avg >85% = CRITICAL. Disk Free <10% = CRITICAL.

5. **Record the findings** — metrics, thresholds hit, overall status.

---

### 4c — Security Agent Check

The ticket asks about Defender/MDE status. The agent should:

1. **Check Defender extensions** on all Arc servers (or the specific server mentioned):

```shell
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines/extensions' | where name in~ ('MDE.Linux', 'MDE.Windows', 'MicrosoftMonitoringAgent', 'AzureMonitorWindowsAgent', 'AzureMonitorLinuxAgent') | extend machineName = tostring(split(id, '/')[8]) | project machineName, extensionName=name, status=tostring(properties.provisioningState), type=tostring(properties.type) | order by machineName" --first 1000 -o table
```

2. **Record the findings** — which servers have MDE installed, provisioning state, any missing extensions.

---

### 4d — Compliance Review

The ticket asks for a compliance posture check. The agent should:

1. **Query Defender for Cloud**:

```shell
az security regulatory-compliance-standards list --query "[].{Standard:name, State:state, PassedControls:passedControls, FailedControls:failedControls}" -o table
```

2. **For standards with failures**, drill into the failing controls:

```shell
az security regulatory-compliance-controls list --standard-name STANDARD_NAME --query "[?state=='Failed'].{Control:name, FailedAssessments:failedAssessments}" -o table
```

3. **Record the findings** — compliance percentage, top failing controls, priority.

---

### 4e — Patch Assessment

The ticket asks about missing patches. The agent should:

1. **Query Resource Graph for patch data**:

```shell
az graph query -q "patchassessmentresources | where type =~ 'microsoft.hybridcompute/machines/patchassessmentresults/softwarepatches' | extend machineName = tostring(split(id, '/')[8]), classification = tostring(properties.classifications[0]), patchName = tostring(properties.patchName) | summarize patchCount=count() by machineName, classification | order by machineName, classification" --first 1000 -o table
```

2. **Record the findings** — patch counts by classification per server.

---

## Step 5 — Update each ticket with findings

For each ticket processed, add the investigation findings as a **followup** on the ticket:

**OAuth2:**
```shell
curl.exe -s -X POST -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d "{\"content\": \"FINDINGS_TEXT\"}" "GLPI_URL/api.php/v2.2/Assistance/Ticket/TICKET_ID/ITILFollowup"
```

**Legacy API:**
```shell
curl.exe -s -X POST -H "Session-Token: TOKEN" -H "Content-Type: application/json" -d "{\"input\": {\"itemtype\": \"Ticket\", \"items_id\": TICKET_ID, \"content\": \"FINDINGS_TEXT\"}}" "GLPI_URL/apirest.php/ITILFollowup"
```

Replace `TICKET_ID` with the GLPI ticket ID and `FINDINGS_TEXT` with a structured summary of the investigation. Use HTML formatting in the content for readability:

```
<p><b>Investigation by SRE Agent</b></p>
<p><b>Classification:</b> CMDB Update / Health Check / Security / Compliance / Patch</p>
<p><b>Findings:</b></p>
<ul>
<li>Finding 1...</li>
<li>Finding 2...</li>
</ul>
<p><b>Action Taken:</b> Describe what was done (e.g., CMDB record updated, metrics collected)</p>
<p><b>Recommendation:</b> Next steps if any</p>
```

## Step 6 — Mark resolved tickets as Solved

If the investigation resolved the issue (e.g., CMDB was updated, no critical findings), change the ticket status to Solved (status=5):

**OAuth2:**
```shell
curl.exe -s -X PATCH -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d "{\"status\": 5}" "GLPI_URL/api.php/v2.2/Assistance/Ticket/TICKET_ID"
```

**Legacy API:**
```shell
curl.exe -s -X PUT -H "Session-Token: TOKEN" -H "Content-Type: application/json" -d "{\"input\": {\"status\": 5}}" "GLPI_URL/apirest.php/Ticket/TICKET_ID"
```

Do NOT auto-solve tickets where:
- Critical findings were identified that need human action
- The investigation was inconclusive
- The ticket type was General/Unknown

For those, leave the ticket open and add the followup only.

## Step 7 — Summary

Present a summary table of all tickets processed:

| Ticket ID | Title | Classification | Action Taken | Result | New Status |
|-----------|-------|---------------|-------------|--------|------------|
| 1 | CMDB stale: ArcBox-Win2K25 | CMDB Update | Updated OS version in GLPI | ✅ Corrected | Solved |
| 2 | High CPU on ArcBox-Win2K22 | Health Check | Queried metrics — CPU 45% avg | ℹ️ Normal | Solved |
| 3 | Verify MDE on Linux servers | Security Agent | All extensions installed | ✅ Healthy | Solved |

Report:
- Total tickets processed
- Tickets auto-resolved
- Tickets left open for manual review
- Time taken
