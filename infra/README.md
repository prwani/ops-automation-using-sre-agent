# Infrastructure

Bicep IaC for the ops automation solution.

## Resources Deployed

| Resource | Name Pattern | Purpose |
|---|---|---|
| Log Analytics Workspace | `law-opsauto-{env}` | Telemetry, KQL queries, monitoring |
| Application Insights | `ai-opsauto-{env}` | Function App + API telemetry |
| Storage Account | `stospautodevfn` | Azure Functions storage |
| Key Vault | `kv-opsauto-{env}` | Secrets (GLPI tokens, API keys) |
| Cosmos DB (serverless) | `cosmos-opsauto-{env}` | Runs, feedback, memories |
| App Service Plan (B1 Linux) | `asp-opsauto-{env}` | Portal API hosting |
| App Service | `app-opsauto-{env}-api` | FastAPI portal backend |
| Function App (Consumption) | `func-opsauto-{env}` | Timer-triggered automation |

## RBAC Assignments

- Function App managed identity → Cosmos DB Built-in Data Contributor
- Function App managed identity → Key Vault Secrets User
- Portal API managed identity → Cosmos DB Built-in Data Contributor

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

1. **Arc RBAC**: Grant Function App managed identity `Azure Arc Machine Contributor` on the ArcBox resource group:
   ```bash
   az role assignment create \
     --assignee <function-app-principal-id> \
     --role "Azure Arc Machine Contributor" \
     --scope /subscriptions/<sub>/resourceGroups/<arcbox-rg>
   ```

2. **Defender RBAC**: Grant Function App managed identity `Security Reader` on the subscription:
   ```bash
   az role assignment create \
     --assignee <function-app-principal-id> \
     --role "Security Reader" \
     --scope /subscriptions/<sub>
   ```

3. **Secrets**: Store GLPI credentials and SRE Agent webhook in Key Vault, then reference from Function App settings.

4. **Deploy Functions**:
   ```bash
   cd functions/
   func azure functionapp publish func-opsauto-dev
   ```
