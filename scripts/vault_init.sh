#!/bin/bash
# =============================================================================
# Vault Initialization Script
# =============================================================================
# This script initializes Vault with the required secrets engines, policies,
# and initial secrets for the Bybit Strategy Tester application.
#
# Prerequisites:
#   - Vault is running and unsealed
#   - VAULT_ADDR environment variable is set
#   - VAULT_TOKEN environment variable is set (root token)
#
# Usage:
#   export VAULT_ADDR="http://localhost:8200"
#   export VAULT_TOKEN="<root-token>"
#   ./vault_init.sh
# =============================================================================

set -e

echo "=============================================="
echo "Vault Initialization for Bybit Strategy Tester"
echo "=============================================="

# Check prerequisites
if [ -z "$VAULT_ADDR" ]; then
    echo "ERROR: VAULT_ADDR not set. Run: export VAULT_ADDR=http://localhost:8200"
    exit 1
fi

if [ -z "$VAULT_TOKEN" ]; then
    echo "ERROR: VAULT_TOKEN not set. Run: export VAULT_TOKEN=<root-token>"
    exit 1
fi

echo "Vault Address: $VAULT_ADDR"

# Check Vault status
echo ""
echo "Checking Vault status..."
vault status || {
    echo "ERROR: Cannot connect to Vault or Vault is sealed"
    exit 1
}

# Enable KV secrets engine v2
echo ""
echo "Enabling KV secrets engine v2..."
vault secrets enable -path=secret kv-v2 2>/dev/null || echo "KV engine already enabled"

# Create policies
echo ""
echo "Creating policies..."

POLICY_DIR="$(dirname "$0")/../deployment/vault/policies"

if [ -f "$POLICY_DIR/bybit-app.hcl" ]; then
    vault policy write bybit-app "$POLICY_DIR/bybit-app.hcl"
    echo "  - bybit-app policy created"
fi

if [ -f "$POLICY_DIR/vault-admin.hcl" ]; then
    vault policy write vault-admin "$POLICY_DIR/vault-admin.hcl"
    echo "  - vault-admin policy created"
fi

# Create initial secrets structure
echo ""
echo "Creating initial secrets structure..."

# Bybit API credentials (placeholder)
vault kv put secret/bybit/credentials \
    api_key="YOUR_BYBIT_API_KEY" \
    api_secret="YOUR_BYBIT_API_SECRET" \
    testnet="true"
echo "  - secret/bybit/credentials created (UPDATE WITH REAL VALUES!)"

# Database credentials
vault kv put secret/database/app \
    url="postgresql://user:password@localhost:5432/bybit_tester" \
    pool_size="5" \
    pool_recycle="1800"
echo "  - secret/database/app created"

# Redis credentials
vault kv put secret/redis/app \
    url="redis://localhost:6379/0" \
    password=""
echo "  - secret/redis/app created"

# MLflow credentials
vault kv put secret/mlflow/app \
    tracking_uri="http://localhost:5000" \
    artifact_location="/mlflow/artifacts"
echo "  - secret/mlflow/app created"

# Create app token
echo ""
echo "Creating application token..."
APP_TOKEN=$(vault token create -policy=bybit-app -ttl=720h -format=json | jq -r '.auth.client_token')
echo "  - App token created (valid for 30 days)"
echo ""
echo "=============================================="
echo "APPLICATION TOKEN (save this securely!):"
echo "$APP_TOKEN"
echo "=============================================="

echo ""
echo "Initialization complete!"
echo ""
echo "Next steps:"
echo "1. Update secrets with real values:"
echo "   vault kv put secret/bybit/credentials api_key=<key> api_secret=<secret>"
echo ""
echo "2. Set environment variable in your app:"
echo "   export VAULT_TOKEN=$APP_TOKEN"
echo "   export VAULT_ADDR=$VAULT_ADDR"
echo ""
echo "3. Or update .env file:"
echo "   VAULT_TOKEN=$APP_TOKEN"
echo "   VAULT_ADDR=$VAULT_ADDR"
