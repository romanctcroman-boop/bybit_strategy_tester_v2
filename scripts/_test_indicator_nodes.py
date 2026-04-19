"""
Test CCI, Williams %R, ADX, MA, Supertrend and other indicator nodes
using the same architecture as Strategy_MACD_04.

Strategy_MACD_04 pattern:
  [macd].long  -->  [strategy].entry_long
  [macd].short -->  [strategy].entry_short
  [static_sltp].config --> [strategy].sl_tp

For indicators that output only 'value' (CCI, WilliamsR, ADX, MA family):
  [cci].value  -->  [condition/greater_than].left
  [constant].value --> [condition/greater_than].right
  [condition/greater_than].result --> [strategy].entry_long

This script builds minimal graphs for each indicator and runs them through
StrategyBuilderAdapter.generate_signals() to verify they produce valid signals.
"""

import sys
import traceback
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter  # noqa: E402

# ─── Synthetic OHLCV data ────────────────────────────────────────────────────
np.random.seed(42)
N = 500
dates = pd.date_range("2025-01-01", periods=N, freq="30min")
close = pd.Series(3000 + np.cumsum(np.random.randn(N) * 10), index=dates)
df = pd.DataFrame(
    {
        "open": close * (1 + np.random.randn(N) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(N)) * 0.002),
        "low": close * (1 - np.abs(np.random.randn(N)) * 0.002),
        "close": close,
        "volume": np.abs(np.random.randn(N) * 1000) + 500,
    },
    index=dates,
)


def make_graph(blocks: list[dict], connections: list[dict]) -> dict:
    """Build a minimal strategy graph dict."""
    strategy_block = {
        "id": "main_strategy",
        "type": "strategy",
        "category": "main",
        "name": "Strategy",
        "isMain": True,
        "params": {},
    }
    return {
        "blocks": [strategy_block] + blocks,
        "connections": connections,
    }


def conn(src_block_id: str, src_port: str, tgt_block_id: str, tgt_port: str) -> dict:
    return {
        "id": f"c_{src_block_id}_{src_port}",
        "source": {"blockId": src_block_id, "portId": src_port},
        "target": {"blockId": tgt_block_id, "portId": tgt_port},
    }


def run_graph(name: str, graph: dict, ohlcv: pd.DataFrame | None = None) -> None:
    """Run adapter and show signal counts."""
    data = ohlcv if ohlcv is not None else df
    try:
        adapter = StrategyBuilderAdapter(graph)
        result = adapter.generate_signals(data)
        # SignalResult has .entries (long) and .short_entries (short) as bool Series
        n_long = int(result.entries.sum()) if result.entries is not None else 0
        n_short = int(result.short_entries.sum()) if result.short_entries is not None else 0
        total = n_long + n_short
        status = "OK" if total > 0 else "ZERO SIGNALS"
        print(f"  [{status}]  long={n_long:4d}  short={n_short:4d}  [{name}]")
    except Exception as e:
        print(f"  [ERROR]  [{name}]: {e}")
        traceback.print_exc()


# ─── Oscillating OHLCV (for tests that need price reversals) ─────────────────
# Sine wave price series: guaranteed multiple up/down trend reversals
_N_OSD = 500
_dates_osd = pd.date_range("2025-01-01", periods=_N_OSD, freq="30min")
_t = np.linspace(0, 8 * np.pi, _N_OSD)  # 4 full cycles → ~8 trend changes
_close_osd = 3000 + 400 * np.sin(_t) + np.random.RandomState(7).randn(_N_OSD) * 5
df_osc = pd.DataFrame(
    {
        "open": _close_osd * (1 + np.random.RandomState(8).randn(_N_OSD) * 0.001),
        "high": _close_osd * (1 + np.abs(np.random.RandomState(9).randn(_N_OSD)) * 0.003),
        "low": _close_osd * (1 - np.abs(np.random.RandomState(10).randn(_N_OSD)) * 0.003),
        "close": _close_osd,
        "volume": np.abs(np.random.RandomState(11).randn(_N_OSD) * 1000) + 500,
    },
    index=_dates_osd,
)


print("\n" + "=" * 70)
print("STRATEGY BUILDER INDICATOR NODE TESTS")
print("=" * 70)

# ─── 1. MACD (reference — same as Strategy_MACD_04) ─────────────────────────
print("\n── Momentum / Oscillators ────────────────────────────────────────────")

