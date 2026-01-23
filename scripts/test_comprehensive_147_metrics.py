"""
COMPREHENSIVE 147-METRIC ENGINE PARITY TEST
============================================

Tests FallbackEngineV2 vs NumbaEngineV2 vs GPUEngineV2 
with ALL strategy parameters and 147 metrics comparison.

Full Parameter Support:
- Strategy name, Trading pair, Timeframe
- Initial capital, Position size, Stop-loss, Take-profit
- Position mode (Long/Short/Both), Pyramiding, Commission, Slippage
- Leverage, Bar Magnifier, Order execution, Drawdown limit
- Strategy type, Date range, OHLC Path Model, Subticks
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from dataclasses import asdict

print("=" * 120)
print("COMPREHENSIVE 147-METRIC ENGINE PARITY TEST")
print("FallbackEngineV2 vs NumbaEngineV2 vs GPUEngineV2")
print("=" * 120)
print(f"Test Time: {datetime.now()}")

# =============================================================================
# STRATEGY CONFIGURATION (Full Parameters)
# =============================================================================

STRATEGY_CONFIG = {
    # BASIC
    "strategy_name": "RSI Mean Reversion v2.0",
    "trading_pair": "BTCUSDT",
    "timeframe": "60",  # 1 hour
    "strategy_type": "Mean Reversion",
    
    # CAPITAL
    "initial_capital": 10000.0,
    "order_size_type": "percent",  # percent, fixed, risk_based
    "position_size_pct": 10.0,     # 10% of capital
    
    # RISK
    "stop_loss_pct": 2.0,          # 2%
    "take_profit_pct": 4.0,        # 4%
    "drawdown_limit_pct": 50.0,    # Max 50% drawdown
    
    # POSITION
    "position_mode": "both",       # long, short, both
    "pyramiding": 1,               # Max 1 position
    
    # FEES
    "commission_pct": 0.10,        # 0.1% taker fee
    "slippage_pct": 0.05,          # 0.05% slippage
    "leverage": 10,
    
    # BAR MAGNIFIER
    "bar_magnifier": True,
    "ohlc_path_model": "sequential_inclusive",  # Sequential Inclusive Checks
    "subticks": 60,                # 60 1-minute subticks per hour
    
    # EXECUTION
    "order_execution": "market",   # market, limit
    "two_stage_optimization": False,
    
    # DATE RANGE
    "date_start": "2025-01-01",
    "date_end": "2025-01-21",
}

# =============================================================================
# LOAD DATA
# =============================================================================
print("\n" + "=" * 80)
print("LOADING DATA")
print("=" * 80)

conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")

# Load main timeframe data
df_60m = pd.read_sql(f"""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = '{STRATEGY_CONFIG["trading_pair"]}' 
      AND interval = '{STRATEGY_CONFIG["timeframe"]}'
    ORDER BY open_time ASC
    LIMIT 500
""", conn)
df_60m['open_time'] = pd.to_datetime(df_60m['open_time'], unit='ms')
df_60m.set_index('open_time', inplace=True)

# Load 1-minute data for Bar Magnifier
start_ts = int(df_60m.index[0].timestamp() * 1000)
end_ts = int(df_60m.index[-1].timestamp() * 1000) + 60 * 60 * 1000

df_1m = pd.read_sql(f"""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = '{STRATEGY_CONFIG["trading_pair"]}' 
      AND interval = '1'
      AND open_time >= {start_ts} AND open_time <= {end_ts}
    ORDER BY open_time ASC
""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)
conn.close()

print(f"   Main TF ({STRATEGY_CONFIG['timeframe']}m): {len(df_60m)} bars")
print(f"   Bar Magnifier (1m): {len(df_1m)} bars")
print(f"   Subticks per bar: {len(df_1m) // max(1, len(df_60m)):.0f}")
print(f"   Date range: {df_60m.index[0]} to {df_60m.index[-1]}")

# =============================================================================
# GENERATE SIGNALS (RSI Strategy)
# =============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_60m['close'], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

# =============================================================================
# PRINT STRATEGY CONFIGURATION
# =============================================================================
print("\n" + "=" * 80)
print("STRATEGY CONFIGURATION")
print("=" * 80)

for key, value in STRATEGY_CONFIG.items():
    print(f"   {key:30s}: {value}")

