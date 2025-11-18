"""
Universal API Keys Loader for Integration Tests

Tries to load encrypted keys from encrypted_secrets.json,
falls back to plaintext keys from mcp-server/.env if decryption fails.

Usage:
    from tests.integration.api_keys_loader import load_deepseek_keys, load_perplexity_keys
    
    deepseek_keys = load_deepseek_keys()  # Returns list of dicts with id, api_key, weight
    perplexity_keys = load_perplexity_keys()
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Try to import KeyManager for encrypted keys
try:
    from automation.task2_key_manager.key_manager import KeyManager
    KEY_MANAGER_AVAILABLE = True
except ImportError:
    KEY_MANAGER_AVAILABLE = False

# Load environment variables
env_path = Path(__file__).parent.parent.parent / "mcp-server" / ".env"
load_dotenv(env_path)


def _try_load_encrypted_keys() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Try to load encrypted keys from encrypted_secrets.json
    
    Returns:
        (deepseek_keys, perplexity_keys) - both as lists of dicts
        Returns ([], []) if decryption fails
    """
    if not KEY_MANAGER_AVAILABLE:
        return [], []
    
    secrets_file = Path(__file__).parent.parent.parent / "encrypted_secrets.json"
    if not secrets_file.exists():
        return [], []
    
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    if not master_key:
        return [], []
    
    try:
        # Initialize KeyManager
        key_manager = KeyManager()
        if not key_manager.initialize_encryption(master_key):
            return [], []
        
        # Load encrypted secrets
        if not key_manager.load_keys(str(secrets_file)):
            return [], []
        
        # Load DeepSeek keys (main + _1 through _7)
        deepseek_keys = []
        
        # Try main key
        try:
            api_key = key_manager.get_key("DEEPSEEK_API_KEY")
            if api_key and api_key.startswith("sk-"):
                deepseek_keys.append({
                    "id": "deepseek-key-1",
                    "api_key": api_key,
                    "weight": 1.0
                })
        except Exception:
            pass
        
        # Try keys _1 through _7
        for i in range(1, 8):
            try:
                api_key = key_manager.get_key(f"DEEPSEEK_API_KEY_{i}")
                if api_key and api_key.startswith("sk-"):
                    deepseek_keys.append({
                        "id": f"deepseek-key-{i+1}",
                        "api_key": api_key,
                        "weight": 1.0
                    })
            except Exception:
                pass
        
        # Load Perplexity keys (main + _1 through _3)
        perplexity_keys = []
        
        # Try main key
        try:
            api_key = key_manager.get_key("PERPLEXITY_API_KEY")
            if api_key and api_key.startswith("pplx-"):
                perplexity_keys.append({
                    "id": "perplexity-key-1",
                    "api_key": api_key,
                    "weight": 1.0
                })
        except Exception:
            pass
        
        # Try keys _1 through _3
        for i in range(1, 4):
            try:
                api_key = key_manager.get_key(f"PERPLEXITY_API_KEY_{i}")
                if api_key and api_key.startswith("pplx-"):
                    perplexity_keys.append({
                        "id": f"perplexity-key-{i+1}",
                        "api_key": api_key,
                        "weight": 1.0
                    })
            except Exception:
                pass
        
        return deepseek_keys, perplexity_keys
    
    except Exception as e:
        print(f"⚠️ Failed to load encrypted keys: {e}")
        return [], []


def _load_plaintext_keys() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load plaintext keys from mcp-server/.env as fallback
    
    Returns:
        (deepseek_keys, perplexity_keys) - both as lists with single key each
    """
    deepseek_keys = []
    perplexity_keys = []
    
    # Load DeepSeek key
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        deepseek_keys.append({
            "id": "deepseek-key-1",
            "api_key": deepseek_key,
            "weight": 1.0
        })
    
    # Load Perplexity key
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    if perplexity_key:
        perplexity_keys.append({
            "id": "perplexity-key-1",
            "api_key": perplexity_key,
            "weight": 1.0
        })
    
    return deepseek_keys, perplexity_keys


def load_deepseek_keys() -> List[Dict[str, Any]]:
    """
    Load all available DeepSeek API keys
    
    Tries encrypted_secrets.json first, falls back to .env
    
    Returns:
        List of dicts with format: {"id": str, "api_key": str, "weight": float}
        Returns 1-8 keys depending on availability
    """
    # Try encrypted keys first
    deepseek_keys, _ = _try_load_encrypted_keys()
    
    if deepseek_keys:
        print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys from encrypted_secrets.json")
        return deepseek_keys
    
    # Fallback to plaintext
    deepseek_keys, _ = _load_plaintext_keys()
    
    if deepseek_keys:
        print(f"⚠️ Using {len(deepseek_keys)} plaintext DeepSeek key(s) from .env (encrypted keys unavailable)")
    else:
        print(f"❌ No DeepSeek keys available!")
    
    return deepseek_keys


def load_perplexity_keys() -> List[Dict[str, Any]]:
    """
    Load all available Perplexity API keys
    
    Tries encrypted_secrets.json first, falls back to .env
    
    Returns:
        List of dicts with format: {"id": str, "api_key": str, "weight": float}
        Returns 1-4 keys depending on availability
    """
    # Try encrypted keys first
    _, perplexity_keys = _try_load_encrypted_keys()
    
    if perplexity_keys:
        print(f"✅ Loaded {len(perplexity_keys)} Perplexity keys from encrypted_secrets.json")
        return perplexity_keys
    
    # Fallback to plaintext
    _, perplexity_keys = _load_plaintext_keys()
    
    if perplexity_keys:
        print(f"⚠️ Using {len(perplexity_keys)} plaintext Perplexity key(s) from .env (encrypted keys unavailable)")
    else:
        print(f"❌ No Perplexity keys available!")
    
    return perplexity_keys


def get_keys_info() -> dict:
    """
    Get information about available keys
    
    Returns:
        Dict with counts and source info
    """
    deepseek_keys = load_deepseek_keys()
    perplexity_keys = load_perplexity_keys()
    
    # Determine source
    encrypted_deepseek, _ = _try_load_encrypted_keys()
    source = "encrypted" if encrypted_deepseek else "plaintext (.env)"
    
    return {
        "deepseek_count": len(deepseek_keys),
        "perplexity_count": len(perplexity_keys),
        "source": source,
        "multi_key_testing": len(deepseek_keys) > 1 or len(perplexity_keys) > 1
    }


if __name__ == "__main__":
    print("\n🔑 API Keys Loader Test\n")
    
    info = get_keys_info()
    print(f"Source: {info['source']}")
    print(f"DeepSeek keys: {info['deepseek_count']}")
    print(f"Perplexity keys: {info['perplexity_count']}")
    print(f"Multi-key testing enabled: {info['multi_key_testing']}")
    
    if info['multi_key_testing']:
        print("\n✅ Ready for parallel/multi-threaded testing with key rotation!")
    else:
        print("\n⚠️ Only single key available. Key rotation tests will be limited.")
        print("   To enable full testing, fix encrypted_secrets.json decryption.")
