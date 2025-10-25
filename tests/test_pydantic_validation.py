"""
Тестирование Pydantic валидации
Проверка: модели data_types.py корректно валидируют данные
"""

import sys
import types
from pathlib import Path

# Create shim for backend.database to avoid import errors
mod_db = types.ModuleType("backend.database")


class _Base:
    pass


mod_db.Base = _Base
sys.modules["backend.database"] = mod_db

# Добавить backend в путь
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from models.data_types import (
    TradeEntry,
    PerformanceMetrics,
    RiskPerformanceRatios,
    TradesAnalysis,
    BacktestResults,
    OHLCVCandle,
)
from pydantic import ValidationError


def test_trade_entry():
    """Тест валидации TradeEntry"""
    print("\n=== TEST: TradeEntry ===")
    
    # Валидные данные
    valid_trade = {
        "trade_number": 1,
        "type": "Exit long",
        "date_time": "2025-07-02 19:00",
        "signal": "Long Trail",
        "price_usdt": 39.311,
        "position_size_qty": 3.725,
        "position_size_value": 145.27,
        "net_pl_usdt": 1.02,
        "net_pl_percent": 0.70,
        "run_up_usdt": 1.75,
        "run_up_percent": 1.20,
        "drawdown_usdt": -8.13,
        "drawdown_percent": -5.59,
        "cumulative_pl_usdt": 0.84,
        "cumulative_pl_percent": 0.08,
    }
    
    try:
        trade = TradeEntry(**valid_trade)
        print(f"✓ Валидный TradeEntry создан: {trade.signal} @ {trade.price_usdt}")
    except ValidationError as e:
        print(f"✗ ОШИБКА валидации: {e}")
        return False
    
    # Невалидная дата (DD.MM.YYYY вместо YYYY-MM-DD)
    invalid_date = valid_trade.copy()
    invalid_date["date_time"] = "02.07.2025 19:00"
    
    try:
        TradeEntry(**invalid_date)
        print("✗ ОШИБКА: Должна была отклонить неверный формат даты!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен неверный формат даты: {e.errors()[0]['msg']}")
    
    # Отрицательная цена
    invalid_price = valid_trade.copy()
    invalid_price["price_usdt"] = -10.0
    
    try:
        TradeEntry(**invalid_price)
        print("✗ ОШИБКА: Должна была отклонить отрицательную цену!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонена отрицательная цена: {e.errors()[0]['type']}")
    
    return True


def test_performance_metrics():
    """Тест валидации PerformanceMetrics"""
    print("\n=== TEST: PerformanceMetrics ===")
    
    valid_metrics = {
        "open_pl_usdt": -4.22,
        "open_pl_percent": -0.30,
        "net_profit_usdt": 424.19,
        "net_profit_percent": 42.42,
        "gross_profit_usdt": 965.45,
        "gross_profit_percent": 96.54,
        "gross_loss_usdt": -541.25,
        "gross_loss_percent": -54.13,
        "commission_paid_usdt": 48.22,
        "buy_hold_return_usdt": 4.64,
        "buy_hold_return_percent": 0.46,
        "max_equity_run_up_usdt": 450.07,
        "max_equity_run_up_percent": 31.04,
        "max_equity_drawdown_usdt": 94.86,
        "max_equity_drawdown_percent": 6.55,
        "max_contracts_held": 18,
    }
    
    try:
        metrics = PerformanceMetrics(**valid_metrics)
        print(f"✓ Валидный PerformanceMetrics создан: Net profit {metrics.net_profit_usdt}")
    except ValidationError as e:
        print(f"✗ ОШИБКА валидации: {e}")
        return False
    
    # gross_profit должен быть >= 0
    invalid_gross = valid_metrics.copy()
    invalid_gross["gross_profit_usdt"] = -100.0
    
    try:
        PerformanceMetrics(**invalid_gross)
        print("✗ ОШИБКА: Должна была отклонить отрицательный gross_profit!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен отрицательный gross_profit: {e.errors()[0]['type']}")
    
    return True