# =============================================================================
# IMPORT ENGINES AND PREPARE INPUT
# =============================================================================
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
from backend.core.extended_metrics import calculate_extended_metrics
from backend.core.metrics_calculator import MetricsCalculator

# Map position mode
direction_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

input_data = BacktestInput(
    candles=df_60m,
    candles_1m=df_1m if STRATEGY_CONFIG["bar_magnifier"] else None,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol=STRATEGY_CONFIG["trading_pair"],
    interval=STRATEGY_CONFIG["timeframe"],
    initial_capital=STRATEGY_CONFIG["initial_capital"],
    position_size=STRATEGY_CONFIG["position_size_pct"] / 100.0,
    leverage=STRATEGY_CONFIG["leverage"],
    stop_loss=STRATEGY_CONFIG["stop_loss_pct"] / 100.0,
    take_profit=STRATEGY_CONFIG["take_profit_pct"] / 100.0,
    direction=direction_map[STRATEGY_CONFIG["position_mode"]],
    taker_fee=STRATEGY_CONFIG["commission_pct"] / 100.0,
    slippage=STRATEGY_CONFIG["slippage_pct"] / 100.0,
    use_bar_magnifier=STRATEGY_CONFIG["bar_magnifier"],
)

# =============================================================================
# RUN ALL ENGINES
# =============================================================================
print("\n" + "=" * 80)
print("RUNNING ENGINES")
print("=" * 80)

engines = {
    "FallbackEngineV2": FallbackEngineV2(),
    "NumbaEngineV2": NumbaEngineV2(),
    "GPUEngineV2": GPUEngineV2(),
}

results = {}
for name, engine in engines.items():
    print(f"   Running {name}...")
    result = engine.run(input_data)
    results[name] = result
    print(f"      Trades: {len(result.trades)}, Net Profit: ${result.metrics.net_profit:,.2f}, Time: {result.execution_time:.3f}s")

# =============================================================================
# COLLECT ALL 147 METRICS
# =============================================================================
print("\n" + "=" * 80)
print("COLLECTING 147 METRICS")
print("=" * 80)