graph = make_graph(
    blocks=[
        {
            "id": "b_macd",
            "type": "macd",
            "category": "indicator",
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "use_macd_cross_signal": True,
                "disable_signal_memory": True,
                "opposite_macd_cross_signal": True,
            },
        }
    ],
    connections=[
        conn("b_macd", "long", "main_strategy", "entry_long"),
        conn("b_macd", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("MACD (reference)", graph)

# ─── 2. RSI — direct long/short ─────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_rsi",
            "type": "rsi",
            "category": "indicator",
            "params": {"period": 14, "overbought": 70, "oversold": 30, "signal_mode": "level"},
        }
    ],
    connections=[
        conn("b_rsi", "long", "main_strategy", "entry_long"),
        conn("b_rsi", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("RSI (direct long/short)", graph)

# ─── 3. Stochastic — direct long/short ──────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_stoch",
            "type": "stochastic",
            "category": "indicator",
            "params": {"k_period": 14, "d_period": 3, "overbought": 80, "oversold": 20},
        }
    ],
    connections=[
        conn("b_stoch", "long", "main_strategy", "entry_long"),
        conn("b_stoch", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Stochastic (direct long/short)", graph)

# ─── 4. QQE — direct long/short ─────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_qqe",
            "type": "qqe",
            "category": "indicator",
            "params": {"rsi_period": 14, "smoothing": 5, "qqe_factor": 4.238},
        }
    ],
    connections=[
        conn("b_qqe", "long", "main_strategy", "entry_long"),
        conn("b_qqe", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("QQE (direct long/short)", graph)

# ─── 5. CCI — via greater_than condition ────────────────────────────────────
# CCI value → greater_than(> +100) = long signal (overbought breakout)
# CCI value → less_than(< -100) = short signal (oversold breakout)
graph = make_graph(
    blocks=[
        {"id": "b_cci", "type": "cci", "category": "indicator", "params": {"period": 20}},
        {"id": "b_const_long", "type": "constant", "category": "input", "params": {"value": 100}},
        {"id": "b_const_short", "type": "constant", "category": "input", "params": {"value": -100}},
        {"id": "b_gt", "type": "greater_than", "category": "condition", "params": {}},
        {"id": "b_lt", "type": "less_than", "category": "condition", "params": {}},
    ],
    connections=[
        conn("b_cci", "value", "b_gt", "a"),
        conn("b_const_long", "value", "b_gt", "b"),
        conn("b_cci", "value", "b_lt", "a"),
        conn("b_const_short", "value", "b_lt", "b"),
        conn("b_gt", "result", "main_strategy", "entry_long"),
        conn("b_lt", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("CCI via greater_than/less_than conditions", graph)

# ─── 6. CCI Filter — direct long/short ──────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_cci_f",
            "type": "cci_filter",
            "category": "indicator",
            "params": {"period": 20, "cci_long_more": 0, "cci_short_less": 0},
        }
    ],
    connections=[
        conn("b_cci_f", "long", "main_strategy", "entry_long"),
        conn("b_cci_f", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("CCI Filter (direct long/short)", graph)

# ─── 7. Williams %R — via condition ─────────────────────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_wr", "type": "williams_r", "category": "indicator", "params": {"period": 14}},
        {"id": "b_c_long", "type": "constant", "category": "input", "params": {"value": -20}},
        {"id": "b_c_short", "type": "constant", "category": "input", "params": {"value": -80}},
        {"id": "b_gt2", "type": "greater_than", "category": "condition", "params": {}},
        {"id": "b_lt2", "type": "less_than", "category": "condition", "params": {}},
    ],
    connections=[
        conn("b_wr", "value", "b_gt2", "a"),
        conn("b_c_long", "value", "b_gt2", "b"),  # WR > -20 → overbought → short in TV
        conn("b_wr", "value", "b_lt2", "a"),
        conn("b_c_short", "value", "b_lt2", "b"),  # WR < -80 → oversold → long
        conn("b_gt2", "result", "main_strategy", "entry_short"),
        conn("b_lt2", "result", "main_strategy", "entry_long"),
    ],
)
run_graph("Williams %R via greater_than/less_than", graph)

print("\n── Trend — MA family ─────────────────────────────────────────────────")

# ─── 8. EMA crossover (fast crosses above slow = long) ──────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_ema_fast", "type": "ema", "category": "indicator", "params": {"period": 9}},
        {"id": "b_ema_slow", "type": "ema", "category": "indicator", "params": {"period": 21}},
        {"id": "b_cross_up", "type": "crossover", "category": "condition", "params": {}},
        {"id": "b_cross_dn", "type": "crossunder", "category": "condition", "params": {}},
    ],
    connections=[
        conn("b_ema_fast", "value", "b_cross_up", "a"),
        conn("b_ema_slow", "value", "b_cross_up", "b"),
        conn("b_ema_fast", "value", "b_cross_dn", "a"),
        conn("b_ema_slow", "value", "b_cross_dn", "b"),
        conn("b_cross_up", "result", "main_strategy", "entry_long"),
        conn("b_cross_dn", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("EMA fast/slow crossover", graph)

# ─── 9. SMA crossover ───────────────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_sma_f", "type": "sma", "category": "indicator", "params": {"period": 10}},
        {"id": "b_sma_s", "type": "sma", "category": "indicator", "params": {"period": 50}},
        {"id": "b_co", "type": "crossover", "category": "condition", "params": {}},
        {"id": "b_cu", "type": "crossunder", "category": "condition", "params": {}},
    ],
    connections=[
        conn("b_sma_f", "value", "b_co", "a"),
        conn("b_sma_s", "value", "b_co", "b"),
        conn("b_sma_f", "value", "b_cu", "a"),
        conn("b_sma_s", "value", "b_cu", "b"),
        conn("b_co", "result", "main_strategy", "entry_long"),
        conn("b_cu", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("SMA fast/slow crossover", graph)

# ─── 10. Two MAs block (built-in crossover) ─────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_2ma",
            "type": "two_mas",
            "category": "indicator",
            "params": {"fast_period": 9, "slow_period": 21, "ma_type": "ema"},
        }
    ],
    connections=[
        conn("b_2ma", "long", "main_strategy", "entry_long"),
        conn("b_2ma", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Two MAs block (built-in crossover)", graph)

print("\n── Trend — ADX / Supertrend ─────────────────────────────────────────")

# ─── 11. ADX — filter (only trade when trend strong) ────────────────────────
# ADX alone gives no direction — combine with MA crossover
graph = make_graph(
    blocks=[
        {"id": "b_ema_f", "type": "ema", "category": "indicator", "params": {"period": 9}},
        {"id": "b_ema_sl", "type": "ema", "category": "indicator", "params": {"period": 21}},
        {"id": "b_adx", "type": "adx", "category": "indicator", "params": {"period": 14}},
        {"id": "b_adx_const", "type": "constant", "category": "input", "params": {"value": 25}},
        {"id": "b_co2", "type": "crossover", "category": "condition", "params": {}},
        {"id": "b_cu2", "type": "crossunder", "category": "condition", "params": {}},
        {"id": "b_adx_gt", "type": "greater_than", "category": "condition", "params": {}},
        {"id": "b_and_l", "type": "and", "category": "logic", "params": {}},
        {"id": "b_and_s", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_ema_f", "value", "b_co2", "a"),
        conn("b_ema_sl", "value", "b_co2", "b"),
        conn("b_ema_f", "value", "b_cu2", "a"),
        conn("b_ema_sl", "value", "b_cu2", "b"),
        conn("b_adx", "value", "b_adx_gt", "a"),
        conn("b_adx_const", "value", "b_adx_gt", "b"),
        conn("b_co2", "result", "b_and_l", "a"),
        conn("b_adx_gt", "result", "b_and_l", "b"),
        conn("b_cu2", "result", "b_and_s", "a"),
        conn("b_adx_gt", "result", "b_and_s", "b"),
        conn("b_and_l", "result", "main_strategy", "entry_long"),
        conn("b_and_s", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("ADX filter + EMA crossover (AND logic)", graph)

# ─── 12. ADX Filter block (built-in) ────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_2ma2",
            "type": "two_mas",
            "category": "indicator",
            "params": {"fast_period": 9, "slow_period": 21, "ma_type": "ema"},
        },
        {
            "id": "b_adxf",
            "type": "adx_filter",
            "category": "filter",
            "params": {"period": 14, "threshold": 15},
        },  # low threshold → more signals on synthetic data
        {"id": "b_andl2", "type": "and", "category": "logic", "params": {}},
        {"id": "b_ands2", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_2ma2", "long", "b_andl2", "a"),
        conn("b_adxf", "buy", "b_andl2", "b"),
        conn("b_2ma2", "short", "b_ands2", "a"),
        conn("b_adxf", "sell", "b_ands2", "b"),
        conn("b_andl2", "result", "main_strategy", "entry_long"),
        conn("b_ands2", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("ADX Filter block + Two MAs", graph)

# ─── 13. Supertrend — direct long/short ─────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_st",
            "type": "supertrend",
            "category": "indicator",
            "params": {
                "period": 10,
                "multiplier": 3.0,
                "use_supertrend": True,
                "generate_on_trend_change": True,
                "opposite_signal": False,
            },
        }
    ],
    connections=[
        conn("b_st", "long", "main_strategy", "entry_long"),
        conn("b_st", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Supertrend (on_trend_change=True)", graph, ohlcv=df_osc)

# ─── 14. Supertrend — continuous filter mode ────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_st2",
            "type": "supertrend",
            "category": "indicator",
            "params": {
                "period": 10,
                "multiplier": 3.0,
                "use_supertrend": True,
                "generate_on_trend_change": False,
                "opposite_signal": False,
            },
        }
    ],
    connections=[
        conn("b_st2", "long", "main_strategy", "entry_long"),
        conn("b_st2", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Supertrend (continuous filter mode)", graph)

print("\n── Bands / Channels ──────────────────────────────────────────────────")

# ─── 15. Bollinger Bands — price crosses upper/lower ────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_bb", "type": "bollinger", "category": "indicator", "params": {"period": 20, "std_dev": 2.0}},
        # Use constant blocks for price levels — "price" input block can be tricky
        # Instead wire bb output to crossover using close as indicator input
        {"id": "b_close_ema", "type": "ema", "category": "indicator", "params": {"period": 1}},  # close proxy
        {"id": "b_co_bb", "type": "crossover", "category": "condition", "params": {}},
        {"id": "b_cu_bb", "type": "crossunder", "category": "condition", "params": {}},
    ],
    connections=[
        # close (EMA-1 ≈ close) crosses above upper → short (mean reversion)
        conn("b_close_ema", "value", "b_co_bb", "a"),
        conn("b_bb", "upper", "b_co_bb", "b"),
        # close crosses below lower → long
        conn("b_close_ema", "value", "b_cu_bb", "a"),
        conn("b_bb", "lower", "b_cu_bb", "b"),
        conn("b_cu_bb", "result", "main_strategy", "entry_long"),
        conn("b_co_bb", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("Bollinger Bands crossover (price vs bands)", graph)

print("\n── Volatility ────────────────────────────────────────────────────────")

# ─── 16. ATR Volatility filter ──────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_2ma3", "type": "two_mas", "category": "indicator", "params": {"fast_period": 9, "slow_period": 21}},
        {
            "id": "b_atrv",
            "type": "atr_volatility",
            "category": "indicator",
            "params": {"period": 14, "min_atr_pct": 0.3, "max_atr_pct": 5.0},
        },
        {"id": "b_and_av_l", "type": "and", "category": "logic", "params": {}},
        {"id": "b_and_av_s", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_2ma3", "long", "b_and_av_l", "a"),
        conn("b_atrv", "long", "b_and_av_l", "b"),
        conn("b_2ma3", "short", "b_and_av_s", "a"),
        conn("b_atrv", "short", "b_and_av_s", "b"),
        conn("b_and_av_l", "result", "main_strategy", "entry_long"),
        conn("b_and_av_s", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("ATR Volatility filter + Two MAs", graph)

print("\n── Volume ────────────────────────────────────────────────────────────")

# ─── 17. Volume filter ──────────────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_2ma4", "type": "two_mas", "category": "indicator", "params": {"fast_period": 9, "slow_period": 21}},
        {"id": "b_vf", "type": "volume_filter", "category": "indicator", "params": {"period": 20, "multiplier": 1.5}},
        {"id": "b_and_vl", "type": "and", "category": "logic", "params": {}},
        {"id": "b_and_vs", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_2ma4", "long", "b_and_vl", "a"),
        conn("b_vf", "long", "b_and_vl", "b"),
        conn("b_2ma4", "short", "b_and_vs", "a"),
        conn("b_vf", "short", "b_and_vs", "b"),
        conn("b_and_vl", "result", "main_strategy", "entry_long"),
        conn("b_and_vs", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("Volume Filter + Two MAs", graph)

print("\n── Divergence ────────────────────────────────────────────────────────")

# ─── 18. Divergence block ───────────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_div",
            "type": "divergence",
            "category": "divergence",
            "params": {
                "pivot_interval": 2,  # small window → more pivots on 500-bar sine data
                "act_without_confirmation": True,
                "use_divergence_rsi": True,  # correct param name (not "indicator")
                "rsi_period": 14,
            },
        }
    ],
    connections=[
        conn("b_div", "bullish", "main_strategy", "entry_long"),
        conn("b_div", "bearish", "main_strategy", "entry_short"),
    ],
)
run_graph("Divergence (RSI)", graph, ohlcv=df_osc)

print("\n── Price Action ──────────────────────────────────────────────────────")

# ─── 19. Engulfing pattern ──────────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_eng",
            "type": "engulfing",
            "category": "price_action",
            "params": {},
        }
    ],
    connections=[
        conn("b_eng", "long", "main_strategy", "entry_long"),
        conn("b_eng", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Engulfing pattern", graph)

# ─── 20. Hammer pattern ─────────────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_ham",
            "type": "hammer",
            "category": "price_action",
            "params": {},
        }
    ],
    connections=[
        conn("b_ham", "long", "main_strategy", "entry_long"),
        conn("b_ham", "short", "main_strategy", "entry_short"),
    ],
)
run_graph("Hammer pattern", graph)

print("\n── Complex: RSI + ADX filter ─────────────────────────────────────────")

# ─── 21. RSI + ADX filter (AND) ─────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {
            "id": "b_rsi2",
            "type": "rsi",
            "category": "indicator",
            "params": {"period": 14, "overbought": 70, "oversold": 30, "signal_mode": "level"},
        },
        {"id": "b_adx2", "type": "adx", "category": "indicator", "params": {"period": 14}},
        {"id": "b_adx_c2", "type": "constant", "category": "input", "params": {"value": 25}},
        {"id": "b_adx_gt2", "type": "greater_than", "category": "condition", "params": {}},
        {"id": "b_and2l", "type": "and", "category": "logic", "params": {}},
        {"id": "b_and2s", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_adx2", "value", "b_adx_gt2", "a"),
        conn("b_adx_c2", "value", "b_adx_gt2", "b"),
        conn("b_rsi2", "long", "b_and2l", "a"),
        conn("b_adx_gt2", "result", "b_and2l", "b"),
        conn("b_rsi2", "short", "b_and2s", "a"),
        conn("b_adx_gt2", "result", "b_and2s", "b"),
        conn("b_and2l", "result", "main_strategy", "entry_long"),
        conn("b_and2s", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("RSI + ADX filter (AND logic)", graph)

print("\n── Complex: CCI + Supertrend filter ─────────────────────────────────")

# ─── 22. CCI + Supertrend filter ────────────────────────────────────────────
graph = make_graph(
    blocks=[
        {"id": "b_cci2", "type": "cci", "category": "indicator", "params": {"period": 20}},
        {"id": "b_c_l2", "type": "constant", "category": "input", "params": {"value": 100}},
        {"id": "b_c_s2", "type": "constant", "category": "input", "params": {"value": -100}},
        {"id": "b_gt_l2", "type": "greater_than", "category": "condition", "params": {}},
        {"id": "b_lt_s2", "type": "less_than", "category": "condition", "params": {}},
        {
            "id": "b_st3",
            "type": "supertrend",
            "category": "indicator",
            "params": {"period": 10, "multiplier": 3.0, "use_supertrend": True, "generate_on_trend_change": False},
        },
        {"id": "b_and_cl", "type": "and", "category": "logic", "params": {}},
        {"id": "b_and_cs", "type": "and", "category": "logic", "params": {}},
    ],
    connections=[
        conn("b_cci2", "value", "b_gt_l2", "a"),
        conn("b_c_l2", "value", "b_gt_l2", "b"),
        conn("b_cci2", "value", "b_lt_s2", "a"),
        conn("b_c_s2", "value", "b_lt_s2", "b"),
        conn("b_gt_l2", "result", "b_and_cl", "a"),
        conn("b_st3", "long", "b_and_cl", "b"),
        conn("b_lt_s2", "result", "b_and_cs", "a"),
        conn("b_st3", "short", "b_and_cs", "b"),
        conn("b_and_cl", "result", "main_strategy", "entry_long"),
        conn("b_and_cs", "result", "main_strategy", "entry_short"),
    ],
)
run_graph("CCI > 100 AND Supertrend bullish", graph)

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
