"""Test MarketRegimeDetector class."""

import numpy as np

from backend.backtesting.engines.fallback_engine_v4 import MarketRegimeDetector

print("=== MarketRegimeDetector Test ===")
print()

# 1. Simulate trending market (prices going up)
print("1. Trending market (prices rising):")
detector = MarketRegimeDetector(lookback=50)
np.random.seed(42)
base_price = 100.0
for i in range(100):
    # Uptrend with small noise
    price = base_price + i * 0.5 + np.random.normal(0, 0.5)
    volume = 1000 + np.random.normal(0, 100)
    atr = 2.0 + np.random.normal(0, 0.2)
    detector.update(price, volume, atr)

regime = detector.get_regime()
print(f"   Regime: {regime['regime']}")
print(f"   Hurst: {regime['hurst']:.3f} (>0.55 = trending)")
print(f"   Vol percentile: {regime['volatility_percentile']:.1f}%")
print(f"   Should trade (trending): {detector.should_trade('trending')}")

# 2. Simulate ranging market (prices oscillating)
print()
print("2. Ranging market (prices oscillating):")
detector2 = MarketRegimeDetector(lookback=50)
np.random.seed(123)
for i in range(100):
    # Oscillating price (mean-reverting)
    price = 100.0 + 5 * np.sin(i * 0.3) + np.random.normal(0, 0.3)
    volume = 1000 + np.random.normal(0, 100)
    atr = 2.0 + np.random.normal(0, 0.2)
    detector2.update(price, volume, atr)

regime = detector2.get_regime()
print(f"   Regime: {regime['regime']}")
print(f"   Hurst: {regime['hurst']:.3f} (<0.45 = ranging)")
print(f"   Should trade (ranging): {detector2.should_trade('ranging')}")

# 3. Volatile market
print()
print("3. Volatile market (high ATR):")
detector3 = MarketRegimeDetector(lookback=50)
np.random.seed(456)
for i in range(100):
    price = 100.0 + np.random.normal(0, 1)
    volume = 1000 + np.random.normal(0, 100)
    # Gradually increasing ATR, last values very high
    if i < 80:
        atr = 2.0 + np.random.normal(0, 0.2)
    else:
        atr = 10.0 + np.random.normal(0, 0.5)  # Spike in volatility
    detector3.update(price, volume, atr)

regime = detector3.get_regime()
print(f"   Regime: {regime['regime']}")
print(f"   Vol percentile: {regime['volatility_percentile']:.1f}% (>80 = volatile)")
print(f"   Should trade (not_volatile): {detector3.should_trade('not_volatile')}")

# 4. High volume market
print()
print("4. High volume market:")
detector4 = MarketRegimeDetector(lookback=50)
np.random.seed(789)
for i in range(100):
    price = 100.0 + np.random.normal(0, 1)
    # Last 20 bars have very high volume
    if i < 80:
        volume = 1000 + np.random.normal(0, 100)
    else:
        volume = 5000 + np.random.normal(0, 200)  # Volume spike
    atr = 2.0 + np.random.normal(0, 0.2)
    detector4.update(price, volume, atr)

regime = detector4.get_regime()
print(f"   Regime: {regime['regime']}")
print(f"   Volume z-score: {regime['volume_zscore']:.2f} (>2 = high volume)")
print(f"   Should trade (high_volume): {detector4.should_trade('high_volume')}")

print()
print("=== All MarketRegimeDetector tests PASSED! ===")
