# Infrastructure

Bicep IaC for the ops automation solution.

## Resources Deployed

| Resource | Name Pattern | Purpose |
|---|---|---|
| Log Analytics Workspace | `law-opsauto-{env}` | Telemetry, KQL queries, monitoring |
| Application Insights | `ai-opsauto-{env}` | Application telemetry |
| Storage Account | `stopsauto{env}` | Script artifacts and logs |
| Key Vault | `kv-opsauto-{env}` | Secrets (GLPI tokens, API keys) |

## Deployment

### Prerequisites
- Azure CLI installed and logged in (`az login`)
- Bicep CLI or Azure CLI with Bicep support (`az bicep install`)
- Contributor access on the target subscription

### Deploy

```bash
chmod +x infra/deploy.sh
./infra/deploy.sh <resource-group-name> [dev|staging|prod] [eastus]
```

### Post-Deployment Configuration

1. **Secrets**: Store GLPI credentials and SRE Agent webhook in Key Vault.

2. **Arc RBAC**: Grant appropriate identities `Azure Arc Machine Contributor` on the ArcBox resource group:
   ```bash
   az role assignment create \
     --assignee <principal-id> \
     --role "Azure Arc Machine Contributor" \
     --scope /subscriptions/<sub>/resourceGroups/<arcbox-rg>
   ```

3. **Defender RBAC**: Grant `Security Reader` on the subscription:
   ```bash
   az role assignment create \
     --assignee <principal-id> \
     --role "Security Reader" \
     --scope /subscriptions/<sub>
   ```
