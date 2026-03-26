# Scenario A: Daily Health Check

## Overview

This demo walks through a daily health check across five Arc-enrolled servers running in ArcBox for IT Pros. It shows how **deterministic automation handles ~90% of the work** — collecting metrics, evaluating thresholds, generating reports, and opening tickets — and then how the **SRE Agent adds the remaining ~10%** by interpreting trends, correlating cross-server anomalies, and producing a human-readable daily brief that automation alone cannot generate.

---

## What the Team Does Today (Manual Process)

| Step | Manual action | Time |
|------|--------------|------|
| 1 | RDP into each of the 5 servers one by one | 5 min |
| 2 | Open Task Manager / `top`, check CPU & memory | 5 min |
| 3 | Open Disk Management / `df -h`, check free space | 5 min |
| 4 | Open Services console, verify critical services are running | 5 min |
| 5 | Open Event Viewer, scan for Error/Critical events in last 6 h | 10 min |
| 6 | Copy findings into a Word doc or email | 5 min |
| 7 | If anything fails, manually open a ticket in the ITSM tool | 5 min |
| **Total** | | **~30–45 min** |

This is done **four times per day** (06:00, 12:00, 18:00, 00:00 UTC). It does not scale, is error-prone, and depends on someone remembering to do it.

---

## Demo Environment

