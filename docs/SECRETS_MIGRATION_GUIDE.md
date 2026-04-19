# Secrets Migration Guide: Environment Variables to HashiCorp Vault

> This guide describes how to migrate from environment variable-based secrets
> to HashiCorp Vault for secure secrets management.

---

## Overview

The Bybit Strategy Tester supports two methods for managing secrets:

1. **Environment Variables** (default, simple setup)
2. **HashiCorp Vault** (recommended for production)

The VaultClient automatically falls back to environment variables when Vault
is unavailable, making migration seamless.

## Current Environment Variables

| Variable              | Purpose             | Vault Path                 |
| --------------------- | ------------------- | -------------------------- |
| `BYBIT_API_KEY`       | Bybit API key       | `secret/bybit/credentials` |
| `BYBIT_API_SECRET`    | Bybit API secret    | `secret/bybit/credentials` |
| `DATABASE_URL`        | Database connection | `secret/database/app`      |
| `REDIS_URL`           | Redis connection    | `secret/redis/app`         |
| `MLFLOW_TRACKING_URI` | MLflow server       | `secret/mlflow/app`        |

## Migration Steps

### Step 1: Deploy Vault

```bash
# Start Vault using Docker Compose
cd deployment
docker-compose -f docker-compose.vault.yml up -d vault

# Wait for Vault to start
sleep 5
docker logs bybit-vault
```

### Step 2: Initialize Vault

```bash
# Initialize (SAVE THE KEYS!)
docker exec -it bybit-vault vault operator init -key-shares=5 -key-threshold=3

# Output will be like:
# Unseal Key 1: xxxx
# Unseal Key 2: xxxx
# Unseal Key 3: xxxx
# Unseal Key 4: xxxx
# Unseal Key 5: xxxx
# Initial Root Token: hvs.xxxx

# CRITICAL: Save these keys securely! You need 3 keys to unseal Vault.
```

### Step 3: Unseal Vault

```bash
# Unseal with 3 different keys
docker exec -it bybit-vault vault operator unseal <key1>
docker exec -it bybit-vault vault operator unseal <key2>
docker exec -it bybit-vault vault operator unseal <key3>

# Verify Vault is unsealed
docker exec -it bybit-vault vault status
```

### Step 4: Run Initialization Script

```bash
# Set environment variables
export VAULT_ADDR="http://localhost:8200"
export VAULT_TOKEN="<root-token>"

# Run init script
./scripts/vault_init.sh
```

### Step 5: Update Secrets

```bash
# Update Bybit credentials
docker exec -it bybit-vault vault kv put secret/bybit/credentials \
    api_key="YOUR_REAL_API_KEY" \
    api_secret="YOUR_REAL_API_SECRET" \
    testnet="false"

# Update database URL
docker exec -it bybit-vault vault kv put secret/database/app \
    url="postgresql://user:password@host:5432/db" \
    pool_size="10"

# Verify
docker exec -it bybit-vault vault kv get secret/bybit/credentials
```

### Step 6: Configure Application

Add to your `.env` file:

```env
# Vault Configuration
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=<app-token-from-init-script>
VAULT_NAMESPACE=  # Optional, for enterprise Vault

# These can be removed once Vault is working
# BYBIT_API_KEY=...
# BYBIT_API_SECRET=...
```

### Step 7: Verify Integration

```python
from backend.core.vault_client import VaultClient, get_bybit_credentials

# Test connection
client = VaultClient()
print(f"Vault available: {client.is_available}")

# Get credentials
creds = get_bybit_credentials()
print(f"Got credentials: {creds is not None}")
```

## Rollback Procedure

If something goes wrong, the application automatically falls back to
environment variables. Simply:

1. Set the old environment variables in `.env`
2. Remove or unset `VAULT_ADDR` and `VAULT_TOKEN`
3. Restart the application

## Security Best Practices

### Token Management

- **Never commit tokens to git**
- Rotate application tokens every 30 days
- Use short TTLs for development tokens
- Store unseal keys in separate locations

### Network Security

- Run Vault in a private network
- Use TLS in production (configure in vault config)
- Restrict access with firewall rules
- Enable audit logging

### Backup Strategy

```bash
# Backup Vault data
docker exec bybit-vault vault operator raft snapshot save /vault/backup.snap
docker cp bybit-vault:/vault/backup.snap ./vault-backup-$(date +%Y%m%d).snap
```

## Troubleshooting

### Vault is sealed

```bash
# Unseal with threshold keys
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

### Cannot connect to Vault

```bash
# Check Vault is running
docker ps | grep vault

# Check Vault logs
docker logs bybit-vault

# Verify network
curl http://localhost:8200/v1/sys/health
```

### Permission denied

```bash
# Check token policies
vault token lookup

# Verify policy allows access
vault policy read bybit-app
```

### Application not reading from Vault

```python
# Debug in Python
from backend.core.vault_client import VaultClient
client = VaultClient()
print(f"URL: {client.url}")
print(f"Available: {client.is_available}")
print(f"Token set: {bool(client.token)}")
```

## Monitoring

### Health Check

```bash
# Check Vault health
curl -s http://localhost:8200/v1/sys/health | jq

# Expected output when healthy:
# {
#   "initialized": true,
#   "sealed": false,
#   "standby": false,
#   ...
# }
```

### Prometheus Metrics

Vault exposes Prometheus metrics at `/v1/sys/metrics` when configured.

## Production Recommendations

1. **High Availability**: Deploy 3+ Vault nodes with Raft storage
2. **Auto-unseal**: Use AWS KMS, Azure Key Vault, or GCP KMS
3. **TLS**: Enable TLS for all Vault communication
4. **Audit**: Enable file or syslog audit device
5. **Rotation**: Implement automatic secret rotation
6. **Backup**: Schedule daily snapshots
