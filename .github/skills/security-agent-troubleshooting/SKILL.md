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

## Step 1 — Check Defender extension status on Arc machines

For each server (ArcBox-Win2K22, ArcBox-Win2K25, ArcBox-SQL):

```shell
az connectedmachine extension list --machine-name SERVER_NAME --resource-group rg-arcbox-itpro --query "[].{Name:name, Type:properties.type, Status:properties.provisioningState, Version:properties.typeHandlerVersion}" -o table
```

Look for the `MDE.Windows` or `MicrosoftMonitoringAgent` extension. If missing or Status != Succeeded, note it as CRITICAL.

## Step 2 — Check Defender service status via Arc Run Command

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeServiceCheck --location swedencentral --script "Get-Service -Name WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType | Format-Table -AutoSize" --no-wait
```

Then check results (poll until executionState is Succeeded):

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeServiceCheck --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Expected: All three services should show Status=Running.
- WinDefend stopped → CRITICAL
- Sense stopped → CRITICAL
- MdCoreSvc stopped → WARNING

## Step 3 — Check Defender definitions and real-time protection

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeDefinitions --location swedencentral --script "Get-MpComputerStatus | Select-Object AntivirusSignatureAge,AntivirusSignatureLastUpdated,RealTimeProtectionEnabled,AntivirusEnabled,AMServiceEnabled,OnAccessProtectionEnabled | Format-List" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeDefinitions --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Thresholds:
- AntivirusSignatureAge > 3 → WARNING (definitions stale)
- AntivirusSignatureAge > 7 → CRITICAL (definitions very stale)
- RealTimeProtectionEnabled = False → CRITICAL
- AntivirusEnabled = False → CRITICAL

## Step 4 — Check Defender event logs for errors

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeEventLog --location swedencentral --script "Get-WinEvent -LogName 'Microsoft-Windows-Windows Defender/Operational' -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeEventLog --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Look for Event IDs:
- 5001 = Real-time protection disabled → CRITICAL
- 5010/5012 = Scan/definition update failed → WARNING
- 1116/1117 = Malware detected/action taken → log for awareness

## Step 5 — Check connectivity to Defender endpoints

For each server:

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeConnectivity --location swedencentral --script "foreach (\$ep in @('winatp-gw-weu.microsoft.com','winatp-gw-neu.microsoft.com','us-v20.events.data.microsoft.com')) { \$r = Test-NetConnection -ComputerName \$ep -Port 443 -WarningAction SilentlyContinue; Write-Output \"\$ep : TcpTestSucceeded=\$(\$r.TcpTestSucceeded)\" }" --no-wait
```

Then check results:

```shell
az connectedmachine run-command show --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeConnectivity --query "instanceView.{state:executionState, output:output, error:error}" -o json
```

Any endpoint with TcpTestSucceeded=False → CRITICAL (firewall or network issue)

## Step 6 — Remediation (only if safe)

Based on findings, apply remediations:

**Service stopped → Restart it:**

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeRestart --location swedencentral --script "Restart-Service WinDefend -Force -ErrorAction SilentlyContinue; Start-Service Sense -ErrorAction SilentlyContinue; Start-Service MdCoreSvc -ErrorAction SilentlyContinue; Start-Sleep -Seconds 10; Get-Service WinDefend,Sense,MdCoreSvc -ErrorAction SilentlyContinue | Select-Object Name,Status | Format-Table -AutoSize" --no-wait
```

**Definitions stale → Force update:**

```shell
az connectedmachine run-command create --resource-group rg-arcbox-itpro --machine-name SERVER_NAME --name mdeUpdate --location swedencentral --script "Update-MpSignature -UpdateSource MicrosoftUpdateServer -ErrorAction SilentlyContinue; Start-Sleep -Seconds 30; Get-MpComputerStatus | Select-Object AntivirusSignatureAge,AntivirusSignatureLastUpdated | Format-List" --no-wait
```

After remediation, re-run Step 2 and Step 3 to verify the fix took effect.

Do NOT attempt remediation for connectivity issues — those require firewall changes.

## Step 7 — Summarize findings

Present results as a table:

| Server | WinDefend | Sense | MdCoreSvc | Definitions Age | RealTime | Connectivity | Status |
|--------|-----------|-------|-----------|-----------------|----------|--------------|--------|
| ArcBox-Win2K22 | Running/Stopped | Running/Stopped | Running/Stopped | _days_ | True/False | OK/FAIL | OK / WARNING / CRITICAL |
| ArcBox-Win2K25 | ... | ... | ... | ... | ... | ... | ... |
| ArcBox-SQL | ... | ... | ... | ... | ... | ... | ... |

## Step 8 — Create GLPI ticket if escalation needed

Create a ticket if:
- Any service won't restart after remediation
- Connectivity is blocked (firewall change needed)
- Definitions won't update
- Real-time protection cannot be re-enabled

First, initialize a GLPI session:

```shell
curl -s -X GET -H "Content-Type: application/json" -H "Authorization: user_token YOUR_TOKEN" -H "App-Token: YOUR_APP_TOKEN" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

Then create the ticket (replace SESSION_TOKEN with the value from initSession):

```shell
curl -s -X POST -H "Content-Type: application/json" -H "Session-Token: SESSION_TOKEN" -H "App-Token: YOUR_APP_TOKEN" -d "{\"input\": {\"name\": \"[Security] Defender agent issue: SERVER_NAME - ISSUE_SUMMARY\", \"content\": \"DETAILED_FINDINGS_AND_REMEDIATION_ATTEMPTED\", \"type\": 1, \"urgency\": 4, \"priority\": 4}}" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/Ticket"
```

If GLPI credentials are not available, report the findings and recommend the user create a ticket manually.
