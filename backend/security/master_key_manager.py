"""
Master Key Manager - Handles master encryption key retrieval
Supports multiple environments: development, staging, production
"""
import os
from typing import Optional
from .crypto import CryptoManager


class MasterKeyManager:
    """
    Manages master encryption key retrieval based on environment.
    
    Environments:
    - development: .env file (MASTER_ENCRYPTION_KEY)
    - staging: HashiCorp Vault (future)
    - production: AWS Secrets Manager (future)
    """
    
    def __init__(self):
        self.env = os.getenv("ENVIRONMENT", "development")
        self._cached_key: Optional[str] = None
    
    def get_master_key(self) -> str:
        """
        Get master encryption key based on environment.
        
        Returns:
            Master key string
            
        Raises:
            ValueError: If key not found or unavailable
        """
        if self._cached_key:
            return self._cached_key
        
        if self.env == "development":
            key = self._get_from_env()
        elif self.env == "production":
            key = self._get_from_aws_secrets()
        elif self.env == "staging":
            key = self._get_from_vault()
        else:
            raise ValueError(f"Unknown environment: {self.env}")
        
        self._cached_key = key
        return key
    
    def _get_from_env(self) -> str:
        """Get master key from environment variable (.env file)"""
        key = os.getenv("MASTER_ENCRYPTION_KEY")
        
        if not key:
            raise ValueError(
                "MASTER_ENCRYPTION_KEY not set in environment.\n"
                "Please add it to .env file:\n"
                "  MASTER_ENCRYPTION_KEY=your-generated-key\n\n"
                "To generate a key:\n"
                "  openssl rand -base64 32\n"
                "  or\n"
                "  python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        
        return key
    
    def _get_from_aws_secrets(self) -> str:
        """
        Get master key from AWS Secrets Manager (production).
        
        Requires:
        - boto3 installed
        - AWS credentials configured
        - Secret: bybit-tester/master-key
        """
        try:
            import boto3
            
            session = boto3.Session()
            client = session.client('secretsmanager')
            
            response = client.get_secret_value(
                SecretId='bybit-tester/master-key'
            )
            
            return response['SecretString']
            
        except ImportError:
            raise ValueError(
                "boto3 not installed. Install with: pip install boto3"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to retrieve master key from AWS Secrets Manager: {e}"
            )
    
    def _get_from_vault(self) -> str:
        """
        Get master key from HashiCorp Vault (staging).
        
        Requires:
        - hvac installed
        - VAULT_URL and VAULT_TOKEN env vars
        - Secret path: bybit-tester/master-key
        """
        try:
            import hvac
            
            vault_url = os.getenv("VAULT_URL")
            vault_token = os.getenv("VAULT_TOKEN")
            
            if not vault_url or not vault_token:
                raise ValueError(
                    "VAULT_URL and VAULT_TOKEN must be set for staging environment"
                )
            
            client = hvac.Client(url=vault_url, token=vault_token)
            
            response = client.secrets.kv.v2.read_secret_version(
                path='bybit-tester/master-key'
            )
            
            return response['data']['data']['key']
            
        except ImportError:
            raise ValueError(
                "hvac not installed. Install with: pip install hvac"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to retrieve master key from Vault: {e}"
            )
    
    def create_crypto_manager(self) -> CryptoManager:
        """
        Create CryptoManager instance with master key.
        
        Returns:
            Initialized CryptoManager
        """
        master_key = self.get_master_key()
        return CryptoManager(master_key)
    
    def clear_cache(self):
        """Clear cached master key (useful for testing)"""
        self._cached_key = None


# Singleton instance
_master_key_manager = None


def get_master_key_manager() -> MasterKeyManager:
    """Get singleton MasterKeyManager instance"""
    global _master_key_manager
    if _master_key_manager is None:
        _master_key_manager = MasterKeyManager()
    return _master_key_manager
