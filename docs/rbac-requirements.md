# RBAC Requirements

Minimum Azure roles needed to execute all skills across the 4 AI tier options.

## Per-Skill Azure Operations

| Skill | Azure Operations | Read | Write |
|---|---|---|---|
| **Health Check** | Resource Graph, Log Analytics query, Arc Run Commands | ✅ | ✅ (run-command) |
| **Security Agent** | Resource Graph, Log Analytics query, Arc Extensions list, Arc Run Commands | ✅ | ✅ (run-command, service restart) |
| **Compliance** | Resource Graph, Defender regulatory compliance, Policy state, Arc Run Commands | ✅ | ✅ (run-command for spot-checks) |
| **Patch Validation** | Resource Graph (patch assessment), Log Analytics, Arc Run Commands | ✅ | ✅ (run-command for pre/post checks) |
| **VMware BAU** | Resource Graph, Azure VM Run Command, Arc Run Commands, Log Analytics | ✅ | ✅ (checkpoint operations) |

## Minimum Azure RBAC Roles

| Role | Scope | What It Enables | Required By |
|---|---|---|---|
| **Reader** | Subscription or RG | List resources, view properties, read config | All skills |
| **Log Analytics Reader** | Workspace(s) | KQL queries for Perf, Heartbeat, SecurityBaseline | Health Check, Security, Patch, VMware |
| **Security Reader** | Subscription | Defender for Cloud compliance standards, recommendations | Compliance |
| **Azure Connected Machine Resource Administrator** | RG with Arc servers | Execute Run Commands on Arc-enrolled servers | All skills (for live diagnostics) |
| **Virtual Machine Contributor** | RG with Azure VMs | Execute Run Commands on Azure VMs (e.g., Hyper-V host) | VMware BAU only |
| **Resource Policy Reader** | Subscription | Query Azure Policy compliance state | Compliance |

> **Note:** If you only need read-only investigation (no Arc Run Commands), **Reader** + **Log Analytics Reader** + **Security Reader** is sufficient for most skills. Arc Run Commands require the write-capable **Azure Connected Machine Resource Administrator** role.

## RBAC Setup Per AI Tier Option

### Option 0: Azure SRE Agent

The SRE Agent uses a **managed identity**. Assign roles to the managed identity:

```bash
# Find managed identity
AGENT_MI=$(az containerapp show -n <sre-agent-app> -g <rg> --query "identity.principalId" -o tsv)

# Assign roles on each resource group containing Arc servers
az role assignment create --assignee $AGENT_MI --role "Reader" --scope /subscriptions/<sub>/resourceGroups/<rg>
az role assignment create --assignee $AGENT_MI --role "Log Analytics Reader" --scope /subscriptions/<sub>/resourceGroups/<rg>
az role assignment create --assignee $AGENT_MI --role "Azure Connected Machine Resource Administrator" --scope /subscriptions/<sub>/resourceGroups/<rg>
az role assignment create --assignee $AGENT_MI --role "Security Reader" --scope /subscriptions/<sub>
az role assignment create --assignee $AGENT_MI --role "Resource Policy Reader" --scope /subscriptions/<sub>
```

Or simpler: add resource groups as **managed resource groups** in the SRE Agent portal — this auto-assigns Reader + Log Analytics Reader + Monitoring Reader. Then manually add the write roles.

| Setup method | Roles auto-assigned | Roles to add manually |
|---|---|---|
| Managed resource groups (portal) | Reader, Log Analytics Reader, Monitoring Reader | Azure Connected Machine Resource Administrator, Security Reader, Resource Policy Reader |
| Manual RBAC (az CLI) | None | All 6 roles |

### Option A: Microsoft Agent Framework

The self-hosted agent uses either a **service principal** or **managed identity** (if hosted on Azure). Same roles as SRE Agent:

```bash
# If using service principal
SP_ID=$(az ad sp show --id <app-id> --query "id" -o tsv)
az role assignment create --assignee $SP_ID --role "Reader" --scope /subscriptions/<sub>
# ... same 6 roles as above
```

If running locally during development, the agent inherits your `az login` credentials — same as Copilot CLI.

### Option B: Foundry Agent Service

Foundry agents use a **managed identity** from the Foundry project. Assign roles similarly:

```bash
FOUNDRY_MI=$(az cognitiveservices account show -n <foundry-account> -g <rg> --query "identity.principalId" -o tsv)
# ... same 6 roles
```

### Option C: GitHub Copilot CLI

**No service identity needed.** Copilot CLI runs as YOUR user. You need these roles on your own Azure AD account:

```bash
# Check your current roles
az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv) --query "[].{Role:roleDefinitionName, Scope:scope}" -o table
```

**Minimum roles for your user account:**

| Role | Scope | How to get it |
|---|---|---|
| **Reader** | Subscription(s) | Usually already assigned |
| **Log Analytics Reader** | Workspace(s) or subscription | Ask your admin or self-assign if Owner |
| **Security Reader** | Subscription | Ask your admin |
| **Azure Connected Machine Resource Administrator** | RG(s) with Arc servers | Ask your admin — this is the key one for Run Commands |
| **Resource Policy Reader** | Subscription | Usually included with Reader, but verify |
| **Virtual Machine Contributor** | RG(s) with Azure VMs | Only if running VMware BAU skill |

> **Quick check:** If you can run these commands successfully, you have enough permissions:
> ```bash
> # Can you list Arc servers? (needs Reader)
> az graph query -q "Resources | where type == 'microsoft.hybridcompute/machines' | take 1" -o table
> 
> # Can you query Log Analytics? (needs Log Analytics Reader)
> az monitor log-analytics query --workspace <ID> --analytics-query "Heartbeat | take 1" -o table
> 
> # Can you run commands on Arc servers? (needs Connected Machine Resource Administrator)
> az connectedmachine run-command create -g <rg> --machine-name <server> --name test --location <loc> --script 'hostname' --async-execution true
> ```

## Comparison: RBAC Setup Effort

| Setup Step | SRE Agent | Agent Framework | Foundry Agent | Copilot CLI |
|---|---|---|---|---|
| **Identity type** | Managed identity (auto-created) | Service principal or managed identity | Managed identity | Your user account |
| **Roles to assign** | 6 roles on managed identity | 6 roles on SP/MI | 6 roles on MI | 0 (if you already have Reader + LA Reader) |
| **Who assigns** | Azure admin | Azure admin | Azure admin | Already done (your existing access) |
| **Effort** | ~15 min (or use managed RGs) | ~15 min | ~15 min | **~0 min** (verify existing access) |
| **Least privilege risk** | Low (dedicated identity) | Low (dedicated identity) | Low (dedicated identity) | ⚠️ Medium (uses your full permissions) |
| **Audit trail** | Agent identity in logs | SP/MI identity in logs | MI identity in logs | Your user identity in logs |

## GLPI Permissions (Non-Azure)

All options need GLPI OAuth2 credentials if using the GLPI ITSM/CMDB integration:

| Credential | Where to get it | Used by |
|---|---|---|
| **Client ID** | GLPI → Setup → OAuth Clients | All options (ticket creation) |
| **Client Secret** | GLPI → Setup → OAuth Clients | All options |
| **GLPI admin password** | Set during GLPI setup | OAuth2 password grant |