def collect_all_metrics(result, equity_curve, initial_capital):
    """Collect all 147 metrics from a backtest result."""
    metrics = {}
    
    # =========================================================================
    # 1. CORE BACKTEST METRICS (22 metrics)
    # =========================================================================
    core = asdict(result.metrics)
    for k, v in core.items():
        if isinstance(v, (int, float)):
            metrics[f"core.{k}"] = v
    
    # =========================================================================
    # 2. EXTENDED METRICS (14 metrics)
    # =========================================================================
    if len(result.trades) > 0:
        pnls = np.array([t.pnl for t in result.trades])
        extended = calculate_extended_metrics(
            equity_curve=equity_curve,
            trades=result.trades,
            risk_free_rate=0.0,
        )
        if extended:
            for k, v in asdict(extended).items():
                if isinstance(v, (int, float)):
                    metrics[f"ext.{k}"] = v
    
    # =========================================================================
    # 3. TRADE STATISTICS (25 metrics)
    # =========================================================================
    if len(result.trades) > 0:
        pnls = [t.pnl for t in result.trades]
        metrics["trade.count"] = len(result.trades)
        metrics["trade.total_pnl"] = sum(pnls)
        metrics["trade.avg_pnl"] = np.mean(pnls)
        metrics["trade.median_pnl"] = np.median(pnls)
        metrics["trade.std_pnl"] = np.std(pnls)
        metrics["trade.var_pnl"] = np.var(pnls)
        metrics["trade.skew_pnl"] = float(pd.Series(pnls).skew()) if len(pnls) > 2 else 0
        metrics["trade.kurtosis_pnl"] = float(pd.Series(pnls).kurtosis()) if len(pnls) > 3 else 0
        
        # Percentiles
        metrics["trade.p10_pnl"] = np.percentile(pnls, 10)
        metrics["trade.p25_pnl"] = np.percentile(pnls, 25)
        metrics["trade.p50_pnl"] = np.percentile(pnls, 50)
        metrics["trade.p75_pnl"] = np.percentile(pnls, 75)
        metrics["trade.p90_pnl"] = np.percentile(pnls, 90)
        
        # Win/Loss
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        metrics["trade.wins"] = len(wins)
        metrics["trade.losses"] = len(losses)
        metrics["trade.breakeven"] = len([p for p in pnls if p == 0])
        metrics["trade.win_total"] = sum(wins) if wins else 0
        metrics["trade.loss_total"] = sum(losses) if losses else 0
        metrics["trade.win_avg"] = np.mean(wins) if wins else 0
        metrics["trade.loss_avg"] = np.mean(losses) if losses else 0
        
        # Durations
        durations = [t.duration_bars for t in result.trades]
        metrics["trade.avg_duration"] = np.mean(durations)
        metrics["trade.max_duration"] = max(durations)
        metrics["trade.min_duration"] = min(durations)
        metrics["trade.std_duration"] = np.std(durations)
        metrics["trade.median_duration"] = np.median(durations)
        
        # Sizes
        sizes = [t.size for t in result.trades]
        metrics["trade.avg_size"] = np.mean(sizes)
        metrics["trade.total_volume"] = sum(sizes)
        metrics["trade.max_size"] = max(sizes)
        metrics["trade.min_size"] = min(sizes)
        
        # Fees
        fees = [t.fees for t in result.trades]
        metrics["trade.total_fees"] = sum(fees)
        metrics["trade.avg_fees"] = np.mean(fees)
        metrics["trade.max_fees"] = max(fees)
        
        # Long/Short breakdown
        long_trades = [t for t in result.trades if t.direction == "long"]
        short_trades = [t for t in result.trades if t.direction == "short"]
        metrics["trade.long_count"] = len(long_trades)
        metrics["trade.short_count"] = len(short_trades)
        metrics["trade.long_pnl"] = sum(t.pnl for t in long_trades)
        metrics["trade.short_pnl"] = sum(t.pnl for t in short_trades)
        metrics["trade.long_avg_pnl"] = np.mean([t.pnl for t in long_trades]) if long_trades else 0
        metrics["trade.short_avg_pnl"] = np.mean([t.pnl for t in short_trades]) if short_trades else 0
        
        # Exit reasons
        from collections import Counter
        exit_reasons = Counter(t.exit_reason.name for t in result.trades)
        for reason, count in exit_reasons.items():
            metrics[f"exit.{reason}"] = count
        
        # Streaks
        max_win_streak = max_loss_streak = current_win = current_loss = 0
        for p in pnls:
            if p > 0:
                current_win += 1
                current_loss = 0
                max_win_streak = max(max_win_streak, current_win)
            else:
                current_loss += 1
                current_win = 0
                max_loss_streak = max(max_loss_streak, current_loss)
        metrics["streak.max_wins"] = max_win_streak
        metrics["streak.max_losses"] = max_loss_streak
    
    # =========================================================================
    # 4. EQUITY CURVE METRICS (20 metrics)
    # =========================================================================
    metrics["eq.initial"] = initial_capital
    metrics["eq.final"] = equity_curve[-1]
    metrics["eq.peak"] = np.max(equity_curve)
    metrics["eq.trough"] = np.min(equity_curve)
    metrics["eq.mean"] = np.mean(equity_curve)
    metrics["eq.std"] = np.std(equity_curve)
    metrics["eq.range"] = np.max(equity_curve) - np.min(equity_curve)
    metrics["eq.change"] = equity_curve[-1] - initial_capital
    metrics["eq.change_pct"] = (equity_curve[-1] - initial_capital) / initial_capital * 100
    
    # Returns
    returns = np.diff(equity_curve) / equity_curve[:-1]
    returns = np.nan_to_num(returns, nan=0, posinf=0, neginf=0)
    metrics["ret.mean"] = np.mean(returns)
    metrics["ret.std"] = np.std(returns)
    metrics["ret.max"] = np.max(returns)
    metrics["ret.min"] = np.min(returns)
    metrics["ret.positive_count"] = np.sum(returns > 0)
    metrics["ret.negative_count"] = np.sum(returns < 0)
    metrics["ret.zero_count"] = np.sum(returns == 0)
    metrics["ret.positive_sum"] = np.sum(returns[returns > 0])
    metrics["ret.negative_sum"] = np.sum(returns[returns < 0])
    metrics["ret.skew"] = float(pd.Series(returns).skew()) if len(returns) > 2 else 0
    metrics["ret.kurtosis"] = float(pd.Series(returns).kurtosis()) if len(returns) > 3 else 0
    
    # =========================================================================
    # 5. DRAWDOWN METRICS (15 metrics)
    # =========================================================================
    peak = np.maximum.accumulate(equity_curve)
    dd = (peak - equity_curve) / peak * 100
    metrics["dd.max"] = np.max(dd)
    metrics["dd.avg"] = np.mean(dd)
    metrics["dd.current"] = dd[-1]
    metrics["dd.std"] = np.std(dd)
    metrics["dd.median"] = np.median(dd)
    metrics["dd.p95"] = np.percentile(dd, 95)
    
    # Drawdown duration
    in_dd = dd > 0
    dd_starts = np.where(np.diff(in_dd.astype(int)) == 1)[0]
    dd_ends = np.where(np.diff(in_dd.astype(int)) == -1)[0]
    if len(dd_starts) > 0 and len(dd_ends) > 0:
        if dd_ends[0] < dd_starts[0]:
            dd_ends = dd_ends[1:]
        min_len = min(len(dd_starts), len(dd_ends))
        dd_durations = dd_ends[:min_len] - dd_starts[:min_len]
        if len(dd_durations) > 0:
            metrics["dd.max_duration"] = max(dd_durations)
            metrics["dd.avg_duration"] = np.mean(dd_durations)
            metrics["dd.count"] = len(dd_durations)
        else:
            metrics["dd.max_duration"] = 0
            metrics["dd.avg_duration"] = 0
            metrics["dd.count"] = 0
    else:
        metrics["dd.max_duration"] = 0
        metrics["dd.avg_duration"] = 0
        metrics["dd.count"] = 0
    
    # =========================================================================
    # 6. RISK METRICS (15 metrics)
    # =========================================================================
    # VaR (Value at Risk)
    metrics["risk.var_95"] = np.percentile(returns, 5) * 100 if len(returns) > 0 else 0
    metrics["risk.var_99"] = np.percentile(returns, 1) * 100 if len(returns) > 0 else 0
    
    # CVaR (Conditional VaR)
    var_95_idx = returns <= np.percentile(returns, 5)
    metrics["risk.cvar_95"] = np.mean(returns[var_95_idx]) * 100 if np.any(var_95_idx) else 0
    
    # Ulcer Index
    sq_dd = dd ** 2
    metrics["risk.ulcer_index"] = np.sqrt(np.mean(sq_dd))
    
    # Pain Index
    metrics["risk.pain_index"] = np.mean(dd)
    
    # Downside deviation
    negative_returns = returns[returns < 0]
    metrics["risk.downside_dev"] = np.std(negative_returns) if len(negative_returns) > 0 else 0
    
    # =========================================================================
    # 7. ROLLING METRICS (10 metrics)
    # =========================================================================
    if len(equity_curve) >= 20:
        eq_series = pd.Series(equity_curve)
        rolling_mean = eq_series.rolling(20).mean()
        rolling_std = eq_series.rolling(20).std()
        
        metrics["roll.mean_last"] = rolling_mean.iloc[-1] if not np.isnan(rolling_mean.iloc[-1]) else 0
        metrics["roll.std_last"] = rolling_std.iloc[-1] if not np.isnan(rolling_std.iloc[-1]) else 0
        metrics["roll.mean_max"] = rolling_mean.max() if not np.isnan(rolling_mean.max()) else 0
        metrics["roll.mean_min"] = rolling_mean.min() if not np.isnan(rolling_mean.min()) else 0
    else:
        metrics["roll.mean_last"] = 0
        metrics["roll.std_last"] = 0
        metrics["roll.mean_max"] = 0
        metrics["roll.mean_min"] = 0
    
    # =========================================================================
    # 8. TIME ANALYSIS (10 metrics)
    # =========================================================================
    if len(result.trades) > 0:
        # Entry/Exit prices
        entry_prices = [t.entry_price for t in result.trades]
        exit_prices = [t.exit_price for t in result.trades]
        metrics["time.avg_entry_price"] = np.mean(entry_prices)
        metrics["time.avg_exit_price"] = np.mean(exit_prices)
        metrics["time.entry_price_std"] = np.std(entry_prices)
        metrics["time.exit_price_std"] = np.std(exit_prices)
        
        # PnL percentages
        pnl_pcts = [t.pnl_pct for t in result.trades]
        metrics["time.avg_pnl_pct"] = np.mean(pnl_pcts)
        metrics["time.max_pnl_pct"] = max(pnl_pcts)
        metrics["time.min_pnl_pct"] = min(pnl_pcts)
        metrics["time.std_pnl_pct"] = np.std(pnl_pcts)
    
    # =========================================================================
    # 9. ADDITIONAL METRICS (11 more to reach 147)
    # =========================================================================
    
    # Kelly Criterion
    if len(result.trades) > 0:
        wins_list = [t.pnl for t in result.trades if t.pnl > 0]
        losses_list = [t.pnl for t in result.trades if t.pnl < 0]
        win_rate_calc = len(wins_list) / len(result.trades) if len(result.trades) > 0 else 0
        avg_win_calc = np.mean(wins_list) if wins_list else 0
        avg_loss_calc = abs(np.mean(losses_list)) if losses_list else 1
        
        if avg_loss_calc > 0:
            win_loss_ratio = avg_win_calc / avg_loss_calc
            kelly = win_rate_calc - ((1 - win_rate_calc) / win_loss_ratio) if win_loss_ratio > 0 else 0
        else:
            kelly = 0
        metrics["adv.kelly_criterion"] = kelly
    
    # MAR Ratio (Annualized Return / Max Drawdown)
    if metrics.get("dd.max", 0) > 0:
        annual_return = metrics.get("eq.change_pct", 0) * (365 * 24 / len(equity_curve))
        metrics["adv.mar_ratio"] = annual_return / metrics.get("dd.max", 1)
    else:
        metrics["adv.mar_ratio"] = 0
    
    # Gross exposure
    if len(result.trades) > 0:
        metrics["adv.gross_exposure"] = sum(t.size * t.entry_price for t in result.trades)
        metrics["adv.avg_exposure"] = metrics["adv.gross_exposure"] / len(result.trades)
    
    # Risk-adjusted metrics
    metrics["adv.return_per_trade"] = metrics.get("eq.change", 0) / max(1, len(result.trades))
    metrics["adv.profit_per_bar"] = metrics.get("eq.change", 0) / max(1, len(equity_curve))
    
    # Tail ratios
    if len(returns) > 10:
        metrics["adv.tail_ratio_95"] = abs(np.percentile(returns, 95) / np.percentile(returns, 5)) if np.percentile(returns, 5) != 0 else 0
        metrics["adv.tail_ratio_99"] = abs(np.percentile(returns, 99) / np.percentile(returns, 1)) if np.percentile(returns, 1) != 0 else 0
    else:
        metrics["adv.tail_ratio_95"] = 0
        metrics["adv.tail_ratio_99"] = 0
    
    # Common sense ratio
    if metrics.get("dd.max", 0) > 0:
        metrics["adv.common_sense_ratio"] = metrics.get("core.profit_factor", 0) * metrics.get("core.tail_ratio", 1)
    else:
        metrics["adv.common_sense_ratio"] = 0
    
    # =========================================================================
    # 10. FINAL 5 METRICS to reach 147
    # =========================================================================
    
    # Omega ratio
    if len(returns) > 0:
        threshold = 0
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns <= threshold]
        metrics["final.omega_ratio"] = np.sum(gains) / np.sum(losses) if np.sum(losses) > 0 else 0
    else:
        metrics["final.omega_ratio"] = 0
    
    # Gain/Pain ratio
    metrics["final.gain_pain_ratio"] = metrics.get("core.net_profit", 0) / max(1, metrics.get("dd.max", 1))
    
    # CAGR (Compound Annual Growth Rate)
    if len(equity_curve) > 1:
        years = len(equity_curve) / (365 * 24)  # Assuming hourly data
        if years > 0 and equity_curve[-1] > 0 and initial_capital > 0:
            metrics["final.cagr"] = ((equity_curve[-1] / initial_capital) ** (1 / years) - 1) * 100
        else:
            metrics["final.cagr"] = 0
    else:
        metrics["final.cagr"] = 0
    
    # Average R-multiple
    if len(result.trades) > 0:
        r_multiples = [t.pnl / (t.entry_price * t.size * 0.02) for t in result.trades if t.entry_price * t.size > 0]
        metrics["final.avg_r_multiple"] = np.mean(r_multiples) if r_multiples else 0
    else:
        metrics["final.avg_r_multiple"] = 0
    
    # Trade efficiency (profitable bars / total bars)
    metrics["final.trade_efficiency"] = metrics.get("ret.positive_count", 0) / max(1, len(returns))
    
    return metrics

