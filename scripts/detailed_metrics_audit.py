#!/usr/bin/env python3
"""
Detailed Metrics Audit - Shows EVERY metric with its actual value
"""

import sys
from pathlib import Path
from datetime import datetime
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd


def load_candles():
    """Load test candles from database."""
    conn = sqlite3.connect(str(ROOT / "data.sqlite3"))
    start_ts = int(datetime(2025, 1, 1).timestamp() * 1000)
    end_ts = int(datetime(2025, 1, 11).timestamp() * 1000)
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit 
        WHERE symbol = 'BTCUSDT' AND interval = '15'
        AND open_time >= ? AND open_time <= ? 
        ORDER BY open_time
    ''', (start_ts, end_ts))
    
    rows = cursor.fetchall()
    conn.close()
    
    df = pd.DataFrame(rows, columns=['open_time', 'open', 'high', 'low', 'close', 'volume'])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.set_index('open_time')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def main():
    from backend.backtesting.models import BacktestConfig, PerformanceMetrics
    from backend.backtesting.engine import BacktestEngine
    
    print("="*80)
    print("DETAILED METRICS AUDIT - ALL 137 METRICS")
    print("="*80)
    
    df = load_candles()
    
    config = BacktestConfig(
        symbol='BTCUSDT',
        interval='15',
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 11),
        strategy_type='rsi',
        strategy_params={'period': 21, 'oversold': 30, 'overbought': 70},
        direction='both',
        initial_capital=10000.0,
        leverage=10.0,
        position_size=1.0,
    )
    
    engine = BacktestEngine()
    result = engine.run(config, df, silent=True)
    metrics = result.metrics
    
    # Get all fields
    schema = PerformanceMetrics.model_fields
    
    # Categorize metrics
    categories = {
        'MONETARY': ['net_profit', 'net_profit_pct', 'gross_profit', 'gross_profit_pct', 
                     'gross_loss', 'gross_loss_pct', 'total_commission', 'buy_hold_return',
                     'total_return', 'annual_return'],
        'RISK': ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'volatility', 
                 'ulcer_index', 'sqn', 'recovery_factor', 'expectancy', 'expectancy_ratio'],
        'DRAWDOWN': ['max_drawdown', 'max_drawdown_value', 'avg_drawdown', 
                     'max_drawdown_duration_days', 'max_runup', 'avg_runup',
                     'max_drawdown_intrabar', 'max_runup_intrabar'],
        'TRADE_STATS': ['total_trades', 'winning_trades', 'losing_trades', 'breakeven_trades',
                        'win_rate', 'profit_factor', 'avg_trade', 'avg_trade_value'],
        'WIN_LOSS': ['avg_win', 'avg_win_value', 'avg_loss', 'avg_loss_value',
                     'largest_win', 'largest_loss', 'avg_win_loss_ratio'],
        'DURATION': ['avg_bars_in_trade', 'avg_bars_in_winning', 'avg_bars_in_losing',
                     'exposure_time', 'avg_trade_duration_hours', 'max_trade_duration_hours',
                     'min_trade_duration_hours'],
        'STREAKS': ['max_consecutive_wins', 'max_consecutive_losses'],
        'LONG_SPECIFIC': ['long_trades', 'long_win_rate', 'long_pnl', 'long_profit_factor',
                          'long_avg_win', 'long_avg_loss', 'long_largest_win', 'long_largest_loss'],
        'SHORT_SPECIFIC': ['short_trades', 'short_win_rate', 'short_pnl', 'short_profit_factor',
                           'short_avg_win', 'short_avg_loss', 'short_largest_win', 'short_largest_loss'],
        'MARGIN': ['avg_margin_used', 'max_margin_used', 'margin_efficiency', 'max_contracts_held'],
        'TV_SPECIFIC': ['strategy_outperformance', 'largest_win_pct_of_gross', 
                        'largest_loss_pct_of_gross', 'net_profit_to_largest_loss',
                        'account_size_required'],
    }
    
    total = 0
    filled = 0
    zero = 0
    none_count = 0
    problematic = []
    
    # Print by category
    for cat_name, cat_fields in categories.items():
        print(f"\n{'='*80}")
        print(f"  {cat_name}")
        print(f"{'='*80}")
        
        for field in cat_fields:
            if field not in schema:
                continue
            
            value = getattr(metrics, field, None)
            total += 1
            
            # Determine status
            if value is None:
                status = "[NONE]"
                none_count += 1
                problematic.append((field, "None"))
            elif isinstance(value, (int, float)):
                if value == 0:
                    status = "[ZERO]"
                    zero += 1
                elif abs(value) > 1e15 or (abs(value) < 1e-10 and value != 0):
                    status = "[WARN]"
                    problematic.append((field, f"Suspicious: {value}"))
                else:
                    status = "[OK]"
                    filled += 1
            elif isinstance(value, list):
                if len(value) == 0:
                    status = "[EMPTY]"
                    none_count += 1
                else:
                    status = f"[LIST:{len(value)}]"
                    filled += 1
            else:
                status = "[OK]"
                filled += 1
            
            # Format value for display
            if isinstance(value, float):
                if abs(value) >= 1000:
                    val_str = f"{value:,.2f}"
                elif abs(value) >= 1:
                    val_str = f"{value:.4f}"
                elif value == 0:
                    val_str = "0"
                else:
                    val_str = f"{value:.6f}"
            elif isinstance(value, list):
                val_str = f"[{len(value)} items]"
            else:
                val_str = str(value)
            
            print(f"  {status:8} {field:40} = {val_str}")
    
    # Also check fields not in our categories
    all_categorized = set()
    for fields in categories.values():
        all_categorized.update(fields)
    
    uncategorized = [f for f in schema.keys() if f not in all_categorized]
    
    if uncategorized:
        print(f"\n{'='*80}")
        print(f"  OTHER METRICS ({len(uncategorized)} fields)")
        print(f"{'='*80}")
        
        for field in sorted(uncategorized):
            value = getattr(metrics, field, None)
            total += 1
            
            if value is None:
                status = "[NONE]"
                none_count += 1
            elif isinstance(value, (int, float)):
                if value == 0:
                    status = "[ZERO]"
                    zero += 1
                else:
                    status = "[OK]"
                    filled += 1
            elif isinstance(value, list):
                if len(value) == 0:
                    status = "[EMPTY]"
                    none_count += 1
                else:
                    status = f"[LIST:{len(value)}]"
                    filled += 1
            else:
                status = "[OK]"
                filled += 1
            
            if isinstance(value, float):
                val_str = f"{value:.4f}" if abs(value) < 1000 else f"{value:,.2f}"
            elif isinstance(value, list):
                val_str = f"[{len(value)} items]"
            else:
                val_str = str(value)
            
            print(f"  {status:8} {field:40} = {val_str}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"  Total metrics:     {total}")
    print(f"  Filled (non-zero): {filled}")
    print(f"  Zero values:       {zero}")
    print(f"  None/Empty:        {none_count}")
    print(f"  Coverage:          {(filled + zero) / total * 100:.1f}%")
    
    if problematic:
        print(f"\n  PROBLEMATIC METRICS ({len(problematic)}):")
        for field, issue in problematic:
            print(f"    - {field}: {issue}")
    
    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
