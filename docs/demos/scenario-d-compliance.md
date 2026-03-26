# Scenario D: Compliance Reporting

> **Defender for Cloud + Azure Policy** — ArcBox VMs in `rg-arcbox-itpro`, Defender for Cloud enabled with CIS benchmarks.

## Overview

Compliance reporting is a daily obligation that consumes significant SRE time — pulling data from Defender for Cloud, cross-referencing Azure Policy states, formatting reports, and distributing them to stakeholders. The vast majority of this work is deterministic data retrieval and formatting. AI adds value only at the narrative and prioritization layer.

| Layer | Coverage | What it does |
|-------|----------|--------------|
| **Phase 1 — Deterministic Automation** | ~95% | Defender API pull, Azure Policy state query, formatted HTML/PDF report, auto-distribute |
| **Phase 2 — AI (SRE Agent)** | ~5% | Executive summary with trends, root-cause hypotheses for common non-compliance, business-context prioritization |

## What the team does today (1 hr daily manual report)

1. **Log into Defender for Cloud** — navigate to regulatory compliance dashboard, screenshot or export CIS benchmark results.
2. **Open Azure Policy** — filter by `rg-arcbox-itpro`, manually note non-compliant resources and which policies they violate.
3. **Cross-reference in Excel** — combine Defender findings with Policy state into a single spreadsheet.
4. **Calculate Secure Score** — pull current score, compare to yesterday, note any changes.
5. **Write narrative** — summarize what changed, what needs attention, add context for leadership.
6. **Email the report** — attach spreadsheet and narrative to a distribution list.

**Total time:** ~1 hour/day × 5 days = **5 hours/week** of skilled engineer time on copy-paste reporting.

---

## Phase 1: Deterministic Automation (~95%)

### What it solves

- Automated data collection from Defender for Cloud and Azure Policy APIs
- Consistent, repeatable report formatting (HTML with charts, PDF export)
- Scheduled distribution — no human in the loop for daily sends
- Historical trend tracking via stored report data

### Step-by-step demo

#### Step 1: Query Defender compliance

Pull regulatory compliance standards to see overall posture:

```bash
az security regulatory-compliance-standards list -o table
```

Expected output shows CIS, Azure Security Benchmark, and other enabled standards with pass/fail/skip counts.

#### Step 2: Query Azure Policy state

Summarize policy compliance for the ArcBox resource group:

```bash
az policy state summarize --resource-group rg-arcbox-itpro -o table
```

Returns a summary of compliant vs. non-compliant resources and policy assignments.

#### Step 3: Query non-compliant resources

List specific resources that are non-compliant:

```bash
az policy state list --filter "complianceState eq 'NonCompliant'" --resource-group rg-arcbox-itpro -o table
```

Each row identifies a resource, the violated policy, and the timestamp of last evaluation.

#### Step 4: Show auto-generated compliance report (HTML format with charts)

The automation pipeline renders an HTML report containing:

- **Compliance score gauge** — current percentage with trend arrow
- **Standards breakdown table** — pass/fail/skip per regulatory standard
- **Non-compliant resources list** — sortable table with resource name, policy, severity
- **Trend chart** — 30-day compliance trajectory (line chart)
- **PDF export** — one-click download for offline distribution

#### Step 5: Show Secure Score

Pull the current Secure Score controls to quantify overall security posture:

```bash
az security secure-score-controls list -o table
```

Shows each control family (e.g., "Enable MFA", "Apply system updates") with current score, max score, and percentage.

#### Step 6: Show auto-email distribution via Outlook connector

- Logic App triggers daily at 07:00 UTC
- Collects all data from Steps 1–5
- Renders the HTML report
- Sends via Outlook connector to the compliance distribution list
- Archives a copy to SharePoint for audit trail

### What automation CANNOT do

| Gap | Why it matters |
|-----|----------------|
| **Cannot explain WHY servers are non-compliant** | The API says "non-compliant" but not whether it's a failed agent install, a policy conflict, or a deliberate exception. |
| **Cannot prioritize: business-critical vs. dev** | A non-compliant production database and a dev sandbox VM look the same in the report. |
| **Report is data-heavy, lacks executive narrative** | Leadership needs "compliance improved, here's what to worry about" — not 200 rows of policy state. |

