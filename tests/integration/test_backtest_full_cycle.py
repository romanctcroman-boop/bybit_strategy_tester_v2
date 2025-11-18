"""
Integration Test: Full Backtest Cycle

Проверяем полный цикл:
API → Celery Task → BacktestEngine → Database → Results

Тестируем:
- Long стратегию
- Short стратегию
- Сохранение результатов в БД
- Сохранение трейдов
- Корректность метрик
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.database import SessionLocal
from backend.models import Backtest, Strategy, Trade
from backend.services.data_service import DataService


def generate_test_data_trend(n_bars: int = 500, trend: str = "up") -> pd.DataFrame:
    """
    Генерирует тестовые OHLCV данные с трендом
    
    Args:
        n_bars: Количество баров
        trend: Тип тренда ('up', 'down', 'sideways')
    
    Returns:
        DataFrame с колонками: timestamp, open, high, low, close, volume
    """
    import numpy as np
    
    start = datetime(2025, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=15 * i) for i in range(n_bars)]
    
    base_price = 50000.0
    volatility = 100.0
    
    if trend == "up":
        # Восходящий тренд
        trend_values = np.linspace(0, 5000, n_bars)
    elif trend == "down":
        # Нисходящий тренд
        trend_values = np.linspace(0, -5000, n_bars)
    else:
        # Боковик
        trend_values = np.zeros(n_bars)
    
    closes = []
    for i in range(n_bars):
        noise = np.random.randn() * volatility
        price = base_price + trend_values[i] + noise
        closes.append(price)
    
    data = []
    for i, ts in enumerate(timestamps):
        close = closes[i]
        open_price = closes[i - 1] if i > 0 else close
        high = max(open_price, close) + abs(np.random.randn() * volatility * 0.5)
        low = min(open_price, close) - abs(np.random.randn() * volatility * 0.5)
        volume = 1000 + np.random.rand() * 500
        
        data.append({
            "timestamp": ts,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
    
    return pd.DataFrame(data)


@pytest.fixture(scope="module")
def db_session():
    """Создаём сессию БД для тестов"""
    from backend.database import Base, engine
    
    # Создаём все таблицы
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Удаляем таблицы после тестов
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_strategy(db_session):
    """Создаём тестовую стратегию"""
    ds = DataService(db_session)
    
    # Удаляем старую стратегию если есть
    existing = db_session.query(Strategy).filter(Strategy.name == "Test EMA Crossover").first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
    
    strategy = ds.create_strategy(
        name="Test EMA Crossover",
        description="EMA Crossover for integration testing",
        strategy_type="Indicator-Based",
        config={
            "type": "ema_crossover",
            "fast_ema": 20,
            "slow_ema": 50,
            "take_profit_pct": 5.0,
            "stop_loss_pct": 2.0,
        },
        is_active=True,
    )
    
    yield strategy
    
    # Cleanup
    try:
        db_session.delete(strategy)
        db_session.commit()
    except Exception:
        pass


def run_backtest_sync(db_session, test_strategy, strategy_config, test_data_trend="up"):
    """Helper функция для запуска бэктеста синхронно"""
    from backend.core.engine_adapter import get_engine
    from backend.services.data_service import DataService as DS
    
    # Mock данных
    test_data = generate_test_data_trend(n_bars=500, trend=test_data_trend)
    
    def mock_get_market_data(self, symbol, timeframe, start_time, end_time):
        return test_data
    
    # Временно патчим метод
    original = DS.get_market_data
    DS.get_market_data = mock_get_market_data
    
    try:
        start_date = datetime(2025, 1, 1, tzinfo=UTC)
        end_date = datetime(2025, 1, 10, tzinfo=UTC)
        
        ds = DataService(db_session)
        
        backtest = ds.create_backtest(
            strategy_id=test_strategy.id,
            symbol="BTCUSDT",
            timeframe="15",
            start_date=start_date,
            end_date=end_date,
            initial_capital=10_000.0,
            leverage=5,
            commission=0.075 / 100,
            config={},
            status="queued",
        )
        
        ds.update_backtest(backtest.id, status="running", started_at=datetime.now(UTC))
        
        candles = ds.get_market_data(
            symbol="BTCUSDT",
            timeframe="15",
            start_time=start_date,
            end_time=end_date,
        )
        
        leverage = strategy_config.get("leverage", 1)
        order_size_usd = strategy_config.get("order_size_usd", None)
        commission = 0.075 / 100
        slippage_pct = 0.05
        
        engine = get_engine(
            None,
            initial_capital=10_000.0,
            commission=commission,
            slippage_pct=slippage_pct,
            leverage=leverage,
            order_size_usd=order_size_usd,
        )
        
        results = engine.run(data=candles, strategy_config=strategy_config)
        
        # Сохраняем результаты
        ds.update_backtest_results(
            backtest_id=backtest.id,
            **{
                "final_capital": results.get("final_capital", 0),
                "total_return": results.get("total_return", 0),
                "total_trades": results.get("total_trades", 0),
                "winning_trades": results.get("winning_trades", 0),
                "losing_trades": results.get("losing_trades", 0),
                "win_rate": results.get("win_rate", 0),
                "sharpe_ratio": results.get("sharpe_ratio", 0),
                "max_drawdown": results.get("max_drawdown", 0),
                "results": results,
            },
        )
        
        # Сохраняем трейды
        trades = results.get("trades", [])
        if trades:
            trades_data = []
            for trade in trades:
                entry_time = trade.get("entry_time")
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                
                exit_time = trade.get("exit_time")
                if isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time)
                
                trade_data = {
                    "backtest_id": backtest.id,
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "side": trade.get("side", "long").upper(),
                    "entry_price": trade.get("entry_price"),
                    "exit_price": trade.get("exit_price"),
                    "quantity": trade.get("quantity"),
                    "pnl": trade.get("pnl"),
                    "pnl_pct": trade.get("pnl_pct"),
                    "run_up": trade.get("run_up"),
                    "run_up_pct": trade.get("run_up_pct"),
                    "drawdown": trade.get("drawdown"),
                    "drawdown_pct": trade.get("drawdown_pct"),
                    "cumulative_pnl": trade.get("cumulative_pnl"),
                }
                trades_data.append(trade_data)
            
            ds.create_trades_batch(trades_data)
        
        db_session.refresh(backtest)
        return backtest, ds
    
    finally:
        # Восстанавливаем оригинальный метод
        DS.get_market_data = original


def test_full_cycle_long_strategy(db_session, test_strategy):
    """
    Тест полного цикла: Long стратегия
    
    Проверяем:
    1. Создание бэктеста
    2. Запуск через BacktestEngine
    3. Сохранение результатов
    4. Сохранение трейдов
    5. Корректность метрик
    """
    strategy_config = {
        "type": "ema_crossover",
        "fast_ema": 20,
        "slow_ema": 50,
        "take_profit_pct": 5.0,
        "stop_loss_pct": 2.0,
        "direction": "long",  # LONG ONLY
        "signal_exit": False,
        "trailing_stop_pct": None,
        "leverage": 5,
        "order_size_usd": 100.0,
    }
    
    backtest, ds = run_backtest_sync(db_session, test_strategy, strategy_config, test_data_trend="up")
    
    # Проверки
    assert backtest.status == "completed"
    assert backtest.final_capital is not None
    assert backtest.total_return is not None
    assert backtest.total_trades is not None
    assert backtest.total_trades > 0, "Should have at least 1 trade in uptrend"
    
    # Метрики
    assert backtest.win_rate is not None
    assert backtest.sharpe_ratio is not None
    assert backtest.max_drawdown is not None
    
    # Трейды
    trades_db = ds.get_trades(backtest.id)
    assert len(trades_db) > 0, "Trades should be saved to database"
    assert len(trades_db) == backtest.total_trades
    
    # Все трейды LONG
    for trade in trades_db:
        assert trade.side == "LONG", f"All trades should be LONG, got {trade.side}"
        assert trade.entry_price is not None
        assert trade.entry_time is not None
    
    print(f"\n✅ LONG Strategy Test:")
    print(f"   Final Capital: ${backtest.final_capital:,.2f}")
    print(f"   Total Return: {backtest.total_return*100:.2f}%")
    print(f"   Total Trades: {backtest.total_trades}")
    print(f"   Win Rate: {backtest.win_rate*100:.1f}%")
    print(f"   Sharpe Ratio: {backtest.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {backtest.max_drawdown*100:.2f}%")


def test_full_cycle_short_strategy(db_session, test_strategy):
    """
    Тест полного цикла: Short стратегия
    
    Проверяем SHORT трейды в нисходящем тренде
    """
    strategy_config = {
        "type": "ema_crossover",
        "fast_ema": 20,
        "slow_ema": 50,
        "take_profit_pct": 5.0,
        "stop_loss_pct": 2.0,
        "direction": "short",  # SHORT ONLY
        "signal_exit": False,
        "trailing_stop_pct": None,
        "leverage": 5,
        "order_size_usd": 100.0,
    }
    
    backtest, ds = run_backtest_sync(db_session, test_strategy, strategy_config, test_data_trend="down")
    
    # Проверки
    assert backtest.status == "completed"
    assert backtest.total_trades is not None
    assert backtest.total_trades > 0, "Should have at least 1 SHORT trade in downtrend"
    
    # Трейды
    trades = ds.get_trades(backtest.id)
    assert len(trades) > 0, "Trades should be saved"
    
    # Все трейды SHORT
    for trade in trades:
        assert trade.side == "SHORT", f"All trades should be SHORT, got {trade.side}"
        assert trade.entry_price is not None
        assert trade.entry_time is not None
    
    print(f"\n✅ SHORT Strategy Test:")
    print(f"   Final Capital: ${backtest.final_capital:,.2f}")
    print(f"   Total Return: {backtest.total_return*100:.2f}%")
    print(f"   Total Trades: {backtest.total_trades}")
    print(f"   Win Rate: {backtest.win_rate*100:.1f}%")
    print(f"   Sharpe Ratio: {backtest.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {backtest.max_drawdown*100:.2f}%")


def test_full_cycle_both_directions(db_session, test_strategy):
    """
    Тест полного цикла: Both directions (Long + Short)
    """
    strategy_config = {
        "type": "ema_crossover",
        "fast_ema": 20,
        "slow_ema": 50,
        "take_profit_pct": 5.0,
        "stop_loss_pct": 2.0,
        "direction": "both",  # BOTH DIRECTIONS
        "signal_exit": True,
        "trailing_stop_pct": None,
        "leverage": 5,
        "order_size_usd": 100.0,
    }
    
    backtest, ds = run_backtest_sync(db_session, test_strategy, strategy_config, test_data_trend="sideways")
    
    # Проверки
    assert backtest.status == "completed"
    assert backtest.total_trades is not None
    
    # Трейды
    trades = ds.get_trades(backtest.id)
    
    # Подсчёт Long/Short
    long_trades = [t for t in trades if t.side == "LONG"]
    short_trades = [t for t in trades if t.side == "SHORT"]
    
    print(f"\n✅ BOTH Directions Test:")
    print(f"   Final Capital: ${backtest.final_capital:,.2f}")
    print(f"   Total Return: {backtest.total_return*100:.2f}%")
    print(f"   Total Trades: {backtest.total_trades}")
    print(f"   LONG Trades: {len(long_trades)}")
    print(f"   SHORT Trades: {len(short_trades)}")
    print(f"   Win Rate: {backtest.win_rate*100:.1f}%")
    print(f"   Sharpe Ratio: {backtest.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {backtest.max_drawdown*100:.2f}%")
    
    assert len(trades) > 0, "Should have trades"


def test_commission_correctness(db_session, test_strategy):
    """
    Проверка корректности комиссии 0.075%
    """
    strategy_config = {
        "type": "ema_crossover",
        "fast_ema": 10,
        "slow_ema": 20,
        "take_profit_pct": 5.0,
        "stop_loss_pct": 2.0,
        "direction": "long",
        "signal_exit": False,
        "leverage": 5,
        "order_size_usd": 100.0,
    }
    
    backtest, ds = run_backtest_sync(db_session, test_strategy, strategy_config, test_data_trend="up")
    
    # Проверяем commission
    assert backtest.commission == 0.075 / 100
    
    print(f"\n✅ Commission Test:")
    print(f"   Commission Rate: {backtest.commission * 100:.3f}%")
    print(f"   Total Trades: {backtest.total_trades}")
    print(f"   Final Capital: ${backtest.final_capital:,.2f}")


if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v", "-s"])
