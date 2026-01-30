# =============================================================================
# Bybit Strategy Tester - Vault Policy
# =============================================================================
# This policy grants access to secrets for the backtest application.
# Apply with: vault policy write bybit-app vault/policies/bybit-app.hcl

# Allow reading API credentials
path "secret/data/bybit/*" {
  capabilities = ["read", "list"]
}

# Allow reading database credentials
path "secret/data/database/*" {
  capabilities = ["read", "list"]
}

# Allow reading Redis credentials
path "secret/data/redis/*" {
  capabilities = ["read", "list"]
}

# Allow reading ML service credentials
path "secret/data/mlflow/*" {
  capabilities = ["read", "list"]
}

# Allow listing secrets (for discovery)
path "secret/metadata/*" {
  capabilities = ["list"]
}

# Deny write access to all secrets (read-only for app)
path "secret/data/*" {
  capabilities = ["deny"]
}