| Component | Value |
|-----------|-------|
| Environment | [Azure Jumpstart ArcBox for IT Pros](https://azurearcjumpstart.com/azure_jumpstart_arcbox/ITPro) |
| Resource group | `rg-arcbox-itpro` |
| Location | `swedencentral` |
| Windows VMs | `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL` |
| Linux VMs | `ArcBox-Ubuntu-01`, `ArcBox-Ubuntu-02` |
| ITSM (demo) | GLPI — `http://glpi-opsauto-demo.swedencentral.azurecontainer.io` |

---

## Phase 1: Deterministic Automation (~90%)

### What It Solves

Deterministic automation replaces every manual step listed above. It runs on a timer (Azure Function, 4×/day), executes predefined health-check scripts on all five servers via **Azure Arc Run Commands**, evaluates results against fixed thresholds, produces a structured report, and auto-creates ITSM tickets for any WARNING or CRITICAL findings — all without human intervention.

### Thresholds

| Check | ⚠️ WARNING | 🔴 CRITICAL |
|-------|-----------|------------|
| Disk usage | > 80 % | > 90 % |
| CPU average | > 80 % | > 95 % |
| Memory usage | > 85 % | > 95 % |
| Critical services stopped | Any critical service | `MdCoreSvc` or `WinRM` |
| Event-log errors (6 h) | 1–10 errors | > 10 errors |

**Critical services monitored:** `wuauserv`, `WinRM`, `EventLog`, `MpsSvc`, `MdCoreSvc`

---

### Step-by-Step Demo

> **Tip:** Run these commands from Azure Cloud Shell or any terminal with the `az` CLI authenticated and the `connectedmachine` extension installed.

#### 0. Prerequisites

```bash
# Ensure the connectedmachine extension is installed
az extension add --name connectedmachine --upgrade

# Set common variables
RG="rg-arcbox-itpro"
LOCATION="swedencentral"
WIN_VMS=("ArcBox-Win2K22" "ArcBox-Win2K25" "ArcBox-SQL")
LINUX_VMS=("ArcBox-Ubuntu-01" "ArcBox-Ubuntu-02")
```

---

#### 1. Disk Check — Windows VMs

Run on each Windows VM to collect drive usage in JSON:

```bash
for VM in "${WIN_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-Disk" \
    --location $LOCATION \
    --script "Get-WmiObject Win32_LogicalDisk -Filter \"DriveType=3\" | ForEach-Object { \
        [PSCustomObject]@{ \
            Drive      = \$_.DeviceID; \
            SizeGB     = [math]::Round(\$_.Size / 1GB, 2); \
            FreeGB     = [math]::Round(\$_.FreeSpace / 1GB, 2); \
            UsedPercent = [math]::Round(((\$_.Size - \$_.FreeSpace) / \$_.Size) * 100, 1) \
        } \
    } | ConvertTo-Json" \
    --async-execution false \
    --output json
  echo "--- $VM disk check complete ---"
done
```

**Expected output per VM:**

```json
[
  {
    "Drive": "C:",
    "SizeGB": 127.0,
    "FreeGB": 82.35,
    "UsedPercent": 35.2
  },
  {
    "Drive": "D:",
    "SizeGB": 64.0,
    "FreeGB": 12.4,
    "UsedPercent": 80.6
  }
]
```

---

#### 2. CPU Check — Windows VMs

```bash
for VM in "${WIN_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-CPU" \
    --location $LOCATION \
    --script "\$samples = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 2 -MaxSamples 3).CounterSamples.CookedValue; \
    [PSCustomObject]@{ \
        AverageCpuPercent = [math]::Round((\$samples | Measure-Object -Average).Average, 1); \
        MaxCpuPercent     = [math]::Round((\$samples | Measure-Object -Maximum).Maximum, 1); \
        SampleCount       = \$samples.Count \
    } | ConvertTo-Json" \
    --async-execution false \
    --output json
  echo "--- $VM CPU check complete ---"
done
```

**Expected output:**

```json
{
  "AverageCpuPercent": 23.4,
  "MaxCpuPercent": 41.2,
  "SampleCount": 3
}
```

---

#### 3. Memory Check — Windows VMs

```bash
for VM in "${WIN_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-Memory" \
    --location $LOCATION \
    --script "\$os = Get-CimInstance Win32_OperatingSystem; \
    [PSCustomObject]@{ \
        TotalMemoryGB  = [math]::Round(\$os.TotalVisibleMemorySize / 1MB, 2); \
        FreeMemoryGB   = [math]::Round(\$os.FreePhysicalMemory / 1MB, 2); \
        UsedPercent    = [math]::Round((1 - (\$os.FreePhysicalMemory / \$os.TotalVisibleMemorySize)) * 100, 1) \
    } | ConvertTo-Json" \
    --async-execution false \
    --output json
  echo "--- $VM memory check complete ---"
done
```

---

#### 4. Critical Services Check — Windows VMs

```bash
for VM in "${WIN_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-Services" \
    --location $LOCATION \
    --script "\$svcNames = @('wuauserv','WinRM','EventLog','MpsSvc','MdCoreSvc'); \
    \$svcNames | ForEach-Object { \
        \$svc = Get-Service -Name \$_ -ErrorAction SilentlyContinue; \
        [PSCustomObject]@{ \
            Name      = \$_; \
            Status    = if (\$svc) { \$svc.Status.ToString() } else { 'NotFound' }; \
            StartType = if (\$svc) { \$svc.StartType.ToString() } else { 'N/A' } \
        } \
    } | ConvertTo-Json" \
    --async-execution false \
    --output json
  echo "--- $VM services check complete ---"
done
```

**Expected output:**

```json
[
  { "Name": "wuauserv",  "Status": "Stopped",  "StartType": "Manual" },
  { "Name": "WinRM",     "Status": "Running",  "StartType": "Automatic" },
  { "Name": "EventLog",  "Status": "Running",  "StartType": "Automatic" },
  { "Name": "MpsSvc",    "Status": "Running",  "StartType": "Automatic" },
  { "Name": "MdCoreSvc", "Status": "Running",  "StartType": "Automatic" }
]
```

---

#### 5. Event Log Check — Windows VMs

Queries for Error and Critical events in the last 6 hours:

```bash
for VM in "${WIN_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-EventLog" \
    --location $LOCATION \
    --script "\$cutoff = (Get-Date).AddHours(-6); \
    \$events = Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2; StartTime=\$cutoff} -ErrorAction SilentlyContinue; \
    [PSCustomObject]@{ \
        ErrorCount    = (\$events | Where-Object Level -eq 2).Count; \
        CriticalCount = (\$events | Where-Object Level -eq 1).Count; \
        TotalCount    = \$events.Count; \
        TopSources    = (\$events | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 3 Name, Count) \
    } | ConvertTo-Json -Depth 3" \
    --async-execution false \
    --output json
  echo "--- $VM event log check complete ---"
done
```

---

#### 6. Disk Check — Linux VMs

```bash
for VM in "${LINUX_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-Disk" \
    --location $LOCATION \
    --script "df -h --output=source,size,used,avail,pcent -x tmpfs -x devtmpfs | tail -n +2 | awk '{print \"{\\\"Filesystem\\\":\\\"\" \$1 \"\\\",\\\"Size\\\":\\\"\" \$2 \"\\\",\\\"Used\\\":\\\"\" \$3 \"\\\",\\\"Avail\\\":\\\"\" \$4 \"\\\",\\\"UsedPercent\\\":\\\"\" \$5 \"\\\"}\"}' | jq -s ." \
    --async-execution false \
    --output json
  echo "--- $VM disk check complete ---"
done
```

---

#### 7. CPU & Memory Check — Linux VMs

```bash
for VM in "${LINUX_VMS[@]}"; do
  az connectedmachine run-command create \
    --resource-group $RG \
    --machine-name "$VM" \
    --name "HealthCheck-CPUMem" \
    --location $LOCATION \
    --script "echo '{\"CpuUsagePercent\":' \$(top -bn3 | grep 'Cpu(s)' | tail -1 | awk '{print 100 - \$8}') ',\"MemTotalMB\":' \$(free -m | awk '/Mem:/{print \$2}') ',\"MemUsedMB\":' \$(free -m | awk '/Mem:/{print \$3}') ',\"MemUsedPercent\":' \$(free | awk '/Mem:/{printf \"%.1f\", \$3/\$2*100}') '}' | jq ." \
    --async-execution false \
    --output json
  echo "--- $VM CPU/memory check complete ---"
done
```

---

#### 8. Automated Threshold Evaluation

In production this runs inside the Azure Function (`HealthCheckEngine`). For the demo, simulate evaluation with this PowerShell snippet:

```powershell
# Simulated threshold evaluation (runs after data collection)
$thresholds = @{
    DiskWarning     = 80;  DiskCritical     = 90
    CpuWarning      = 80;  CpuCritical      = 95
    MemoryWarning   = 85;  MemoryCritical   = 95
    EventLogWarning = 1;   EventLogCritical = 10
}

# Example: evaluate disk result
$diskResult = @{ Drive = "D:"; UsedPercent = 88.5 }

if ($diskResult.UsedPercent -gt $thresholds.DiskCritical) {
    $severity = "CRITICAL"
} elseif ($diskResult.UsedPercent -gt $thresholds.DiskWarning) {
    $severity = "WARNING"
} else {
    $severity = "OK"
}

Write-Output "Disk $($diskResult.Drive): $($diskResult.UsedPercent)% used → $severity"
# Output: Disk D:: 88.5% used → WARNING
```

---

#### 9. Auto-Generated Report

The automation produces a structured report stored in Cosmos DB (`health-runs` container). Example output:

```
╔══════════════════════════════════════════════════════════════════════╗
║                  DAILY HEALTH CHECK REPORT                         ║
║                  2025-01-15 06:00 UTC                              ║
╠══════════════════════════════════════════════════════════════════════╣

  Server: ArcBox-Win2K22
  ├── Disk C:    35.2%  🟢 OK
  ├── Disk D:    88.5%  ⚠️  WARNING  (threshold: 80%)
  ├── CPU avg    23.4%  🟢 OK
  ├── Memory     62.1%  🟢 OK
  ├── Services   5/5    🟢 OK
  └── EventLog   3 err  ⚠️  WARNING  (1–10 errors in 6 h)

  Server: ArcBox-Win2K25
  ├── Disk C:    41.0%  🟢 OK
  ├── CPU avg    15.8%  🟢 OK
  ├── Memory     78.3%  🟢 OK
  ├── Services   5/5    🟢 OK
  └── EventLog   0 err  🟢 OK

  Server: ArcBox-SQL
  ├── Disk C:    55.2%  🟢 OK
  ├── Disk E:    91.3%  🔴 CRITICAL (threshold: 90%)
  ├── CPU avg    67.9%  🟢 OK
  ├── Memory     87.2%  ⚠️  WARNING  (threshold: 85%)
  ├── Services   5/5    🟢 OK
  └── EventLog   14 err 🔴 CRITICAL (>10 errors in 6 h)

  Server: ArcBox-Ubuntu-01
  ├── Disk /     42.0%  🟢 OK
  ├── CPU        11.2%  🟢 OK
  └── Memory     55.0%  🟢 OK

  Server: ArcBox-Ubuntu-02
  ├── Disk /     39.8%  🟢 OK
  ├── CPU        8.7%   🟢 OK
  └── Memory     53.1%  🟢 OK

  ────────────────────────────────────────────────────────────────
  Summary:  2 🔴 CRITICAL  |  2 ⚠️ WARNING  |  18 🟢 OK
  ────────────────────────────────────────────────────────────────
╚══════════════════════════════════════════════════════════════════════╝
```

---

#### 10. Auto-Ticket Creation in GLPI

For every CRITICAL or WARNING finding, the automation calls the GLPI adapter to create an incident:

```bash
# Example: the automation creates a ticket via the GLPI REST API
# (In production this is done by the glpi-create-ticket tool / GLPI adapter)

curl -s -X POST \
  "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket" \
  -H "Content-Type: application/json" \
  -H "Session-Token: $GLPI_SESSION_TOKEN" \
  -H "App-Token: $GLPI_APP_TOKEN" \
  -d '{
    "input": {
      "name": "[Health Check] ArcBox-SQL: Disk E: 91.3% CRITICAL",
      "content": "Automated health check detected CRITICAL disk usage on ArcBox-SQL.\n\nDrive: E:\nUsed: 91.3% (threshold: 90%)\nFree: 5.6 GB of 64 GB\n\nCheck type: disk\nRun ID: hc-2025-01-15-0600\nServer: ArcBox-SQL\nResource Group: rg-arcbox-itpro",
      "priority": 2,
      "type": 1,
      "itilcategories_id": 1
    }
  }'
```

**The automation creates one ticket per CRITICAL finding, one per WARNING finding.** In the example report above, it would create 4 tickets.

---

### What Automation CANNOT Do (Limitations)

Even with full automation, the following gaps remain:

| Gap | Example |
|-----|---------|
| **Cannot interpret WHY** a threshold was breached | Disk at 91% — is it temp files? Database growth? Log accumulation? Automation has no idea. |
| **Cannot spot slow-building trends** | Memory climbed from 70% → 75% → 80% → 85% over 4 days. Each individual check passed. The trend is invisible to threshold logic. |
| **Cannot correlate across servers** | Three servers all show elevated memory at the same time. A human would say "that's an app-level issue." Automation checks each server independently. |
| **Cannot prioritise or summarise** | 4 tickets created, all look equally urgent. No one reads the full report. The team needs a 3-sentence morning brief, not a data dump. |
| **Cannot handle novel situations** | A new event-log source starts appearing that isn't in the script. Automation ignores it completely. |

> 💡 **This is where Phase 2 — the SRE Agent — picks up.**

---

## Phase 2: AI Adds the Remaining ~10%

### What SRE Agent / AI Solves

The SRE Agent sits on top of the automation layer. It consumes the **same data** the automation already collected (health-check results in Cosmos DB, performance trends in Log Analytics) and adds:

- **Root-cause interpretation** — "Disk E: on ArcBox-SQL is filling because SQL transaction logs are not being truncated"
- **Trend projection** — "At current growth rate, disk will hit 95% in ~5 days"
- **Cross-server correlation** — "ArcBox-Win2K22, ArcBox-Win2K25, and ArcBox-SQL all show elevated memory → likely an app-level issue, not individual server problems"
- **Natural-language daily brief** — A 5-sentence summary an ops lead can read in 30 seconds
- **Intelligent ticket enrichment** — Tickets include context, probable cause, and suggested next steps

---

### Step-by-Step Demo

#### 1. Ask the SRE Agent

Open the SRE Agent at [sre.azure.com](https://sre.azure.com) (or the demo portal chat) and type:

> **"Check the health of all my Arc servers and summarize."**

The SRE Agent activates the **`wintel-health-check-investigation`** skill.

---

#### 2. Watch the Skill Execution

The agent executes the following sequence (visible in the activity trace):

```
1. cosmos-query-runs(taskType="health_check", status="WARNING,CRITICAL", limit=10)
   → Retrieves latest health-check results (from Phase 1 automation)

2. query-perf-trends(server_id="ArcBox-SQL", metric="disk", hours=168)
   → Pulls 7-day disk usage trend from Log Analytics

3. query-perf-trends(server_id="ArcBox-SQL", metric="memory", hours=168)
   → Pulls 7-day memory trend

4. query-perf-trends(server_id="ArcBox-Win2K22", metric="memory", hours=168)
   → Pulls 7-day memory trend for cross-correlation

5. arc-run-command(server_id="ArcBox-SQL", script="scripts/check_disk.ps1")
   → Live disk check for current state

6. cosmos-check-memories(server_id="ArcBox-SQL", check_type="disk")
   → Checks if there's a known suppression or context for this server

7. glpi-create-ticket(
       title="[Health Check] ArcBox-SQL: Disk E: trending to 95% in 5 days",
       description="<enriched analysis with trend data and probable cause>",
       priority="2",
       server_id="ArcBox-SQL"
   )
   → Creates an enriched ticket (or updates the existing one from Phase 1)
```

---

#### 3. Anomaly Detection Below Threshold

**What automation reported:** ArcBox-Win2K22 memory at 62.1% → 🟢 OK

**What the SRE Agent notices:**

> "ArcBox-Win2K22 memory was 48% a week ago and has been steadily climbing (+2%/day). While currently within thresholds, this is anomalous compared to its historical baseline of 45–50%. Investigate whether a recent deployment introduced a memory leak."

The agent flags this even though it's green — **automation would have silently passed it.**

---

#### 4. Trend Projection

The agent queries 7-day performance trends from Log Analytics and produces projections:

> **ArcBox-SQL — Disk E: Trend**
>
> | Day | Usage |
> |-----|-------|
> | Mon | 82.1% |
> | Tue | 84.3% |
> | Wed | 86.0% |
> | Thu | 88.2% |
> | Fri | 91.3% ← today (CRITICAL) |
> | **Projected Sat** | **~93.4%** |
> | **Projected Wed** | **~95%+ (capacity risk)** |
>
> "At the current rate of +2.3%/day, drive E: will reach 95% in approximately 5 days. Recommend immediate investigation of SQL transaction log growth and tempdb usage."

---

#### 5. Cross-Server Correlation

Automation created three separate tickets. The SRE Agent connects the dots:

> "Three servers (ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL) are all showing memory increases over the past 4 days. The increases coincide with the deployment of application version 3.2.1 on Tuesday. This pattern suggests an **application-level memory issue**, not independent server problems. Recommend investigating the application deployment rather than each server individually."

---

#### 6. Natural-Language Daily Brief

The agent generates a morning brief (also delivered via the `daily-brief` workflow at 07:00 UTC):

> ### 🟡 Morning Health Brief — 15 Jan 2025
>
> **Estate health: 78%** (3 of 5 servers fully healthy)
>
> 🔴 **ArcBox-SQL** is the priority today. Disk E: crossed 90% (91.3%) and is climbing at ~2.3%/day — you have roughly 5 days before it hits 95%. Event-log errors spiked to 14 in the last 6 hours, mostly from MSSQLSERVER source. Memory is also elevated at 87.2%. **Likely cause:** SQL transaction logs are not being truncated after backups.
>
> ⚠️ **Cross-server trend:** Memory is rising on 3 of 3 Windows servers since Tuesday's v3.2.1 deployment. Not yet critical, but worth investigating with the app team.
>
> 🟢 Both Ubuntu servers are healthy — no action needed.
>
> **Recommended actions:**
> 1. Check SQL backup/log-truncation jobs on ArcBox-SQL (P2 — today)
> 2. Coordinate with app team on memory increase since v3.2.1 (P3 — this week)

---

## Talking Points for Customer

Use these during the demo to land the key messages:

| # | Talking Point | When to Say It |
|---|--------------|----------------|
| 1 | *"The automation ran in **30 seconds** what took **45 minutes** manually — and it does it 4 times a day, never forgets, never misses a server."* | After showing Phase 1 report output |
| 2 | *"But look at these 4 tickets — they all say 'threshold exceeded' with no context. That's where the team still spends time today: figuring out **why**."* | Transitioning from Phase 1 to Phase 2 |
| 3 | *"The AI caught the disk **trend** that automation alone would have missed. A fixed threshold can't see that disk usage climbed 10% in 5 days."* | After showing trend projection |
| 4 | *"Three servers, three separate tickets. The AI correlated them into one insight: it's the app deployment, not the servers."* | After showing cross-server correlation |
| 5 | *"This morning brief took the AI 10 seconds to generate. It would take an engineer 20 minutes to write — and they'd need to read every metric first."* | After showing the daily brief |
| 6 | *"None of this replaces the engineer. It gives them back 45 minutes and a head start on the right problem."* | Closing |

---

## Expected Output

### Phase 1 — Automation Report

After running the `az connectedmachine run-command create` commands, you will see:

- **Per-VM JSON results** — raw metrics for disk, CPU, memory, services, event log
- **Threshold evaluation** — each metric flagged as 🟢 OK / ⚠️ WARNING / 🔴 CRITICAL
- **Structured report** — the table shown in step 9 above
- **GLPI tickets** — one ticket per WARNING/CRITICAL finding, visible at `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

### Phase 2 — SRE Agent Output

After asking the SRE Agent to check health:

- **Activity trace** — the tool calls the agent made (visible in sre.azure.com sidebar)
- **Trend charts** — 7-day disk/memory/CPU trends pulled from Log Analytics
- **Enriched tickets** — GLPI tickets updated with probable cause and recommended actions
- **Daily brief** — the natural-language summary shown in step 6 above (also visible in the ops portal dashboard)

### Portal Dashboard

The ops portal at `https://portal-opsauto-demo.swedencentral.azurecontainer.io` shows:

- **Dashboard** — today's health-check run cards with 🟢/🟡/🔴 indicators
- **History** — paginated list of all health-check runs with filters
- **Chat** — streaming conversation with the Ops Chat Agent
- **Memories** — active suppression rules and knowledge entries

---

## Quick Reference: All Commands in One Block

For convenience, here are all Windows VM health-check commands combined into a single script:

```bash
RG="rg-arcbox-itpro"
LOCATION="swedencentral"

for VM in ArcBox-Win2K22 ArcBox-Win2K25 ArcBox-SQL; do

  # Disk
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-Disk" \
    --location $LOCATION \
    --script "Get-WmiObject Win32_LogicalDisk -Filter \"DriveType=3\" | ForEach-Object { [PSCustomObject]@{ Drive=\$_.DeviceID; SizeGB=[math]::Round(\$_.Size/1GB,2); FreeGB=[math]::Round(\$_.FreeSpace/1GB,2); UsedPercent=[math]::Round(((\$_.Size-\$_.FreeSpace)/\$_.Size)*100,1) } } | ConvertTo-Json" \
    --async-execution false --output json

  # CPU
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-CPU" \
    --location $LOCATION \
    --script "\$s=(Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 2 -MaxSamples 3).CounterSamples.CookedValue; [PSCustomObject]@{ AvgCpu=[math]::Round((\$s|Measure-Object -Average).Average,1); MaxCpu=[math]::Round((\$s|Measure-Object -Maximum).Maximum,1) } | ConvertTo-Json" \
    --async-execution false --output json

  # Memory
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-Memory" \
    --location $LOCATION \
    --script "\$os=Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{ TotalGB=[math]::Round(\$os.TotalVisibleMemorySize/1MB,2); FreeGB=[math]::Round(\$os.FreePhysicalMemory/1MB,2); UsedPct=[math]::Round((1-(\$os.FreePhysicalMemory/\$os.TotalVisibleMemorySize))*100,1) } | ConvertTo-Json" \
    --async-execution false --output json

  # Services
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-Services" \
    --location $LOCATION \
    --script "@('wuauserv','WinRM','EventLog','MpsSvc','MdCoreSvc') | ForEach-Object { \$s=Get-Service \$_ -EA SilentlyContinue; [PSCustomObject]@{Name=\$_;Status=if(\$s){\$s.Status.ToString()}else{'NotFound'}} } | ConvertTo-Json" \
    --async-execution false --output json

  # Event Log
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-EventLog" \
    --location $LOCATION \
    --script "\$e=Get-WinEvent -FilterHashtable @{LogName='System','Application';Level=1,2;StartTime=(Get-Date).AddHours(-6)} -EA SilentlyContinue; [PSCustomObject]@{Errors=(\$e|?{$_.Level-eq2}).Count;Critical=(\$e|?{\$_.Level-eq1}).Count;Total=\$e.Count} | ConvertTo-Json" \
    --async-execution false --output json

  echo "=== $VM complete ==="
done
```

And the Linux VMs:

```bash
for VM in ArcBox-Ubuntu-01 ArcBox-Ubuntu-02; do

  # Disk
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-Disk" \
    --location $LOCATION \
    --script "df -h --output=source,size,used,avail,pcent -x tmpfs -x devtmpfs | tail -n +2" \
    --async-execution false --output json

  # CPU + Memory
  az connectedmachine run-command create \
    --resource-group $RG --machine-name "$VM" --name "HealthCheck-CPUMem" \
    --location $LOCATION \
    --script "echo '=== CPU ===' && top -bn1 | head -5 && echo '=== Memory ===' && free -h" \
    --async-execution false --output json

  echo "=== $VM complete ==="
done
```
