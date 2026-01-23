import json
from datetime import datetime

from backend.backtesting.fast_optimizer import FastGridOptimizer, load_candles_fast

DB = r"d:/bybit_strategy_tester_v2/data.sqlite3"
SYMBOL = "BTCUSDT"
INTERVAL = "15"
START = datetime(2025, 1, 1)
END = datetime(2025, 1, 11)

# Small grid for fast deterministic test
rsi_period_range = [14, 21]
rsi_overbought_range = [70]
rsi_oversold_range = [30]
stop_loss_range = [0.10]
take_profit_range = [0.015]

print("Loading candles...")
candles_arr = load_candles_fast(DB, SYMBOL, INTERVAL, START, END)
if candles_arr is None:
    print("ERROR: no candle data returned")
    raise SystemExit(1)

import pandas as pd

candles = pd.DataFrame(
    candles_arr, columns=["open_time", "open", "high", "low", "close", "volume"]
)
print(f"Candles loaded: {len(candles)} rows")

opt = FastGridOptimizer()

results_summary = []
for run in range(1, 4):
    print(f"Run {run} — optimizing (FastGridOptimizer)...")
    res = opt.optimize(
        candles=candles,
        rsi_period_range=rsi_period_range,
        rsi_overbought_range=rsi_overbought_range,
        rsi_oversold_range=rsi_oversold_range,
        stop_loss_range=stop_loss_range,
        take_profit_range=take_profit_range,
        initial_capital=10000.0,
        leverage=10,
        commission=0.0004,
        slippage=0.0005,
        optimize_metric="net_profit",
        direction="both",
    )

    # FastGridOptimizer returns FastOptimizationResult dataclass
    best = {
        "run": run,
        "best_score": res.best_score,
        "best_params": res.best_params,
        "best_metrics": res.best_metrics,
        "execution_time": res.execution_time_seconds,
    }
    print(json.dumps(best, default=str, indent=2))
    results_summary.append(best)

all_equal = all(
    results_summary[0]["best_params"] == r["best_params"]
    and results_summary[0]["best_score"] == r["best_score"]
    for r in results_summary[1:]
)
print(
    "\nDeterministic check (FastGridOptimizer): best result equal across runs ->",
    all_equal,
)
print(json.dumps(results_summary, default=str, indent=2))
