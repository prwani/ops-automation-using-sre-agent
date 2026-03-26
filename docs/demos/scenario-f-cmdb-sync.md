# Scenario F: CMDB Sync

## Overview

Keep the **GLPI CMDB** in sync with actual Azure infrastructure by comparing **Azure Resource Graph** (source of truth) against GLPI's registered Configuration Items (CIs). This scenario is **100% deterministic automation** — no AI needed.

- **Automation handles ~85%**: Query both sources, diff, auto-update exact matches, flag ambiguous cases
- **AI is not needed**: The logic is purely rule-based — compare, match, update, or flag

## What the team does today

1. Manually log into Azure Portal and GLPI separately
2. Export VM lists to spreadsheets
3. Eyeball differences between the two lists
4. Manually update GLPI records one-by-one
5. Miss discrepancies because the spreadsheets are already stale
6. Audit finds ghost entries in CMDB months later

**Pain points**: Manual comparison is error-prone, always out of date, and nobody enjoys doing it. Audit failures are common.

## Phase 1: Deterministic Automation (~85%)

### What it solves

- Automated inventory comparison between Azure Resource Graph and GLPI CMDB
- Auto-update for exact matches where attributes changed (IP, OS version)
- Flagging of ambiguous cases (disappeared servers, new discoveries)
- Reconciliation reporting for audit compliance

### Step-by-step demo (exact commands)

**Step 1: Query Azure Resource Graph for actual inventory**

```bash
# Get all Arc-enabled machines from Azure Resource Graph
az graph query -q "
  Resources
  | where type == 'microsoft.hybridcompute/machines'
  | project name, resourceGroup, location,
      os = properties.osType,
      osName = properties.osName,
      osVersion = properties.osVersion,
      status = properties.status,
      ip = properties.networkProfile.networkInterfaces[0].ipAddresses[0].address,
      lastSeen = properties.lastStatusChange
  | order by name asc
" --output table
```

Expected output:
```
Name              ResourceGroup  Location  Os       OsName                  Status     IP
────────────────  ─────────────  ────────  ───────  ──────────────────────  ─────────  ──────────────
ArcBox-Client     ArcBox-RG      eastus    Windows  Windows 11 Enterprise  Connected  10.10.1.100
ArcBox-SQL        ArcBox-RG      eastus    Windows  Windows Server 2022    Connected  10.10.1.101
ArcBox-Ubuntu     ArcBox-RG      eastus    Linux    Ubuntu 22.04           Connected  10.10.1.102
ArcBox-Win2K22    ArcBox-RG      eastus    Windows  Windows Server 2022    Connected  10.10.1.103
```

**Step 2: Query GLPI CMDB via API for registered CIs**

```bash
# Initialize GLPI session
SESSION_TOKEN=$(curl -s -X GET \
  "http://glpi.arcbox.local/apirest.php/initSession" \
  -H "Content-Type: application/json" \
  -H "Authorization: user_token YOUR_GLPI_TOKEN" \
  -H "App-Token: YOUR_APP_TOKEN" | jq -r '.session_token')

# Get all computers from GLPI
curl -s -X GET \
  "http://glpi.arcbox.local/apirest.php/Computer" \
  -H "Session-Token: $SESSION_TOKEN" \
  -H "App-Token: YOUR_APP_TOKEN" \
  --data-urlencode "range=0-100" | jq '.[] | {id, name, serial, ip: .networkports, os: .operatingsystems_id}'
```

Expected output:
```json
[
  {"id": 1, "name": "ArcBox-Client",  "ip": "10.10.1.100", "os": "Windows 11"},
  {"id": 2, "name": "ArcBox-SQL",     "ip": "10.10.1.99",  "os": "Windows Server 2022"},
  {"id": 3, "name": "ArcBox-Ubuntu",  "ip": "10.10.1.102", "os": "Ubuntu 20.04"},
  {"id": 4, "name": "OldServer-DC01", "ip": "10.10.1.50",  "os": "Windows Server 2019"}
]
```

**Step 3: Run diff engine — show discrepancies found**

```bash
# The sync script compares both datasets
python scripts/cmdb_sync.py --azure-query --glpi-query --diff

# Diff output:
# ┌──────────────────────────────────────────────────────────────────┐
# │ CMDB Sync Diff Report                                           │
# ├──────────────┬────────────────────────────────────────────────── │
# │ Machine      │ Discrepancy                                      │
# ├──────────────┼──────────────────────────────────────────────────-│
# │ ArcBox-SQL   │ IP changed: GLPI=10.10.1.99 → Azure=10.10.1.101 │
# │ ArcBox-Ubuntu│ OS upgraded: GLPI=Ubuntu 20.04 → Azure=22.04    │
# │ OldServer-DC01│ In GLPI but NOT in Azure (decommissioned?)     │
# │ ArcBox-Win2K22│ In Azure but NOT in GLPI (new server?)         │
# └──────────────┴──────────────────────────────────────────────────┘
```

