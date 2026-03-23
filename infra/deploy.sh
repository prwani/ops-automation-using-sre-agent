#!/usr/bin/env bash
# Deploy the ops automation infrastructure to Azure
# Usage: ./infra/deploy.sh <resource-group> [environment] [location]
set -euo pipefail

RESOURCE_GROUP="${1:?Usage: $0 <resource-group> [environment] [location]}"
ENVIRONMENT="${2:-dev}"
LOCATION="${3:-eastus}"

echo "Deploying ops-automation infrastructure..."
echo "  Resource Group : $RESOURCE_GROUP"
echo "  Environment    : $ENVIRONMENT"
echo "  Location       : $LOCATION"
echo ""

# Create resource group if it doesn't exist
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none 2>/dev/null || true

# Deploy Bicep
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$(dirname "$0")/main.bicep" \
  --parameters environment="$ENVIRONMENT" location="$LOCATION" \
  --name "opsauto-$(date +%Y%m%d-%H%M%S)" \
  --output table

echo ""
echo "Deployment complete."
echo "Next steps:"
echo "  1. Deploy Azure Functions: func azure functionapp publish <function-app-name>"
echo "  2. Deploy Portal API: az webapp deploy --resource-group $RESOURCE_GROUP --name <api-app-name> --src-path portal-api/"
echo "  3. Configure GLPI_BASE_URL, GLPI_APP_TOKEN, GLPI_USER_TOKEN in Key Vault"
echo "  4. Set SRE_AGENT_WEBHOOK_URL in Function App settings"
