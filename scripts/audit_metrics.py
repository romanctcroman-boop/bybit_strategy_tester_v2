"""
METRICS AUDIT SCRIPT
Check all metrics for correctness and data sources
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import sqlite3
from datetime import datetime, timezone
import pandas as pd

from backend.database import SessionLocal
from backend.services.data_service import DataService
from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, StrategyType

def run_audit():
    """Run comprehensive metrics audit"""
    db = SessionLocal()
    
    try:
        data_service = DataService(db)
        
        # Get market data
        start_date = datetime(2025, 12, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 1, 17, tzinfo=timezone.utc)
        
        candle_records = data_service.get_market_data(
            symbol="BTCUSDT",
            timeframe="30",
            start_time=start_date,
            end_time=end_date,
        )
        
        print(f"Market data: {len(candle_records)} candles")
        
        candles = pd.DataFrame([{
            "timestamp": pd.to_datetime(c.open_time, unit="ms", utc=True),
            "open": float(c.open_price),
            "high": float(c.high_price),
            "low": float(c.low_price),
            "close": float(c.close_price),
            "volume": float(c.volume),
        } for c in candle_records])
        candles.set_index("timestamp", inplace=True)
        
        # Run backtest
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="30",
            start_date=start_date,
            end_date=end_date,
            strategy_type=StrategyType.RSI,
            strategy_params={
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
            },
            initial_capital=10000.0,
            leverage=10,
            direction="both",
            stop_loss=0.03,
            take_profit=0.02,
            taker_fee=0.0006,
            maker_fee=0.0006,
        )
        
        engine = BacktestEngine()
        result = engine.run(config, candles, silent=True)
        
        if not result.metrics:
            print("ERROR: No metrics returned!")
            return
        
        m = result.metrics
        trades = result.trades or []
        
        print(f"\n{'='*60}")
        print("METRICS AUDIT REPORT")
        print(f"{'='*60}")
        print(f"Total trades: {len(trades)}")
        print(f"Long trades: {sum(1 for t in trades if str(t.side).lower() in ('buy', 'long'))}")
        print(f"Short trades: {sum(1 for t in trades if str(t.side).lower() in ('sell', 'short'))}")
        
        # ============================================
        # CATEGORY 1: BASIC TRADE COUNTERS
        # ============================================
        print(f"\n--- CATEGORY 1: TRADE COUNTERS ---")
        
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl < 0]
        
        print(f"total_trades: {m.total_trades} (actual: {len(trades)}) {'✅' if m.total_trades == len(trades) else '❌'}")
        print(f"winning_trades: {m.winning_trades} (actual: {len(winning)}) {'✅' if m.winning_trades == len(winning) else '❌'}")
        print(f"losing_trades: {m.losing_trades} (actual: {len(losing)}) {'✅' if m.losing_trades == len(losing) else '❌'}")
        
        expected_win_rate = (len(winning) / len(trades) * 100) if trades else 0
        print(f"win_rate: {m.win_rate:.2f}% (expected: {expected_win_rate:.2f}%) {'✅' if abs(m.win_rate - expected_win_rate) < 0.1 else '❌'}")
        
        # ============================================
        # CATEGORY 2: PROFIT/LOSS METRICS
        # ============================================
        print(f"\n--- CATEGORY 2: PROFIT/LOSS ---")
        
        actual_gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        actual_gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        
        print(f"gross_profit: {m.gross_profit:.2f} (actual: {actual_gross_profit:.2f}) {'✅' if abs(m.gross_profit - actual_gross_profit) < 1 else '❌'}")
        print(f"gross_loss: {m.gross_loss:.2f} (actual: {actual_gross_loss:.2f}) {'✅' if abs(m.gross_loss - actual_gross_loss) < 1 else '❌'}")
        
        expected_pf = actual_gross_profit / actual_gross_loss if actual_gross_loss > 0 else 0
        print(f"profit_factor: {m.profit_factor:.4f} (expected: {expected_pf:.4f}) {'✅' if abs(m.profit_factor - expected_pf) < 0.01 else '❌'}")
        
        # ============================================
        # CATEGORY 3: AVERAGE METRICS
        # ============================================
        print(f"\n--- CATEGORY 3: AVERAGES ---")
        
        actual_avg_win = sum(t.pnl for t in winning) / len(winning) if winning else 0
        actual_avg_loss = sum(t.pnl for t in losing) / len(losing) if losing else 0
        actual_avg_trade = sum(t.pnl for t in trades) / len(trades) if trades else 0
        
        print(f"avg_win_value: {m.avg_win_value:.2f} (actual: {actual_avg_win:.2f}) {'✅' if abs(m.avg_win_value - actual_avg_win) < 1 else '❌'}")
        print(f"avg_loss_value: {m.avg_loss_value:.2f} (actual: {actual_avg_loss:.2f}) {'✅' if abs(m.avg_loss_value - actual_avg_loss) < 1 else '❌'}")
        print(f"avg_trade_value: {m.avg_trade_value:.2f} (actual: {actual_avg_trade:.2f}) {'✅' if abs(m.avg_trade_value - actual_avg_trade) < 1 else '❌'}")
        
        # ============================================
        # CATEGORY 4: LONG/SHORT SPLIT
        # ============================================
        print(f"\n--- CATEGORY 4: LONG/SHORT SPLIT ---")
        
        long_trades = [t for t in trades if str(t.side).lower() in ('buy', 'long')]
        short_trades = [t for t in trades if str(t.side).lower() in ('sell', 'short')]
        
        print(f"long_trades: {m.long_trades} (actual: {len(long_trades)}) {'✅' if m.long_trades == len(long_trades) else '❌'}")
        print(f"short_trades: {m.short_trades} (actual: {len(short_trades)}) {'✅' if m.short_trades == len(short_trades) else '❌'}")
        
        long_winning = [t for t in long_trades if t.pnl > 0]
        short_winning = [t for t in short_trades if t.pnl > 0]
        
        print(f"long_winning_trades: {m.long_winning_trades} (actual: {len(long_winning)}) {'✅' if m.long_winning_trades == len(long_winning) else '❌'}")
        print(f"short_winning_trades: {m.short_winning_trades} (actual: {len(short_winning)}) {'✅' if m.short_winning_trades == len(short_winning) else '❌'}")
        
        # ============================================
        # CATEGORY 5: BARS IN TRADE
        # ============================================
        print(f"\n--- CATEGORY 5: BARS IN TRADE ---")
        
        bars_list = [t.bars_in_trade for t in trades if hasattr(t, 'bars_in_trade') and t.bars_in_trade > 0]
        actual_avg_bars = sum(bars_list) / len(bars_list) if bars_list else 0
        
        print(f"avg_bars_in_trade: {m.avg_bars_in_trade:.2f} (actual: {actual_avg_bars:.2f}) {'✅' if abs(m.avg_bars_in_trade - actual_avg_bars) < 0.5 else '⚠️ check'}")
        print(f"avg_bars_in_winning: {m.avg_bars_in_winning:.2f}")
        print(f"avg_bars_in_losing: {m.avg_bars_in_losing:.2f}")
        
        # ============================================
        # CATEGORY 6: DRAWDOWN (may use tick data)
        # ============================================
        print(f"\n--- CATEGORY 6: DRAWDOWN (may use intrabar data) ---")
        
        print(f"max_drawdown: {m.max_drawdown:.2f}%")
        print(f"max_drawdown_value: {m.max_drawdown_value:.2f}")
        print(f"avg_drawdown: {m.avg_drawdown:.2f}%")
        print(f"NOTE: These metrics are calculated from equity curve, not tick data")
        
        # ============================================
        # CATEGORY 7: INTRABAR METRICS (REQUIRE TICK DATA)
        # ============================================
        print(f"\n--- CATEGORY 7: INTRABAR METRICS (tick data) ---")
        
        intrabar_metrics = [
            ('max_drawdown_intrabar', m.max_drawdown_intrabar),
            ('max_drawdown_intrabar_value', m.max_drawdown_intrabar_value),
            ('max_runup_intrabar', m.max_runup_intrabar),
            ('max_runup_intrabar_value', m.max_runup_intrabar_value),
        ]
        
        for name, value in intrabar_metrics:
            status = '⚠️ ZERO - may need tick data' if value == 0 else f'✅ {value:.4f}'
            print(f"{name}: {status}")
        
        # ============================================
        # CATEGORY 8: MAE/MFE (per-trade intrabar)
        # ============================================
        print(f"\n--- CATEGORY 8: MAE/MFE (per-trade intrabar) ---")
        
        trades_with_mae = [t for t in trades if hasattr(t, 'mae') and t.mae != 0]
        trades_with_mfe = [t for t in trades if hasattr(t, 'mfe') and t.mfe != 0]
        
        print(f"Trades with MAE calculated: {len(trades_with_mae)}/{len(trades)}")
        print(f"Trades with MFE calculated: {len(trades_with_mfe)}/{len(trades)}")
        
        if trades_with_mae:
            avg_mae = sum(t.mae for t in trades_with_mae) / len(trades_with_mae)
            print(f"Average MAE: {avg_mae:.4f}")
        else:
            print("⚠️ MAE not calculated - may need intrabar data")
            
        if trades_with_mfe:
            avg_mfe = sum(t.mfe for t in trades_with_mfe) / len(trades_with_mfe)
            print(f"Average MFE: {avg_mfe:.4f}")
        else:
            print("⚠️ MFE not calculated - may need intrabar data")
        
        # ============================================
        # CATEGORY 9: RISK-ADJUSTED RETURNS
        # ============================================
        print(f"\n--- CATEGORY 9: RISK-ADJUSTED RETURNS ---")
        
        print(f"sharpe_ratio: {m.sharpe_ratio:.4f}")
        print(f"sortino_ratio: {m.sortino_ratio:.4f}")
        print(f"calmar_ratio: {m.calmar_ratio:.4f}")
        print(f"recovery_factor: {m.recovery_factor:.4f}")
        print(f"expectancy: {m.expectancy:.4f}")
        
        # ============================================
        # CATEGORY 10: BUY & HOLD
        # ============================================
        print(f"\n--- CATEGORY 10: BUY & HOLD COMPARISON ---")
        
        first_price = candles['close'].iloc[0]
        last_price = candles['close'].iloc[-1]
        expected_bh_pct = ((last_price - first_price) / first_price) * 100
        
        print(f"First price: {first_price:.2f}")
        print(f"Last price: {last_price:.2f}")
        print(f"buy_hold_return_pct: {m.buy_hold_return_pct:.2f}% (expected: {expected_bh_pct:.2f}%) {'✅' if abs(m.buy_hold_return_pct - expected_bh_pct) < 1 else '⚠️ check'}")
        print(f"strategy_outperformance: {m.strategy_outperformance:.2f}%")
        
        # ============================================
        # CATEGORY 11: CAGR
        # ============================================
        print(f"\n--- CATEGORY 11: CAGR ---")
        
        print(f"cagr: {m.cagr:.2f}%")
        print(f"cagr_long: {m.cagr_long:.2f}%")
        print(f"cagr_short: {m.cagr_short:.2f}%")
        
        # ============================================
        # SUMMARY
        # ============================================
        print(f"\n{'='*60}")
        print("AUDIT SUMMARY")
        print(f"{'='*60}")
        
        print("""
METRICS THAT USE TICK/INTRABAR DATA:
1. max_drawdown_intrabar / max_drawdown_intrabar_value
2. max_runup_intrabar / max_runup_intrabar_value  
3. Per-trade MAE (Maximum Adverse Excursion)
4. Per-trade MFE (Maximum Favorable Excursion)
5. Per-trade max_runup / max_drawdown

STATUS:
- If Bar Magnifier is DISABLED: These metrics use OHLC simulation
- If Bar Magnifier is ENABLED: These metrics use 1-minute candles
- True tick data requires WebSocket streaming (not implemented)
""")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_audit()
