# Microsoft Defender for Endpoint Agent Troubleshooting SOP

## Overview

| Field | Value |
|---|---|
| **Trigger** | Defender agent health alert from Defender for Cloud, or manual request |
| **Scope** | Windows servers enrolled in Microsoft Defender for Endpoint |
| **Automation tier** | Tier 1 (Arc Run Command) + Tier 2 (Security Agent) |
| **Owner** | Security / Wintel SRE team |

---

## Diagnosis Steps

Run these steps in order. Stop and remediate if a root cause is found.

### Step 1 — Check Agent Onboarding Status

Query the Defender for Endpoint device API to confirm the server is onboarded.

- API: `GET /api/machines?$filter=computerDnsName eq '{hostname}'`
- **If not onboarded** → proceed to Remediation 4 (re-onboard).
- **If onboarded** → continue to Step 2.

### Step 2 — Check MdCoreSvc Service Status

Run Arc Run Command on the target server:

```powershell
Get-Service -Name MdCoreSvc | Select-Object Name, Status, StartType
```

- **If Stopped** → proceed to Remediation 1 (restart service).
- **If Running** → continue to Step 3.

### Step 3 — Check Agent Last Seen Timestamp

From the Defender API response (Step 1), check `lastSeen` field.

- If `lastSeen` > 24 hours ago → network connectivity issue likely.
- Continue to Step 4.

### Step 4 — Check Network Connectivity

Run Arc Run Command to test connectivity to Defender endpoints:

```powershell
$endpoints = @(
    "*.endpoint.security.microsoft.com",
    "unitedstates.smart.microsoft.com"
)
$endpoints | ForEach-Object {
    $result = Test-NetConnection -ComputerName $_ -Port 443 -WarningAction SilentlyContinue
    [PSCustomObject]@{ Endpoint = $_; Reachable = $result.TcpTestSucceeded }
} | ConvertTo-Json -Compress
```

- **If unreachable** → proceed to Remediation 2 (firewall change).

### Step 5 — Check for Conflicting AV Software

```powershell
Get-WmiObject -Namespace root\SecurityCenter2 -Class AntiVirusProduct |
  Select-Object displayName, productState | ConvertTo-Json -Compress
```

- If a third-party AV is present and active → raise for security team review.

---

## Remediation

### Remediation 1 — Restart MdCoreSvc

```powershell
Restart-Service -Name MdCoreSvc -Force
Start-Sleep -Seconds 30
Get-Service -Name MdCoreSvc | Select-Object Name, Status
```

### Remediation 2 — Raise Firewall Change Ticket

Create an ITSM change ticket (P3) requesting that the security team unblock outbound HTTPS to `*.endpoint.security.microsoft.com` on the affected server's network segment.

### Remediation 3 — Trigger Update Manager Patch Run

If the Defender agent binary is outdated (version check via API), trigger an Azure Update Manager on-demand assessment and deployment for the server.

### Remediation 4 — Re-run Onboarding Package

Retrieve the onboarding script from Defender for Cloud and execute via Arc Run Command:

```powershell
# Script content injected at runtime from Key Vault
& "C:\Temp\WindowsDefenderATPOnboardingScript.cmd"
```

---

## Output

- **ITSM ticket** created for each remediation action taken.
- **Memory note** added if the same server requires agent remediation > 2 times in 30 days (pattern flagged for review).
