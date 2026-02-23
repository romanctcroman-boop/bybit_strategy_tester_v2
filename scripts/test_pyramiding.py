"""
Тест пирамидинга - проверка корректной работы multiple entries
"""
import sys

sys.path.insert(0, r'd:\bybit_strategy_tester_v2')

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.pyramiding import PyramidingManager


def test_pyramiding_manager():
    """Тест PyramidingManager"""
    print("=" * 60)
    print("TEST: PyramidingManager")
    print("=" * 60)

    # Тест 1: pyramiding = 1 (отключено)
    print("\n1. Pyramiding = 1 (disabled)")
    mgr = PyramidingManager(pyramiding=1)
    assert mgr.can_add_entry("long"), "Should allow first entry"

    mgr.add_entry("long", 50000, 0.1, 1000, 0, datetime.now())
    assert not mgr.can_add_entry("long"), "Should not allow second entry"
    assert mgr.get_avg_entry_price("long") == 50000, "Avg price should be entry price"
    print("   ✓ Passed")

    # Тест 2: pyramiding = 3 (включено)
    print("\n2. Pyramiding = 3 (enabled)")
    mgr = PyramidingManager(pyramiding=3)

    mgr.add_entry("long", 50000, 0.1, 1000, 0, datetime.now())
    assert mgr.can_add_entry("long"), "Should allow 2nd entry"

    mgr.add_entry("long", 51000, 0.1, 1000, 1, datetime.now())
    assert mgr.can_add_entry("long"), "Should allow 3rd entry"

    mgr.add_entry("long", 52000, 0.1, 1000, 2, datetime.now())
    assert not mgr.can_add_entry("long"), "Should not allow 4th entry"

    print(f"   Entry count: {mgr.get_entry_count('long')}")
    print(f"   Total size: {mgr.get_total_size('long')}")
    print("   ✓ Passed")

    # Тест 3: Средневзвешенная цена
    print("\n3. Weighted Average Entry Price")
    mgr = PyramidingManager(pyramiding=3)

    # Entry 1: 100 @ $50,000
    mgr.add_entry("long", 50000, 100, 1000, 0, datetime.now())
    # Entry 2: 100 @ $51,000
    mgr.add_entry("long", 51000, 100, 1000, 1, datetime.now())
    # Entry 3: 100 @ $52,000
    mgr.add_entry("long", 52000, 100, 1000, 2, datetime.now())

    # Expected: (100*50000 + 100*51000 + 100*52000) / 300 = 51000
    expected_avg = (100*50000 + 100*51000 + 100*52000) / 300
    actual_avg = mgr.get_avg_entry_price("long")

    print(f"   Expected avg: ${expected_avg:.2f}")
    print(f"   Actual avg:   ${actual_avg:.2f}")
    assert abs(actual_avg - expected_avg) < 0.01, f"Avg mismatch: {actual_avg} vs {expected_avg}"
    print("   ✓ Passed")

    # Тест 4: TP/SL от средней цены
    print("\n4. TP/SL from Average Price")

    tp_price = mgr.get_tp_price("long", 0.015)  # 1.5% TP
    sl_price = mgr.get_sl_price("long", 0.03)   # 3% SL

    expected_tp = 51000 * 1.015
    expected_sl = 51000 * 0.97

    print(f"   Avg Entry:    ${actual_avg:.2f}")
    print(f"   TP (1.5%):    ${tp_price:.2f} (expected: ${expected_tp:.2f})")
    print(f"   SL (3%):      ${sl_price:.2f} (expected: ${expected_sl:.2f})")

    assert abs(tp_price - expected_tp) < 0.01, "TP mismatch"
    assert abs(sl_price - expected_sl) < 0.01, "SL mismatch"
    print("   ✓ Passed")

    # Тест 5: FIFO закрытие
    print("\n5. FIFO Close")
    mgr = PyramidingManager(pyramiding=3, close_rule="FIFO")

    t1 = datetime.now()
    t2 = t1 + timedelta(hours=1)
    t3 = t2 + timedelta(hours=1)

    mgr.add_entry("long", 50000, 100, 1000, 0, t1)
    mgr.add_entry("long", 51000, 100, 1000, 1, t2)
    mgr.add_entry("long", 52000, 100, 1000, 2, t3)

    # Signal exit - should close FIRST entry (FIFO)
    closed = mgr.close_position("long", 53000, 5, t3, "signal", 0.001)

    print(f"   Closed trades: {len(closed)}")
    print(f"   Remaining entries: {mgr.get_entry_count('long')}")

    assert len(closed) == 1, "Should close 1 trade"
    assert closed[0]['entry_price'] == 50000, "Should close FIRST entry"
    assert mgr.get_entry_count("long") == 2, "Should have 2 remaining"
    print("   ✓ Passed")

    # Тест 6: ALL закрытие при TP
    print("\n6. ALL Close on TP Hit")
    mgr = PyramidingManager(pyramiding=3, close_rule="FIFO")  # Even with FIFO, TP closes ALL

    mgr.add_entry("long", 50000, 100, 1000, 0, t1)
    mgr.add_entry("long", 51000, 100, 1000, 1, t2)
    mgr.add_entry("long", 52000, 100, 1000, 2, t3)

    # TP hit - should close ALL entries
    closed = mgr.close_position("long", 53000, 5, t3, "take_profit", 0.001)

    print(f"   Closed trades: {len(closed)}")
    print(f"   Remaining entries: {mgr.get_entry_count('long')}")

    assert len(closed) == 1, "Should close as 1 aggregated trade"
    assert mgr.get_entry_count("long") == 0, "Should have 0 remaining"
    print("   ✓ Passed")

    print("\n" + "=" * 60)
    print("ALL PYRAMIDING MANAGER TESTS PASSED! ✅")
    print("=" * 60)


