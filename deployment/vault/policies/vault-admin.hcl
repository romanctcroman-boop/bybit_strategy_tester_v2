# =============================================================================
# Vault Admin Policy
# =============================================================================
# Full access policy for administrators.
# Apply with: vault policy write vault-admin vault/policies/vault-admin.hcl

# Full access to all secrets
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage auth methods
path "auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

# Manage policies
path "sys/policies/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage secrets engines
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# View system health
path "sys/health" {
  capabilities = ["read", "sudo"]
}

# View audit logs
path "sys/audit" {
  capabilities = ["read", "list"]
}

# Manage tokens
path "auth/token/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