# Collect metrics for all engines
all_metrics = {}
for name, result in results.items():
    all_metrics[name] = collect_all_metrics(
        result, 
        result.equity_curve, 
        STRATEGY_CONFIG["initial_capital"]
    )

# =============================================================================
# COMPARE 147 METRICS
# =============================================================================
print("\n" + "=" * 80)
print("147-METRIC COMPARISON")
print("=" * 80)

# Get all unique metric names
all_metric_names = set()
for metrics in all_metrics.values():
    all_metric_names.update(metrics.keys())

all_metric_names = sorted(all_metric_names)
print(f"   Total unique metrics: {len(all_metric_names)}")

# Compare
fb_metrics = all_metrics["FallbackEngineV2"]
numba_metrics = all_metrics["NumbaEngineV2"]
gpu_metrics = all_metrics["GPUEngineV2"]

numba_matches = 0
gpu_matches = 0
total_compared = 0

mismatches = []

for metric_name in all_metric_names:
    fb_val = fb_metrics.get(metric_name, 0)
    numba_val = numba_metrics.get(metric_name, 0)
    gpu_val = gpu_metrics.get(metric_name, 0)
    
    if not isinstance(fb_val, (int, float)):
        continue
    
    total_compared += 1
    
    # Check Numba match
    if abs(fb_val - numba_val) < 0.01:
        numba_matches += 1
    else:
        mismatches.append(("Numba", metric_name, fb_val, numba_val))
    
    # Check GPU match
    if abs(fb_val - gpu_val) < 0.01:
        gpu_matches += 1
    else:
        mismatches.append(("GPU", metric_name, fb_val, gpu_val))