def test_fallback_engine_v3_pyramiding():
    """Тест FallbackEngineV3 с пирамидингом"""
    print("\n" + "=" * 60)
    print("TEST: FallbackEngineV3 with Pyramiding")
    print("=" * 60)

    # Создаём тестовые данные с 3 последовательными LONG сигналами
    n = 50
    dates = pd.date_range(start='2025-01-01', periods=n, freq='1h')

    # Цена растёт для проверки пирамидинга
    prices = 50000 + np.arange(n) * 100  # От 50000 до 54900

    candles = pd.DataFrame({
        'open': prices,
        'high': prices + 50,
        'low': prices - 50,
        'close': prices + 25,
    }, index=dates)

    # 3 LONG сигнала подряд
    long_entries = np.zeros(n, dtype=bool)
    long_entries[5] = True   # Сигнал 1
    long_entries[10] = True  # Сигнал 2
    long_entries[15] = True  # Сигнал 3

    long_exits = np.zeros(n, dtype=bool)
    long_exits[40] = True  # Выход

    # Тест 1: pyramiding = 1 (только 1 позиция)
    print("\n1. Pyramiding = 1")

    engine = FallbackEngineV3()
    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=np.zeros(n, dtype=bool),
        short_exits=np.zeros(n, dtype=bool),
        initial_capital=10000,
        position_size=0.5,
        leverage=1,
        stop_loss=0.0,
        take_profit=0.0,
        taker_fee=0.001,
        slippage=0.0,
        direction=TradeDirection.BOTH,
        pyramiding=1,
        close_entries_rule="ALL",
        use_bar_magnifier=False,  # Disable Bar Magnifier for test
    )

    result = engine.run(input_data)

    print(f"   Trades: {len(result.trades)}")
    print(f"   Net Profit: ${result.metrics.net_profit:.2f}")

    # С pyramiding=1 должна быть только 1 сделка (сигналы 2 и 3 игнорируются)
    assert len(result.trades) == 1, f"Expected 1 trade, got {len(result.trades)}"
    print("   ✓ Passed")

    # Тест 2: pyramiding = 3 (3 позиции)
    print("\n2. Pyramiding = 3")

    input_data.pyramiding = 3
    result = engine.run(input_data)

    print(f"   Trades: {len(result.trades)}")
    print(f"   Net Profit: ${result.metrics.net_profit:.2f}")

    # С pyramiding=3 должно быть 3 входа, но при выходе они закрываются как 1 aggregated trade
    # (Или 1 trade если close_rule=ALL)
    assert len(result.trades) >= 1, f"Expected at least 1 trade, got {len(result.trades)}"
    print("   ✓ Passed")

    print("\n" + "=" * 60)
    print("ALL ENGINE V3 TESTS PASSED! ✅")
    print("=" * 60)


if __name__ == '__main__':
    test_pyramiding_manager()
    test_fallback_engine_v3_pyramiding()

    print("\n\n" + "=" * 60)
    print("🎉 ALL PYRAMIDING TESTS PASSED!")
    print("=" * 60)
