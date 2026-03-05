"""
QWEN Configuration Test
Проверка настроек модели для трейдинга
"""

import os
import sys

# Load .env file
from dotenv import load_dotenv

load_dotenv("d:/bybit_strategy_tester_v2/.env")

print("=" * 60)
print("QWEN CONFIGURATION TEST")
print("=" * 60)

# First check system environment (takes precedence over .env)
print("\n1. System Environment Variables (highest priority):")
print(f"   QWEN_MODEL:          {os.getenv('QWEN_MODEL', 'NOT SET')}")
print(f"   QWEN_MODEL_FAST:     {os.getenv('QWEN_MODEL_FAST', 'NOT SET')}")
print(f"   QWEN_TEMPERATURE:    {os.getenv('QWEN_TEMPERATURE', 'NOT SET')}")
print(f"   QWEN_ENABLE_THINKING:{os.getenv('QWEN_ENABLE_THINKING', 'NOT SET')}")
print(f"   QWEN_API_KEY:        {'SET' if os.getenv('QWEN_API_KEY') else 'NOT SET'}")

# Load .env file and show values
from dotenv import load_dotenv

load_dotenv("d:/bybit_strategy_tester_v2/.env", override=False)

print("\n2. .env File Configuration (if not overridden by system):")
env_model = os.getenv("QWEN_MODEL", "NOT SET")
env_model_fast = os.getenv("QWEN_MODEL_FAST", "NOT SET")
env_temp = os.getenv("QWEN_TEMPERATURE", "NOT SET")
env_thinking = os.getenv("QWEN_ENABLE_THINKING", "NOT SET")
print(f"   QWEN_MODEL:          {env_model}")
print(f"   QWEN_MODEL_FAST:     {env_model_fast}")
print(f"   QWEN_TEMPERATURE:    {env_temp}")
print(f"   QWEN_ENABLE_THINKING:{env_thinking}")

# Check config validator
print("\n3. AgentConfig (from config_validator):")
sys.path.insert(0, "d:/bybit_strategy_tester_v2")
from backend.agents.config_validator import get_agent_config

config = get_agent_config()
print(f"   qwen_model:          {config.qwen_model}")
print(f"   qwen_base_url:       {config.qwen_base_url}")

# Validate trading configuration
print("\n4. Trading Configuration Validation:")
expected_model = "qwen3-max"
actual_model = os.getenv("QWEN_MODEL")

if actual_model == expected_model:
    print(f"   [OK] Model set to {expected_model} for trading")
else:
    print(f"   [WARN] Expected {expected_model}, got {actual_model}")
    print("   [INFO] You may need to restart the server")

thinking_enabled = os.getenv("QWEN_ENABLE_THINKING", "false").lower() in ("true", "1", "yes")
if thinking_enabled:
    print("   [OK] Thinking mode ENABLED for complex analysis")
else:
    print("   [INFO] Thinking mode disabled (set QWEN_ENABLE_THINKING=true to enable)")

temperature = float(os.getenv("QWEN_TEMPERATURE", "0.4"))
if temperature <= 0.3:
    print(f"   [OK] Temperature={temperature} (good for trading signals)")
else:
    print(f"   [INFO] Temperature={temperature} (consider 0.3 for trading)")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