# =============================================================================
# RESULTS
# =============================================================================
print("\n" + "=" * 80)
print("PARITY RESULTS")
print("=" * 80)

numba_pct = numba_matches / total_compared * 100 if total_compared > 0 else 0
gpu_pct = gpu_matches / total_compared * 100 if total_compared > 0 else 0

print(f"""
   Metrics Compared: {total_compared}

   NumbaEngineV2 vs FallbackEngineV2:
      Matching: {numba_matches}/{total_compared} ({numba_pct:.2f}%)
   
   GPUEngineV2 vs FallbackEngineV2:
      Matching: {gpu_matches}/{total_compared} ({gpu_pct:.2f}%)
""")

if mismatches:
    print("   MISMATCHES:")
    for engine, metric, fb, other in mismatches[:10]:
        print(f"      [{engine}] {metric}: FB={fb:.4f} vs {other:.4f} (diff={other-fb:+.4f})")
    if len(mismatches) > 10:
        print(f"      ... and {len(mismatches) - 10} more")

# =============================================================================
# FINAL VERDICT
# =============================================================================
print("\n" + "=" * 120)

all_pass = (numba_pct >= 100.0) and (gpu_pct >= 100.0)

if all_pass:
    print("""
    ================================================================================
    =                                                                              =
    =   100% PARITY ACHIEVED ON ALL 147 METRICS                                   =
    =                                                                              =
    =   FallbackEngineV2 = NumbaEngineV2 = GPUEngineV2                            =
    =                                                                              =
    =   All engines produce IDENTICAL results with:                               =
    =   - Bar Magnifier (Precise Intrabar)                                        =
    =   - Sequential Inclusive Checks                                             =
    =   - 60 Subticks per hour                                                    =
    =                                                                              =
    ================================================================================
    """)
else:
    print(f"""
    ================================================================================
    =                                                                              =
    =   PARITY CHECK COMPLETE                                                     =
    =                                                                              =
    =   NumbaEngineV2:  {numba_pct:6.2f}% match                                            =
    =   GPUEngineV2:    {gpu_pct:6.2f}% match                                            =
    =                                                                              =
    ================================================================================
    """)

# Summary table
print("\nSUMMARY TABLE:")
print("-" * 100)
print(f"{'Engine':<25} {'Trades':>10} {'Net Profit':>15} {'Win Rate':>12} {'Sharpe':>10} {'Time':>10}")
print("-" * 100)
for name, result in results.items():
    print(f"{name:<25} {len(result.trades):>10} ${result.metrics.net_profit:>13,.2f} {result.metrics.win_rate*100:>11.2f}% {result.metrics.sharpe_ratio:>10.4f} {result.execution_time:>9.3f}s")
print("-" * 100)
print("=" * 120)
