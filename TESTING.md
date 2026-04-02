# Testing the Ops Automation Solution

## Prerequisites

| Requirement | How to get it |
|---|---|
| Azure CLI | `winget install Microsoft.AzureCLI` or [install guide](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| GitHub Copilot CLI | `gh extension install github/copilot-cli` — requires a [Copilot license](https://github.com/features/copilot) |
| Azure access | `az login` — you need Reader + Log Analytics Reader on subscriptions with Arc servers |

## Quick Start (5 minutes)

### Step 1: Clone and enter the repo
```bash
git clone https://github.com/prwani/ops-automation-using-sre-agent.git
cd ops-automation-using-sre-agent
```

### Step 2: Login to Azure
```bash
az login
```

### Step 3: Skills are already in .github/skills/ — verify they load
```bash
copilot
> /skills list
```

You should see 6 skills: wintel-health-check-investigation, security-agent-troubleshooting, compliance-investigation, patch-validation, vmware-bau-operations, ticket-driven-remediation

### Step 4: Run your first test
```bash
copilot -p "Use the /wintel-health-check-investigation skill. Run a FULL health check on all my Arc servers — check CPU, memory, disk usage, services, and event logs. Show a summary table with all metrics and flag any warnings or critical issues." --allow-all-tools
```

## All Test Commands (Copy-Paste Ready)

### Skill 1: Health Check
```bash
copilot -p "Use the /wintel-health-check-investigation skill. Run a FULL health check — query Log Analytics for CPU, memory, disk on ALL Arc servers. Then check services and event logs via Arc Run Commands. Summarize in a table with OK/WARNING/CRITICAL per server." --allow-all-tools
```

### Skill 2: Security Agent
```bash
copilot -p "Use the /security-agent-troubleshooting skill. Check Defender agent health on ALL Arc servers — verify extensions are installed, check heartbeat in Log Analytics, and run diagnostics on any unhealthy agents. Show a status table per server." --allow-all-tools
```

### Skill 3: Compliance
```bash
copilot -p "Use the /compliance-investigation skill. Query Defender for Cloud regulatory compliance AND Azure Policy state for all Arc servers. List failing controls, non-compliant resources, and prioritize findings as P1-P4." --allow-all-tools
```

### Skill 4: Patch Assessment
```bash
copilot -p "Use the /patch-validation skill. Query Azure Update Manager for missing patches on ALL Arc servers. Show patch counts by classification (Critical, Security, Other) per server. Run pre-patch checks (disk space, pending reboots, services) on each server." --allow-all-tools
```

### Skill 5: VMware BAU
```bash
copilot -p "Use the /vmware-bau-operations skill. Find all Azure VMs that host Hyper-V, list ALL checkpoints on each, classify by age (KEEP <7d, WARNING 7-30d, CRITICAL >30d), and show a cleanup summary." --allow-all-tools
```

### Skill 6: Ticket-Driven Remediation (requires GLPI)

**Prerequisite:** Seed sample tickets first (or verify they exist):
```powershell
# Check GLPI has open tickets — if empty, create them:
curl.exe -s -H "Content-Type: application/json" -H "Authorization: Basic Z2xwaTpnbHBp" "http://glpi-opsauto-demo.swedencentral.azurecontainer.io/apirest.php/initSession"
```

Then invoke the skill:
```bash
copilot -p "Use the /ticket-driven-remediation skill. Connect to GLPI at http://glpi-opsauto-demo.swedencentral.azurecontainer.io with username=glpi, password=glpi. Read all open tickets, investigate each one using Azure Arc and Defender for Cloud, update each ticket with your findings, and mark resolved tickets as Solved." --allow-all-tools
```

## Automation Scripts (No AI — deterministic)

These PowerShell scripts demonstrate what automation handles WITHOUT AI:

```bash
./scripts/demo-health-check.ps1
./scripts/demo-compliance-report.ps1
./scripts/demo-alert-monitoring.ps1
./scripts/demo-cmdb-sync.ps1
./scripts/demo-patch-assessment.ps1
./scripts/demo-snapshot-cleanup.ps1
./scripts/demo-run-all.ps1  # Runs all 6 above
```

## Programmatic Testing (CI/CD, Batch Mode)

Run Copilot CLI non-interactively with `-p` flag:

```bash
copilot -p "PROMPT" --allow-all-tools --model gpt-5.4-mini
```

Options:
- `--allow-all-tools` — auto-approve all tool usage (shell, file, etc.)
- `--allow-tool='shell(az)'` — only allow az CLI commands
- `--model gpt-5.4-mini` — use a specific model (faster/cheaper for testing)

Example: test all 5 skills in sequence:
```bash
for skill in "wintel-health-check-investigation" "security-agent-troubleshooting" "compliance-investigation" "patch-validation" "vmware-bau-operations"; do
    echo "=== Testing $skill ==="
    copilot -p "Use the /$skill skill. Run ALL steps on ALL my Arc servers. Show detailed results in a summary table." --allow-all-tools --model gpt-5.4-mini
    echo ""
  done
```

## RBAC Requirements

See [docs/rbac-requirements.md](docs/rbac-requirements.md) for the minimum Azure roles needed.

Quick check — if these commands work, you have enough permissions:
```bash
az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | take 1" -o table
az monitor log-analytics query --workspace YOUR_WORKSPACE_ID --analytics-query "Heartbeat | take 1" -o table
```

## Detailed Per-Scenario Guides

For step-by-step walkthroughs with expected output:
- [Scenario A: Health Check](docs/implementations/scenario-a-health-check/option-c-copilot-cli.md)
- [Scenario B: Alert Triage](docs/implementations/scenario-b-alert-triage/option-c-copilot-cli.md)
- [Scenario C: Security Agent](docs/implementations/scenario-c-security-troubleshooting/option-c-copilot-cli.md)
- [Scenario D: Compliance](docs/implementations/scenario-d-compliance/option-c-copilot-cli.md)
- [Scenario E: Patching](docs/implementations/scenario-e-patching/option-c-copilot-cli.md)
- [Scenario F: CMDB Sync](docs/implementations/scenario-f-cmdb-sync/option-c-copilot-cli.md)
- [Scenario G: Snapshot Cleanup](docs/implementations/scenario-g-snapshot-cleanup/option-c-copilot-cli.md)
- [Scenario H: Ticket-Driven Remediation](docs/demos/scenario-h-ticket-remediation.md) *(requires GLPI)*

## Other AI Tier Options

Copilot CLI is one of 4 options. See [docs/ai-tier-options.md](docs/ai-tier-options.md) for:
- Option 0: Azure SRE Agent (recommended for production)
- Option A: Microsoft Agent Framework
- Option B: Foundry Agent Service
- Option C: GitHub Copilot CLI (this guide)

