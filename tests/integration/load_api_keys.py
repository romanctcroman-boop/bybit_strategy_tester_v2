"""
Utility to load and decrypt all API keys for integration testing

Loads:
- 8 DeepSeek API keys (DEEPSEEK_API_KEY, DEEPSEEK_API_KEY_1..7)
- 4 Perplexity API keys (PERPLEXITY_API_KEY, PERPLEXITY_API_KEY_1..3)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from automation.task2_key_manager.key_manager import KeyManager


def load_all_api_keys():
    """Load and decrypt all API keys
    
    Returns:
        Tuple of (deepseek_keys, perplexity_keys)
    """
    # Get master encryption key from env
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    if not master_key:
        raise ValueError("MASTER_ENCRYPTION_KEY not found in environment")
    
    # Initialize KeyManager
    key_manager = KeyManager()
    key_manager.initialize_encryption(master_key)
    
    # Load encrypted secrets from project root
    secrets_file = Path(__file__).parent.parent.parent / "encrypted_secrets.json"
    if not secrets_file.exists():
        raise FileNotFoundError(f"encrypted_secrets.json not found at {secrets_file}")
    
    if not key_manager.load_keys(str(secrets_file)):
        raise RuntimeError("Failed to load encrypted secrets")
    
    # Load DeepSeek keys
    deepseek_keys = []
    
    # Main key
    main_key = key_manager.get_key("DEEPSEEK_API_KEY")
    if main_key:
        deepseek_keys.append({
            "id": "deepseek-key-main",
            "api_key": main_key,
            "weight": 1.0
        })
    
    # Additional 7 keys
    for i in range(1, 8):
        key = key_manager.get_key(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_keys.append({
                "id": f"deepseek-key-{i}",
                "api_key": key,
                "weight": 1.0
            })
    
    # Load Perplexity keys
    perplexity_keys = []
    
    # Main key
    main_key = key_manager.get_key("PERPLEXITY_API_KEY")
    if main_key:
        perplexity_keys.append({
            "id": "perplexity-key-main",
            "api_key": main_key,
            "weight": 1.0
        })
    
    # Additional 3 keys
    for i in range(1, 4):
        key = key_manager.get_key(f"PERPLEXITY_API_KEY_{i}")
        if key:
            perplexity_keys.append({
                "id": f"perplexity-key-{i}",
                "api_key": key,
                "weight": 1.0
            })
    
    return deepseek_keys, perplexity_keys


if __name__ == "__main__":
    # Test loading
    from dotenv import load_dotenv
    
    # Load .env from mcp-server FIRST
    env_path = Path(__file__).parent.parent.parent / "mcp-server" / ".env"
    print(f"Loading .env from: {env_path}")
    load_dotenv(env_path)
    
    # Verify key loaded
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    if not master_key:
        print("❌ MASTER_ENCRYPTION_KEY not loaded from .env")
        print(f"   Tried path: {env_path}")
        print(f"   File exists: {env_path.exists()}")
        sys.exit(1)
    
    try:
        deepseek, perplexity = load_all_api_keys()
        print(f"✅ Loaded {len(deepseek)} DeepSeek keys")
        print(f"✅ Loaded {len(perplexity)} Perplexity keys")
        
        # Print key IDs (not the actual keys!)
        print("\nDeepSeek key IDs:")
        for key in deepseek:
            print(f"  - {key['id']}")
        
        print("\nPerplexity key IDs:")
        for key in perplexity:
            print(f"  - {key['id']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
