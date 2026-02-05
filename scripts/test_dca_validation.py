"""Test DCA pyramiding validation warnings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.backtesting.engine_selector import get_engine

print("="*60)
print("Testing DCA Pyramiding Validation")
print("="*60)

# Test 1: DCA with pyramiding=1 (should WARN)
print("\n[Test 1] DCA with pyramiding=1:")
engine = get_engine(strategy_type='dca', pyramiding=1, max_entries=5)
print(f"Engine: {engine.name}")

# Test 2: DCA with pyramiding < max_entries (should WARN)
print("\n[Test 2] DCA with pyramiding=3, max_entries=5:")
engine = get_engine(strategy_type='dca', pyramiding=3, max_entries=5)
print(f"Engine: {engine.name}")

# Test 3: DCA with pyramiding >= max_entries (should OK)
print("\n[Test 3] DCA with pyramiding=5, max_entries=5:")
engine = get_engine(strategy_type='dca', pyramiding=5, max_entries=5)
print(f"Engine: {engine.name}")

# Test 4: Simple strategy with pyramiding=1 (no warning)
print("\n[Test 4] RSI strategy with pyramiding=1:")
engine = get_engine(strategy_type='rsi', pyramiding=1)
print(f"Engine: {engine.name}")

# Test 5: Grid with pyramiding=1 (should WARN)
print("\n[Test 5] Grid strategy with pyramiding=1:")
engine = get_engine(strategy_type='grid', pyramiding=1)
print(f"Engine: {engine.name}")

print("\n" + "="*60)
print("✅ Validation tests completed!")
print("="*60)
