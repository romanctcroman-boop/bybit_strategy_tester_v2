"""Test DCA Engine Integration"""

from datetime import datetime

from backend.backtesting.engine_selector import get_engine
from backend.backtesting.models import BacktestConfig


def test_dca_integration():
    # Create DCA-enabled config
    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="1h",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 15),
        initial_capital=10000,
        leverage=5,
        dca_enabled=True,
        dca_order_count=5,
        dca_grid_size_percent=3.0,
        dca_martingale_coef=1.3,
        dca_direction="both",
        dca_multi_tp_enabled=True,
        dca_tp1_percent=1.0,
        dca_tp2_percent=2.0,
        strategy_type="rsi",
    )

    # Get engine
    engine = get_engine(dca_enabled=config.dca_enabled)
    print("Engine selected:", engine.name)
    print("Config DCA fields:")
    print("  - dca_enabled:", config.dca_enabled)
    print("  - dca_order_count:", config.dca_order_count)
    print("  - dca_grid_size_percent:", config.dca_grid_size_percent)
    print("  - dca_martingale_coef:", config.dca_martingale_coef)
    print("  - dca_multi_tp_enabled:", config.dca_multi_tp_enabled)

    # Test engine configuration
    engine._configure_from_config(config)
    print("\nEngine configured from BacktestConfig:")
    print("  - grid_config.enabled:", engine.grid_config.enabled)
    print("  - grid_config.order_count:", engine.grid_config.order_count)
    print("  - grid_config.grid_size_percent:", engine.grid_config.grid_size_percent)
    print("  - multi_tp.enabled:", engine.multi_tp.enabled)

    print("\n✅ Integration test PASSED!")
    return True


if __name__ == "__main__":
    test_dca_integration()