def test_risk_performance_ratios():
    """Тест валидации RiskPerformanceRatios"""
    print("\n=== TEST: RiskPerformanceRatios ===")
    
    valid_ratios = {
        "sharpe_ratio": 1.59,
        "sortino_ratio": 2.13,
        "profit_factor": 1.784,
        "margin_calls": 0,
    }
    
    try:
        ratios = RiskPerformanceRatios(**valid_ratios)
        print(f"✓ Валидный RiskPerformanceRatios создан: Sharpe {ratios.sharpe_ratio:.2f}")
    except ValidationError as e:
        print(f"✗ ОШИБКА валидации: {e}")
        return False
    
    # Sharpe > 10 должен предупредить
    extreme_sharpe = valid_ratios.copy()
    extreme_sharpe["sharpe_ratio"] = 15.0
    
    try:
        RiskPerformanceRatios(**extreme_sharpe)
        print("✗ ОШИБКА: Должна была отклонить нереалистичный Sharpe!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен нереалистичный Sharpe: {e.errors()[0]['msg']}")
    
    return True


def test_backtest_results():
    """Тест валидации полного результата BacktestResults"""
    print("\n=== TEST: BacktestResults ===")
    
    valid_results = {
        "final_capital": 10424.19,
        "total_return": 0.4242,
        "total_trades": 331,
        "winning_trades": 248,
        "losing_trades": 83,
        "win_rate": 74.92,
        "sharpe_ratio": 1.59,
        "sortino_ratio": 2.13,
        "max_drawdown": 0.0655,
        "profit_factor": 1.784,
        "metrics": {
            "net_profit": 424.19,
            "buy_hold_return": 4.64,
            "buy_hold_return_pct": 0.46,
        },
        "trades": [],
        "equity_curve": [10000.0, 10050.0, 10100.0],
    }
    
    try:
        results = BacktestResults(**valid_results)
        print(f"✓ Валидный BacktestResults создан: {results.total_trades} сделок, "
              f"Win rate {results.win_rate:.2f}%")
    except ValidationError as e:
        print(f"✗ ОШИБКА валидации: {e}")
        return False
    
    # max_drawdown > 1.0 (должен быть decimal 0-1)
    invalid_dd = valid_results.copy()
    invalid_dd["max_drawdown"] = 1.5
    
    try:
        BacktestResults(**invalid_dd)
        print("✗ ОШИБКА: Должна была отклонить max_drawdown > 1.0!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен max_drawdown > 1.0: {e.errors()[0]['type']}")
    
    return True


def test_ohlcv_candle():
    """Тест валидации OHLCV свечи с проверкой High/Low"""
    print("\n=== TEST: OHLCVCandle ===")
    
    from datetime import datetime
    
    valid_candle = {
        "timestamp": 1719847200000,
        "time": datetime(2025, 7, 1, 16, 15),
        "open": 39.0,
        "high": 39.5,
        "low": 38.5,
        "close": 39.2,
        "volume": 145234.56,
    }
    
    try:
        candle = OHLCVCandle(**valid_candle)
        print(f"✓ Валидный OHLCVCandle создан: O={candle.open} H={candle.high} L={candle.low} C={candle.close}")
    except ValidationError as e:
        print(f"✗ ОШИБКА валидации: {e}")
        return False
    
    # High меньше Close (невалидно)
    invalid_high = valid_candle.copy()
    invalid_high["high"] = 38.0  # Меньше close=39.2
    
    try:
        OHLCVCandle(**invalid_high)
        print("✗ ОШИБКА: Должна была отклонить High < Close!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен High < Close: {e.errors()[0]['msg']}")
    
    # Low больше Open (невалидно)
    invalid_low = valid_candle.copy()
    invalid_low["low"] = 40.0  # Больше open=39.0
    
    try:
        OHLCVCandle(**invalid_low)
        print("✗ ОШИБКА: Должна была отклонить Low > Open!")
        return False
    except ValidationError as e:
        print(f"✓ Корректно отклонен Low > Open: {e.errors()[0]['msg']}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ PYDANTIC ВАЛИДАЦИИ")
    print("=" * 60)
    
    tests = [
        ("TradeEntry", test_trade_entry),
        ("PerformanceMetrics", test_performance_metrics),
        ("RiskPerformanceRatios", test_risk_performance_ratios),
        ("BacktestResults", test_backtest_results),
        ("OHLCVCandle", test_ohlcv_candle),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✓✓✓ {test_name} - ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ✓✓✓")
            else:
                failed += 1
                print(f"✗✗✗ {test_name} - ЕСТЬ ОШИБКИ ✗✗✗")
        except Exception as e:
            failed += 1
            print(f"✗✗✗ {test_name} - НЕОЖИДАННАЯ ОШИБКА: {e} ✗✗✗")
    
    print("\n" + "=" * 60)
    print(f"ИТОГО: {passed} пройдено, {failed} провалено")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
