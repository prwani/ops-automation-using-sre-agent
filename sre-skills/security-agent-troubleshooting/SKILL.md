---
name: security-agent-troubleshooting
description: Diagnoses and remediates Microsoft Defender for Endpoint agent issues on Windows servers. Use when asked about Defender health, MDE agent, security agent, or antivirus status.
---

# Security Agent Troubleshooting

Execute these steps IN ORDER. Do not skip steps or explore the repo.

## Environment

- Subscription: `31adb513-7077-47bb-9567-8e9d2a462bcf`
- Resource Group: `rg-arcbox-itpro`
- Region: `swedencentral`
- Windows servers: `ArcBox-Win2K22`, `ArcBox-Win2K25`, `ArcBox-SQL`
- GLPI URL: `http://glpi-opsauto-demo.swedencentral.azurecontainer.io`

## Step 1 — List Arc-connected servers (1 command)

```shell
az connectedmachine list --resource-group rg-arcbox-itpro --query "[].{Name:name, Status:status, OS:osName, LastSeen:lastStatusChange}" -o table
```

Confirm all three Windows servers appear and are Connected. If any server shows Disconnected, note it — remaining steps will not work for that machine.

## Step 2 — Check Defender extension status for ALL servers

Run once per server (lightweight metadata query, no remote execution):

```shell
az connectedmachine extension list --machine-name ArcBox-Win2K22 -g rg-arcbox-itpro --query "[?contains(name,'MDE') || contains(name,'Defender')].{name:name,state:provisioningState,version:typeHandlerVersion}" -o table
```

```shell
az connectedmachine extension list --machine-name ArcBox-Win2K25 -g rg-arcbox-itpro --query "[?contains(name,'MDE') || contains(name,'Defender')].{name:name,state:provisioningState,version:typeHandlerVersion}" -o table
```

```shell
az connectedmachine extension list --machine-name ArcBox-SQL -g rg-arcbox-itpro --query "[?contains(name,'MDE') || contains(name,'Defender')].{name:name,state:provisioningState,version:typeHandlerVersion}" -o table
```

If the MDE extension is missing or state != Succeeded on any server, note it as CRITICAL.

## Step 3 — Check Defender health via Log Analytics (ONE query for ALL servers)

Query the Log Analytics workspace for heartbeat and security baseline data across all servers in a single call:

```shell
az monitor log-analytics query --workspace f98fca75-7479-45e5-bf0c-87b56a9f9e8c --analytics-query 'Heartbeat | where Computer in~ ("ArcBox-Win2K22","ArcBox-Win2K25","ArcBox-SQL") | summarize LastHeartbeat=max(TimeGenerated) by Computer | extend StaleMinutes=datetime_diff("minute",now(),LastHeartbeat)' -o table
```

If any server shows StaleMinutes > 30, flag it as WARNING. If StaleMinutes > 120, flag as CRITICAL.

**Only proceed to Step 4 if** Step 2 shows missing/failed extensions OR Step 3 shows stale heartbeats. If all servers are healthy, skip to Step 6 (Summarize).

## Step 4 — Diagnose unhealthy servers via Arc run-command

For each server flagged in Steps 2–3, run ONE combined diagnostic command that checks services, Defender status, event logs, AND connectivity together. Use `--async-execution true` so commands run in parallel:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeDiag --location swedencentral --async-execution true --script 'Write-Output "=== SERVICES ==="; Get-Service WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType | Format-Table -AutoSize; Write-Output "=== DEFENDER STATUS ==="; Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,AntivirusSignatureLastUpdated | Format-List; Write-Output "=== RECENT EVENTS ==="; Get-WinEvent -LogName "Microsoft-Windows-Windows Defender/Operational" -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap; Write-Output "=== CONNECTIVITY ==="; Test-NetConnection winatp-gw-weu.microsoft.com -Port 443 -WarningAction SilentlyContinue | Select-Object ComputerName,TcpTestSucceeded; Test-NetConnection us-v20.events.data.microsoft.com -Port 443 -WarningAction SilentlyContinue | Select-Object ComputerName,TcpTestSucceeded'
```

After dispatching commands for all unhealthy servers, batch-read results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeDiag --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Evaluate each section of the output:

**Services:** WinDefend or Sense stopped → CRITICAL. MdCoreSvc stopped → WARNING.

**Defender status:** AntivirusEnabled=False or RealTimeProtectionEnabled=False → CRITICAL. AntivirusSignatureAge > 3 → WARNING, > 7 → CRITICAL.

**Events:** ID 5001 (real-time disabled) → CRITICAL. ID 5010/5012 (update failed) → WARNING. ID 1116/1117 (malware) → log for awareness.

**Connectivity:** TcpTestSucceeded=False → CRITICAL (firewall issue, do NOT auto-remediate).

## Step 5 — Remediation (only if Step 4 shows fixable issues)

Skip this step entirely if Step 4 found no issues or only connectivity failures (those require firewall changes).

**Service stopped → Restart it:**

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeRestart --location swedencentral --async-execution true --script 'Restart-Service WinDefend -Force -ErrorAction SilentlyContinue; Start-Service Sense -ErrorAction SilentlyContinue; Start-Service MdCoreSvc -ErrorAction SilentlyContinue; Start-Sleep -Seconds 10; Get-Service WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table -AutoSize'
```

**Definitions stale → Force update:**

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeUpdate --location swedencentral --async-execution true --script 'Update-MpSignature -UpdateSource MicrosoftUpdateServer -ErrorAction SilentlyContinue; Start-Sleep -Seconds 30; Get-MpComputerStatus | Select-Object AntivirusSignatureAge,AntivirusSignatureLastUpdated | Format-List'
```

After remediation, re-read the run-command results to verify the fix took effect. Do NOT attempt remediation for connectivity issues — those require firewall changes.

## Step 6 — Summarize findings

Present results as a table:

| Server | WinDefend | Sense | MdCoreSvc | Definitions Age | RealTime | Connectivity | Status |
|--------|-----------|-------|-----------|-----------------|----------|--------------|--------|
| ArcBox-Win2K22 | Running/Stopped | Running/Stopped | Running/Stopped | _days_ | True/False | OK/FAIL | OK / WARNING / CRITICAL |
| ArcBox-Win2K25 | ... | ... | ... | ... | ... | ... | ... |
| ArcBox-SQL | ... | ... | ... | ... | ... | ... | ... |

## Step 7 — Create GLPI ticket if escalation needed

Create a ticket only if:
- Any service won't restart after remediation
- Connectivity is blocked (firewall change needed)
- Definitions won't update
- Real-time protection cannot be re-enabled

First, initialize a GLPI session:

```shell
curl -s -X GET -H 'Content-Type: application/json' -H 'Authorization: user_token YOUR_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession'
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H 'Content-Type: application/json' -H 'Session-Token: SESSION_TOKEN' -H 'App-Token: YOUR_APP_TOKEN' -d '{"input": {"name": "[Security] Defender agent issue: SERVER_NAME - ISSUE_SUMMARY", "content": "DETAILED_FINDINGS_AND_REMEDIATION_ATTEMPTED", "type": 1, "urgency": 4, "priority": 4}}' 'http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket'
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