---

## Phase 2: AI Adds the Remaining ~5%

### What SRE Agent solves

The SRE Agent sits on top of the deterministic pipeline and adds the thin layer of intelligence that turns data into actionable insight:

- **Executive narrative generation** — converts raw numbers into a story leadership can act on
- **Root-cause hypothesis** — correlates non-compliance patterns with recent changes (patches, deployments, config drift)
- **Business-context prioritization** — ranks remediation by business impact, not just severity score

### Step-by-step demo

#### Ask SRE Agent: "Generate an executive compliance summary for my Arc servers"

```
User → SRE Agent:
"Generate an executive compliance summary for my Arc servers in rg-arcbox-itpro.
Include trends, root causes for non-compliance, and prioritized remediation."
```

#### SRE Agent uses compliance-investigation skill

The agent:

1. Calls the same Defender + Policy APIs (Phase 1 data)
2. Pulls historical compliance data for trend analysis
3. Cross-references with recent change logs (patch deployments, agent updates)
4. Applies business-context metadata (production vs. dev, data classification)

#### Show: executive narrative

> *"Compliance improved 4% this month, from 87% to 91%. CIS Benchmark Level 1 pass rate is now 94%. The remaining gaps are concentrated in two areas: endpoint protection (6 servers) and system update compliance (9 servers). Both correlate with last Tuesday's patch cycle."*

#### Show: root-cause hypothesis

> *"15 servers lost their monitoring agent after the March 12 patch deployment. The Azure Monitor agent extension failed to restart on Ubuntu 22.04 nodes due to a known systemd dependency issue (KB-2024-0312). Recommend re-deploying the extension via Azure Policy remediation task."*

#### Show: prioritized remediation list by business impact

| Priority | Resource | Issue | Business Impact | Recommended Action |
|----------|----------|-------|-----------------|-------------------|
| 🔴 P1 | `sql-prod-01` | Missing endpoint protection | Production database — PCI scope | Deploy Defender for Endpoint immediately |
| 🔴 P1 | `web-prod-03` | Failed system updates | Customer-facing web tier | Schedule maintenance window, apply patches |
| 🟡 P2 | `app-staging-02` | Monitoring agent offline | Staging — pre-prod validation | Re-deploy agent extension |
| 🟢 P3 | `dev-sandbox-07` | Non-compliant NSG rules | Dev sandbox — no customer data | Add to next sprint backlog |

---

## Talking Points (95% done by automation — AI is a nice-to-have)

1. **"The report writes itself."** Phase 1 automation eliminates 55+ minutes of the daily 1-hour reporting task. The data is pulled, formatted, and distributed without human intervention.

2. **"AI doesn't generate the data — it explains it."** Every number in the executive summary comes from the same deterministic API calls. The agent adds narrative, not fabrication.

3. **"Prioritization requires context the API doesn't have."** Defender tells you *what* is non-compliant. The agent tells you *what to fix first* based on business impact — that's the 5% that matters to leadership.

4. **"If the AI is wrong, the data is still right."** The underlying report is always available. The executive summary is additive — remove it and you still have a complete compliance report.

5. **"This is the pattern: automate the 95%, augment the 5%."** Compliance reporting is the clearest example — almost entirely deterministic, with a thin AI layer for human-readable insight.

## Expected Output

| Artifact | Source | Format |
|----------|--------|--------|
| Regulatory compliance summary | `az security regulatory-compliance-standards list` | Table / JSON |
| Policy state summary | `az policy state summarize` | Table / JSON |
| Non-compliant resource list | `az policy state list --filter ...` | Table / JSON |
| Secure Score breakdown | `az security secure-score-controls list` | Table / JSON |
| Formatted compliance report | Automation pipeline | HTML + PDF |
| Email distribution | Logic App + Outlook connector | Email with attachment |
| Executive summary (AI) | SRE Agent — compliance-investigation skill | Markdown narrative |
| Root-cause analysis (AI) | SRE Agent — correlation engine | Markdown with KB links |
| Prioritized remediation (AI) | SRE Agent — business-context ranking | Ranked table |