**Step 4: Auto-update exact matches (IP changed, OS upgraded)**

```bash
# Auto-fix clear matches where only attributes changed
python scripts/cmdb_sync.py --auto-update

# Output:
# ✅ ArcBox-SQL: Updated IP 10.10.1.99 → 10.10.1.101 in GLPI
# ✅ ArcBox-Ubuntu: Updated OS Ubuntu 20.04 → Ubuntu 22.04 in GLPI
# ⏭  Skipped 2 ambiguous cases (require human review)
```

Under the hood, the auto-update calls the GLPI API:
```bash
# Update IP for ArcBox-SQL
curl -s -X PUT \
  "http://glpi.arcbox.local/apirest.php/Computer/2" \
  -H "Session-Token: $SESSION_TOKEN" \
  -H "App-Token: YOUR_APP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": {"comment": "IP auto-updated by CMDB sync on 2025-02-15"}}'
```

**Step 5: Flag ambiguous cases for human review**

```
⚠ AMBIGUOUS — Requires Human Review:

1. OldServer-DC01 (GLPI ID: 4)
   Status: In GLPI but NOT found in Azure
   Possible reasons:
     - Server was decommissioned (remove from GLPI?)
     - Server lost Arc agent connectivity (investigate?)
     - Server was renamed (check by IP/serial?)
   Action needed: Confirm disposition

2. ArcBox-Win2K22
   Status: In Azure but NOT registered in GLPI
   Possible reasons:
     - Recently provisioned, not yet added to CMDB
     - Was added under a different name
   Action needed: Create new CI or link to existing
```

**Step 6: Show reconciliation report**

```bash
python scripts/cmdb_sync.py --report
```

### What automation CANNOT do

In this scenario, automation handles everything needed. The only cases requiring human input are genuinely ambiguous situations (disappeared servers, unmatched new servers) where a human decision is required by policy — not by technical limitation.

## Why AI is Not Needed Here

This scenario deliberately demonstrates that **AI is not always the answer**. The CMDB sync process is:

| Aspect | Why deterministic automation is sufficient |
|---|---|
| **Data comparison** | Simple set difference — no interpretation needed |
| **Exact matches** | Name-based matching with attribute diff is trivial |
| **Update logic** | If name matches and attribute changed → update. No judgment required. |
| **Ambiguous cases** | Flagged for humans, not guessed at by AI |
| **Reporting** | Template-based output, no natural language generation needed |

**Key message for the audience**: A mature ops team knows when to use AI and when simple automation is better. CMDB sync is a perfect example of a problem that's been solvable with scripts for decades — the value here is in the **integration** (Azure Resource Graph ↔ GLPI API), not in AI.

## Talking Points

1. **"Not everything needs AI"** — This is the most important point. CMDB sync is deterministic: query, compare, update. Adding AI would add complexity without adding value.
2. **"Integration is the hard part"** — The value isn't in fancy algorithms; it's in connecting Azure Resource Graph to GLPI via APIs automatically.
3. **"Auto-update safe cases, flag risky ones"** — The 85/15 split here is automation vs. human review, not automation vs. AI.
4. **"Audit compliance for free"** — Every sync generates a reconciliation report. No more scrambling before audits.
5. **"This runs on a schedule"** — Once set up, it runs daily/weekly. The CMDB is always current, not perpetually stale.

## Expected Output

```
╔══════════════════════════════════════════════════════════╗
║              CMDB Reconciliation Report                  ║
║              2025-02-15 08:00 UTC                        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Azure Resource Graph: 4 machines                        ║
║  GLPI CMDB:           4 CIs                              ║
║                                                          ║
║  ✅ In sync:          2 (ArcBox-Client, ArcBox-SQL*)     ║
║  🔄 Auto-updated:     2                                  ║
║     • ArcBox-SQL — IP: 10.10.1.99 → 10.10.1.101         ║
║     • ArcBox-Ubuntu — OS: Ubuntu 20.04 → 22.04          ║
║  ⚠  Needs review:     2                                  ║
║     • OldServer-DC01 — in GLPI, not in Azure             ║
║     • ArcBox-Win2K22 — in Azure, not in GLPI             ║
║                                                          ║
║  Sync accuracy: 50% before → 100% after (for matched)   ║
║  Next sync: 2025-02-16 08:00 UTC                         ║
╚══════════════════════════════════════════════════════════╝
```
