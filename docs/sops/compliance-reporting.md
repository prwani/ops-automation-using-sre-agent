# Daily Compliance Report SOP

## Overview

| Field | Value |
|---|---|
| **Frequency** | Daily at 07:00 UTC |
| **Scope** | All subscriptions enrolled in Defender for Cloud |
| **Automation tier** | Tier 1 (data collection) + Tier 2 (Compliance Analyst Agent) |
| **Owner** | Security / Wintel SRE team |

---

## Data Sources

| Source | API / Method |
|---|---|
| Secure score | Defender for Cloud — `GET /secureScores` |
| Regulatory compliance | Defender for Cloud — `GET /regulatoryComplianceStandards/{standard}/controls` |
| Resource inventory | Azure Resource Graph — `resources` table |
| Historical scores | Cosmos DB `compliance-runs` container |

---

## Report Contents

### 1. Overall Secure Score

- Current score (0–100).
- Delta vs. previous day and previous 7 days.

### 2. Compliance Posture per Framework

Frameworks tracked:

| Framework | Standard ID |
|---|---|
| CIS Windows Server 2022 | `CIS Windows Server 2022` |
| NIST SP 800-53 | `NIST SP 800-53 R5` |
| ISO 27001 | `ISO 27001` |

Report shows: % compliant controls, total controls, failing controls count.

### 3. Top 10 Failing Controls

- Control ID and name.
- Number of servers failing the control.
- Recommended remediation (from Defender API).

### 4. Servers with > 5 Critical Findings

- Server name, resource group, critical finding count.
- Flagged for priority remediation.

### 5. Trend Analysis

| Period | Metric |
|---|---|
| 7-day | Compliance score delta per framework |
| 30-day | Compliance score delta per framework |

### 6. New Findings Since Last Report

- Findings that appeared in today's report but not in yesterday's Cosmos DB record.

---

## Output

1. **Cosmos DB** — `compliance-runs` container; one document per daily run.
2. **AI-generated executive summary** — produced by the **Compliance Analyst Agent** (Tier 2); plain-language summary of key findings for stakeholders.
3. **Portal notification** — summary card published to the ops portal.

---

## Escalation

| Condition | Action |
|---|---|
| Overall compliance drops > 5% in 24 hours | SRE Agent alert raised; P2 incident created |
| New Critical finding on Tier 0 server | P1 incident created immediately |
| Framework compliance drops below 70% | P3 ticket created for remediation planning |
