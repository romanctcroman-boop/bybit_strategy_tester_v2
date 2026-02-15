r"""
AI Agent Comprehensive Understanding Test v3 — Strategy Builder Mastery

Tests whether DeepSeek, Qwen, and Perplexity correctly understand
the FULL Strategy Builder workflow, block wiring, exit/risk management,
and filter blocks — NOT just individual indicator params (those are in v2).

v2 tests (test_agent_node_understanding.py):
  ✅ RSI params (19 checks)
  ✅ MACD params (18 checks)
  ✅ Optimization ranges (71 checks)

v3 tests (this file):
  🆕 Strategy Flow — full workflow understanding
  🆕 Block Wiring — port types, connections, Strategy node
  🆕 Exit/Risk Management — static_sltp, trailing, ATR exit, DCA
  🆕 Filter Blocks — supertrend_filter (3 TFs), stochastic_filter

Usage:
    cd D:\bybit_strategy_tester_v2
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py

    # Test only one agent:
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py --agent deepseek

    # Test only one scenario:
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py --node flow
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py --node wiring
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py --node exits
    .venv\Scripts\python.exe scripts\test_agent_comprehensive.py --node filters
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider, LLMResponse
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient

# Use KeyManager for secure API key access
try:
    from backend.security.key_manager import KeyManager, get_key_manager

    _key_manager: KeyManager | None = get_key_manager()
except ImportError:
    _key_manager = None  # type: ignore[assignment]


def _get_api_key(key_name: str) -> str | None:
    """Get API key from KeyManager or environment."""
    if _key_manager:
        try:
            return _key_manager.get_decrypted_key(key_name)
        except Exception:
            pass
    return os.environ.get(key_name)


# ═══════════════════════════════════════════════════════════════════
# Data class
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ValidationResult:
    """Result of a single agent x node test."""

    agent: str
    node: str
    passed: bool
    score: float
    checks: dict[str, bool] = field(default_factory=dict)
    raw_response: str = ""
    parsed_json: dict | None = None
    error: str = ""
    latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# System prompts
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "deepseek": (
        "You are an expert quantitative trading system architect. You deeply understand "
        "the Strategy Builder visual node editor and all its block types, port types, "
        "connection rules, and workflow. "
        "You must use EXACT parameter names, port IDs, and block type IDs from the system. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
    "qwen": (
        "You are an expert in visual strategy building for algorithmic trading. "
        "You understand the Strategy Builder's block categories: indicators, conditions, "
        "actions, logic, filters, exits, position_sizing, entry_refinement, risk_controls, "
        "sessions, time_management. "
        "Port types: 'data' (indicator values), 'condition' (boolean signals), 'config' (exit settings). "
        "Strategy node has 5 inputs: entry_long, entry_short, exit_long, exit_short, sl_tp. "
        "Exit blocks output 'config' type ports that connect to Strategy's sl_tp port. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
    "perplexity": (
        "You are a trading strategy architect working with a visual Strategy Builder. "
        "Key concepts: blocks have typed ports (data, condition, config). "
        "Connections must match port types: data→data, condition→condition, config→config. "
        "The Strategy node is the central hub with ports: entry_long, entry_short (condition), "
        "exit_long, exit_short (condition), sl_tp (config). "
        "Exit/risk blocks (static_sltp, trailing_stop_exit, atr_exit, dca) output 'config' → sl_tp. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
}


# ═══════════════════════════════════════════════════════════════════
# TEST 1: STRATEGY FLOW — full workflow understanding
# ═══════════════════════════════════════════════════════════════════

FLOW_TEST_PROMPT = """
You are working with a visual Strategy Builder that uses a node-based editor.
Below is the COMPLETE architecture you must understand.

=== BLOCK CATEGORIES (11 total) ===
1. indicators    — RSI, MACD, EMA, SMA, Bollinger, ATR, Stochastic, SuperTrend, Ichimoku,
                   VWAP, OBV, CMF, CCI, Williams_R, MFI, ROC, Aroon, Parabolic SAR,
                   Donchian, Keltner, StochRSI, WMA, DEMA, TEMA, Hull MA, StdDev, ADX, QQE
2. conditions    — crossover, crossunder, greater_than, less_than, equals, between
3. actions       — buy, sell, close, stop_loss, take_profit, trailing_stop
4. logic         — and, or, not, delay, filter
5. filters       — supertrend_filter, two_ma_filter, stochastic_filter, qqe_filter,
                   rsi_filter(=rsi), macd_filter(=macd), cci_filter, momentum_filter,
                   dmi_filter, cmf_filter, bop_filter, levels_filter, atr_filter,
                   volume_compare_filter, divergence_filter, price_action_filter,
                   accumulation_filter, linreg_filter, rvi_filter, highest_lowest_filter,
                   trend_filter, volume_filter, volatility_filter, time_filter,
                   price_filter, block_worse_filter
6. exits         — static_sltp, trailing_stop_exit, atr_exit, time_exit, session_exit,
                   signal_exit, indicator_exit, break_even_exit, partial_close,
                   multi_tp_exit, chandelier_exit,
                   rsi_close, stoch_close, channel_close, ma_close, psar_close, time_bars_close
7. position_sizing — fixed_size, percent_balance, risk_percent, atr_sizing, kelly_criterion
8. entry_refinement — dca, grid_orders, average_down, reentry, scale_in,
                       martingale, anti_martingale, indent_order
9. risk_controls  — max_daily_loss, max_drawdown, max_trades_day, consecutive_loss, cooloff_period
10. sessions      — active_hours, trading_days, session_filter, news_filter, weekend_close
11. time_management — time_stop, max_duration, session_close, intraday_only

=== PORT TYPES (3 types) ===
- data:      numeric series (RSI value, EMA value, price OHLC, etc.)
- condition: boolean signals (crossover result, range filter match, etc.)
- config:    exit/risk configuration (SL/TP settings, DCA settings, etc.)

=== PORT TYPE COMPATIBILITY ===
- data → data:           ✅ (e.g., RSI value → crossover input A)
- condition → condition:  ✅ (e.g., crossover result → AND input A)
- config → config:        ✅ (e.g., static_sltp config → Strategy sl_tp)
- data → condition:       ❌ INCOMPATIBLE
- condition → data:       ❌ INCOMPATIBLE
- config → condition:     ❌ INCOMPATIBLE

=== STRATEGY NODE (central hub) ===
The Strategy node is the MAIN node in every strategy. It has these INPUT ports:
- entry_long   (type: condition) — when to open LONG position
- entry_short  (type: condition) — when to open SHORT position
- exit_long    (type: condition) — when to close LONG position
- exit_short   (type: condition) — when to close SHORT position
- sl_tp        (type: config)    — stop loss / take profit configuration

Strategy node has NO output ports — it is the endpoint.

=== WORKFLOW (correct order) ===
1. Create strategy (name, symbol, timeframe)
2. Add indicator blocks (RSI, MACD, EMA, etc.)
3. Add condition/filter blocks to process indicator outputs
4. Add logic blocks (AND/OR) to combine conditions
5. Add exit blocks (static_sltp, trailing_stop, etc.)
6. Connect ports: indicator outputs → condition inputs → logic → Strategy node
7. Connect exit block config output → Strategy sl_tp port
8. Validate strategy (check all required connections)
9. Run backtest (symbol, date range, initial capital, commission 0.07%)

=== CONNECTION FORMAT ===
Each connection is: { source: { blockId: "block_1", portId: "value" },
                      target: { blockId: "block_2", portId: "a" } }

=== YOUR TASK ===
Design a complete RSI mean-reversion strategy workflow. List:
1. All blocks needed (with their IDs, types, categories)
2. All connections between blocks (source port → target port)
3. The correct workflow steps in order

IMPORTANT: RSI block ports (value, long, short) are ALL type "data", NOT "condition".
Since Strategy.entry_long requires type "condition", you CANNOT connect RSI directly to Strategy.
You MUST use condition blocks (less_than, greater_than) as intermediaries to convert data→condition.

The strategy should:
- Use RSI indicator (period=14) for entry signals
- RSI value (data) → less_than condition (with constant 30) → entry_long on Strategy node
- RSI value (data) → greater_than condition (with constant 70) → entry_short on Strategy node
- Use static_sltp exit block, its "config" output → Strategy sl_tp port
- No exit_long / exit_short signals (leave unconnected)

Return ONLY valid JSON:
{
  "blocks": [
    {"id": "<string>", "type": "<block_type>", "category": "<category>", "name": "<display_name>"}
  ],
  "connections": [
    {"source": {"blockId": "<id>", "portId": "<port_id>"}, "target": {"blockId": "<id>", "portId": "<port_id>"}}
  ],
  "workflow_steps": ["step 1 description", "step 2 description", ...],
  "port_types_explanation": {
    "data": "<what data ports carry>",
    "condition": "<what condition ports carry>",
    "config": "<what config ports carry>"
  },
  "strategy_node_ports": {
    "entry_long": "<port type>",
    "entry_short": "<port type>",
    "exit_long": "<port type>",
    "exit_short": "<port type>",
    "sl_tp": "<port type>"
  },
  "reasoning": "Explain the signal flow from RSI → Strategy node and SL/TP → Strategy node"
}
"""


# ═══════════════════════════════════════════════════════════════════
# TEST 2: BLOCK WIRING — port types, connections, compatibility
# ═══════════════════════════════════════════════════════════════════

WIRING_TEST_PROMPT = """
You are a Strategy Builder expert. Test your knowledge of block ports and wiring.

=== BLOCK PORT REFERENCE ===

Indicators (output data ports, no inputs):
  rsi:         outputs: [value(data), long(data), short(data)]
  macd:        outputs: [macd(data), signal(data), hist(data), long(data), short(data)]
  ema:         outputs: [value(data)]
  sma:         outputs: [value(data)]
  bollinger:   outputs: [upper(data), middle(data), lower(data)]
  atr:         outputs: [value(data)]
  stochastic:  outputs: [k(data), d(data)]
  supertrend:  outputs: [supertrend(data), direction(data), upper(data), lower(data)]
  ichimoku:    outputs: [tenkan_sen(data), kijun_sen(data), senkou_span_a(data), senkou_span_b(data), chikou_span(data)]
  aroon:       outputs: [up(data), down(data), oscillator(data)]

Conditions (input data, output condition):
  crossover:   inputs: [a(data), b(data)]    → outputs: [result(condition)]
  crossunder:  inputs: [a(data), b(data)]    → outputs: [result(condition)]
  greater_than: inputs: [left(data), right(data)] → outputs: [result(condition)]
  less_than:   inputs: [left(data), right(data)] → outputs: [result(condition)]
  between:     inputs: [value(data), min(data), max(data)] → outputs: [result(condition)]

Logic (input condition, output condition):
  and:   inputs: [a(condition), b(condition)] → outputs: [result(condition)]
  or:    inputs: [a(condition), b(condition)] → outputs: [result(condition)]
  not:   inputs: [input(condition)]           → outputs: [result(condition)]

Actions (input condition):
  buy:   inputs: [signal(condition)] → outputs: [signal(condition)]
  sell:  inputs: [signal(condition)] → outputs: [signal(condition)]

Inputs (output data):
  price:    outputs: [open(data), high(data), low(data), close(data)]
  volume:   outputs: [value(data)]
  constant: outputs: [value(data)]

Exits (output config, no inputs except signal_exit):
  static_sltp:        outputs: [config(config)]
  trailing_stop_exit: outputs: [config(config)]
  atr_exit:           outputs: [config(config)]
  break_even_exit:    outputs: [config(config)]
  dca:                outputs: [config(config)]
  signal_exit:        inputs: [signal(condition)] → outputs: [config(config)]

Strategy Node (ALL inputs, no outputs):
  strategy:  inputs: [entry_long(condition), entry_short(condition),
                      exit_long(condition), exit_short(condition),
                      sl_tp(config)]

=== YOUR TASK ===
Design the wiring for a MACD + EMA crossover strategy with ATR exit:

Required blocks:
1. ema_fast (type: ema, period=12) — fast EMA
2. ema_slow (type: ema, period=26) — slow EMA
3. cross_up (type: crossover) — EMA fast crosses above EMA slow → LONG
4. cross_down (type: crossunder) — EMA fast crosses below EMA slow → SHORT
5. atr_exit_1 (type: atr_exit) — ATR-based SL/TP
6. strategy (type: strategy) — main Strategy node

Wire them correctly:
- ema_fast.value → cross_up.a AND cross_down.a
- ema_slow.value → cross_up.b AND cross_down.b
- cross_up.result → strategy.entry_long
- cross_down.result → strategy.entry_short
- atr_exit_1.config → strategy.sl_tp

Also answer these compatibility questions:
1. Can RSI.value (data) connect to strategy.entry_long (condition)?  → NO
2. Can crossover.result (condition) connect to strategy.entry_long (condition)?  → YES
3. Can static_sltp.config (config) connect to strategy.sl_tp (config)?  → YES
4. Can RSI.long (data) connect to crossover.a (data)?  → YES
5. Can static_sltp.config (config) connect to strategy.entry_long (condition)?  → NO
6. Can atr_exit.config connect to and.a?  → NO (config ≠ condition)

Return ONLY valid JSON:
{
  "connections": [
    {"source": {"blockId": "<id>", "portId": "<port_id>"}, "target": {"blockId": "<id>", "portId": "<port_id>"}}
  ],
  "compatibility_answers": {
    "rsi_value_to_entry_long": false,
    "crossover_result_to_entry_long": true,
    "static_sltp_config_to_sl_tp": true,
    "rsi_long_to_crossover_a": true,
    "static_sltp_config_to_entry_long": false,
    "atr_exit_config_to_and_a": false
  },
  "total_connections": <int>,
  "port_type_rules": {
    "data_to_data": "allowed",
    "condition_to_condition": "allowed",
    "config_to_config": "allowed",
    "data_to_condition": "<allowed or not>",
    "condition_to_data": "<allowed or not>",
    "config_to_condition": "<allowed or not>"
  },
  "reasoning": "Explain why port type matching is critical"
}
"""


# ═══════════════════════════════════════════════════════════════════
# TEST 3: EXIT/RISK MANAGEMENT — static_sltp, trailing, ATR, DCA
# ═══════════════════════════════════════════════════════════════════

EXITS_TEST_PROMPT = """
You must configure exit and risk management blocks for a trading strategy.
Below are the EXACT parameters for each exit block type.

=== STATIC SL/TP BLOCK (type: "static_sltp") ===
Category: exits
Output port: config (type: config) → connects to Strategy.sl_tp

Parameters:
1. take_profit_percent  (number, optimizable) — Take Profit in % from entry price
2. stop_loss_percent    (number, optimizable) — Stop Loss in % from entry price
3. sl_type              (select: "average_price" | "last_order") — SL calculation base
4. close_only_in_profit (bool) — Only close if currently in profit
5. activate_breakeven   (bool) — Enable break-even move after profit threshold
6. breakeven_activation_percent (number, optimizable) — % profit to activate break-even
7. new_breakeven_sl_percent     (number, optimizable) — New SL % after break-even activated

=== TRAILING STOP BLOCK (type: "trailing_stop_exit") ===
Category: exits
Output port: config (type: config) → connects to Strategy.sl_tp

Parameters:
1. activation_percent  (number, optimizable) — Min profit % to activate trailing
2. trailing_percent    (number, optimizable) — Trail distance in %
3. trail_type          (select: "percent" | "atr" | "points") — Trailing method

=== ATR EXIT BLOCK (type: "atr_exit") ===
Category: exits
Output port: config (type: config) → connects to Strategy.sl_tp

Parameters:
  --- ATR Stop Loss ---
1. use_atr_sl         (bool) — Enable ATR-based stop loss
2. atr_sl_on_wicks    (bool) — Check SL against wicks (if false, only bar close)
3. atr_sl_smoothing   (select: "WMA" | "RMA" | "SMA" | "EMA") — ATR smoothing method
4. atr_sl_period      (int, optimizable, range 1-150) — ATR calculation period
5. atr_sl_multiplier  (number, optimizable, range 0.1-4, step 0.1) — SL = multiplier x ATR
  --- ATR Take Profit ---
6. use_atr_tp         (bool) — Enable ATR-based take profit
7. atr_tp_on_wicks    (bool) — Check TP against wicks
8. atr_tp_smoothing   (select: "WMA" | "RMA" | "SMA" | "EMA") — ATR smoothing method
9. atr_tp_period      (int, optimizable, range 1-150) — ATR calculation period
10. atr_tp_multiplier (number, optimizable, range 0.1-4, step 0.1) — TP = multiplier x ATR

=== DCA BLOCK (type: "dca") ===
Category: entry_refinement
Output port: config (type: config) → connects to Strategy.sl_tp

Parameters:
1. grid_size_percent       (number, optimizable, range 1-100) — Total grid width in %
2. order_count             (int, optimizable, range 3-15) — Number of DCA orders
3. martingale_coefficient  (number, optimizable, range 1.0-1.8, step 0.1) — Volume multiplier per level
4. log_steps_coefficient   (number, optimizable, range 0.8-1.4, step 0.1) — Logarithmic order spacing
5. first_order_offset      (number, optimizable, range 0-10) — First order offset (0=market)
6. grid_trailing           (number, optimizable, range 0-30) — Grid trailing/cancel %

=== YOUR TASK ===
Configure ALL 4 exit blocks for a conservative BTC trend-following strategy:

1. static_sltp: TP=3%, SL=1.5%, sl_type="average_price",
   close_only_in_profit=false, activate_breakeven=true,
   breakeven_activation_percent=1.0, new_breakeven_sl_percent=0.1

2. trailing_stop_exit: activation_percent=1.5, trailing_percent=0.8,
   trail_type="percent"

3. atr_exit: Enable BOTH ATR SL and ATR TP.
   SL: wicks=true, smoothing="RMA", period=14, multiplier=2.0
   TP: wicks=false, smoothing="RMA", period=14, multiplier=3.0

4. dca: grid_size_percent=5, order_count=5, martingale_coefficient=1.2,
   log_steps_coefficient=1.0, first_order_offset=0.5, grid_trailing=2.0

Also explain:
- What port type do ALL exit blocks output? → config
- Where does this port connect on the Strategy node? → sl_tp
- Can you connect static_sltp.config to strategy.entry_long? → NO (type mismatch)

Return ONLY valid JSON:
{
  "static_sltp_params": {
    "take_profit_percent": <number>,
    "stop_loss_percent": <number>,
    "sl_type": "<string>",
    "close_only_in_profit": <bool>,
    "activate_breakeven": <bool>,
    "breakeven_activation_percent": <number>,
    "new_breakeven_sl_percent": <number>
  },
  "trailing_stop_exit_params": {
    "activation_percent": <number>,
    "trailing_percent": <number>,
    "trail_type": "<string>"
  },
  "atr_exit_params": {
    "use_atr_sl": <bool>,
    "atr_sl_on_wicks": <bool>,
    "atr_sl_smoothing": "<string>",
    "atr_sl_period": <int>,
    "atr_sl_multiplier": <number>,
    "use_atr_tp": <bool>,
    "atr_tp_on_wicks": <bool>,
    "atr_tp_smoothing": "<string>",
    "atr_tp_period": <int>,
    "atr_tp_multiplier": <number>
  },
  "dca_params": {
    "grid_size_percent": <number>,
    "order_count": <int>,
    "martingale_coefficient": <number>,
    "log_steps_coefficient": <number>,
    "first_order_offset": <number>,
    "grid_trailing": <number>
  },
  "exit_port_type": "<string>",
  "strategy_target_port": "<string>",
  "config_to_entry_long_allowed": <bool>,
  "reasoning": "Explain the exit block → Strategy node connection pattern"
}
"""


# ═══════════════════════════════════════════════════════════════════
# TEST 4: FILTER BLOCKS — supertrend_filter (3 TFs) + stochastic
# ═══════════════════════════════════════════════════════════════════

FILTERS_TEST_PROMPT = """
You must configure filter blocks for a multi-timeframe strategy.
Filters are special blocks that combine signal generation AND filtering.

=== SUPERTREND FILTER (type: "supertrend_filter") ===
Category: filters
Title: "SUPER TREND [FILTER] [SIGNAL] - MTF (3 Timeframes)"

This block supports UP TO 3 independent SuperTrend calculations on different timeframes.
Each TF can generate its own signals and filter trades.

--- TF1 (Main) Parameters ---
1.  use_supertrend              (bool) — Enable SuperTrend TF1
2.  generate_on_trend_change    (bool) — Generate signals on trend change
3.  use_btc_source              (bool) — Use BTCUSDT as price source
4.  opposite_signal             (bool) — Reverse signal direction
5.  show_supertrend             (bool) — Show on chart
6.  atr_period                  (int, optimizable) — ATR period for TF1
7.  atr_multiplier              (number, step 0.1, optimizable) — ATR multiplier for TF1
8.  timeframe                   (select: Chart,1,5,15,30,60,240,D,W,M) — TF1 timeframe

--- TF2 Parameters ---
9.  use_supertrend_tf2          (bool) — Enable SuperTrend TF2
10. supertrend_tf2_btc_source   (bool) — Use BTCUSDT for TF2
11. supertrend_tf2_opposite     (bool) — Reverse TF2 signals
12. supertrend_tf2_show         (bool) — Show TF2 on chart
13. supertrend_tf2_period       (int, optimizable) — ATR period for TF2
14. supertrend_tf2_multiplier   (number, step 0.1, optimizable) — ATR multiplier for TF2
15. supertrend_tf2_timeframe    (select) — TF2 timeframe

--- TF3 Parameters ---
16. use_supertrend_tf3          (bool) — Enable SuperTrend TF3
17. supertrend_tf3_opposite     (bool) — Reverse TF3 signals
18. supertrend_tf3_show         (bool) — Show TF3 on chart
19. supertrend_tf3_period       (int, optimizable) — ATR period for TF3
20. supertrend_tf3_multiplier   (number, step 0.1, optimizable) — ATR multiplier for TF3
21. supertrend_tf3_timeframe    (select) — TF3 timeframe

=== STOCHASTIC FILTER (type: "stochastic_filter") ===
Category: filters
Title: "STOCHASTIC [RANGE FILTER]"

Has 3 modes: Range Filter, Cross Level, Cross K/D.

--- Base Parameters ---
1. stoch_k_length          (int, optimizable) — %K calculation period
2. stoch_k_smoothing       (int, optimizable) — %K smoothing
3. stoch_d_smoothing       (int, optimizable) — %D smoothing
4. stoch_timeframe         (select) — Timeframe
5. use_btcusdt_source      (bool) — Use BTCUSDT as source

--- Range Filter Mode ---
6. use_stoch_range_filter  (bool) — Enable range filter
7. long_stoch_d_more       (number, optimizable) — LONG: %D > this value (LOWER bound)
8. long_stoch_d_less       (number, optimizable) — LONG: %D < this value (UPPER bound)
   ⚠ more = LOWER bound, less = UPPER bound, MUST have more < less
9. short_stoch_d_less      (number, optimizable) — SHORT: %D < this value (UPPER bound)
10. short_stoch_d_more     (number, optimizable) — SHORT: %D > this value (LOWER bound)

--- Cross Level Mode ---
11. use_stoch_cross_level      (bool) — Enable cross level signals
12. stoch_cross_level_long     (number, optimizable) — Level for LONG cross
13. stoch_cross_level_short    (number, optimizable) — Level for SHORT cross
14. activate_stoch_cross_memory (bool) — Keep signal in memory
15. stoch_cross_memory_bars    (number) — Memory duration in bars

--- Cross K/D Mode ---
16. use_stoch_kd_cross         (bool) — Enable %K/%D crossover signals
17. opposite_stoch_kd          (bool) — Reverse K/D cross signals
18. activate_stoch_kd_memory   (bool) — Keep K/D signal in memory
19. stoch_kd_memory_bars       (number) — K/D memory duration in bars

=== YOUR TASK ===
Configure a multi-timeframe trend-following filter setup:

1. supertrend_filter: Use ALL 3 timeframes for confluence.
   TF1: use=true, generate_on_trend_change=true, no BTC source, no opposite,
        show=true, atr_period=10, atr_multiplier=3.0, timeframe="15"
   TF2: use=true, no BTC source, no opposite, show=false,
        period=10, multiplier=2.0, timeframe="60"
   TF3: use=true, no opposite, show=false,
        period=10, multiplier=2.5, timeframe="240"

2. stochastic_filter: Use Range Filter + Cross K/D.
   Base: k_length=14, k_smoothing=3, d_smoothing=3, timeframe="Chart", no BTC source.
   Range: enabled, long_more=0, long_less=20, short_less=100, short_more=80.
   Cross Level: disabled.
   Cross K/D: enabled, opposite=false, memory=true, memory_bars=5.

Return ONLY valid JSON:
{
  "supertrend_filter_params": {
    "use_supertrend": <bool>,
    "generate_on_trend_change": <bool>,
    "use_btc_source": <bool>,
    "opposite_signal": <bool>,
    "show_supertrend": <bool>,
    "atr_period": <int>,
    "atr_multiplier": <number>,
    "timeframe": "<string>",
    "use_supertrend_tf2": <bool>,
    "supertrend_tf2_btc_source": <bool>,
    "supertrend_tf2_opposite": <bool>,
    "supertrend_tf2_show": <bool>,
    "supertrend_tf2_period": <int>,
    "supertrend_tf2_multiplier": <number>,
    "supertrend_tf2_timeframe": "<string>",
    "use_supertrend_tf3": <bool>,
    "supertrend_tf3_opposite": <bool>,
    "supertrend_tf3_show": <bool>,
    "supertrend_tf3_period": <int>,
    "supertrend_tf3_multiplier": <number>,
    "supertrend_tf3_timeframe": "<string>"
  },
  "stochastic_filter_params": {
    "stoch_k_length": <int>,
    "stoch_k_smoothing": <int>,
    "stoch_d_smoothing": <int>,
    "stoch_timeframe": "<string>",
    "use_btcusdt_source": <bool>,
    "use_stoch_range_filter": <bool>,
    "long_stoch_d_more": <number>,
    "long_stoch_d_less": <number>,
    "short_stoch_d_less": <number>,
    "short_stoch_d_more": <number>,
    "use_stoch_cross_level": <bool>,
    "use_stoch_kd_cross": <bool>,
    "opposite_stoch_kd": <bool>,
    "activate_stoch_kd_memory": <bool>,
    "stoch_kd_memory_bars": <number>
  },
  "total_supertrend_timeframes_used": <int>,
  "stochastic_modes_enabled": ["<mode1>", "<mode2>"],
  "reasoning": "Explain multi-TF confluence and stochastic range filter logic"
}
"""


# ═══════════════════════════════════════════════════════════════════
# JSON extraction
# ═══════════════════════════════════════════════════════════════════


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } balanced
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[brace_start : i + 1])
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        pass
                    break

    return None


# ═══════════════════════════════════════════════════════════════════
# FLOW Validation
# ═══════════════════════════════════════════════════════════════════


def validate_flow_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate strategy flow understanding."""
    result = ValidationResult(
        agent=agent, node="flow", passed=False, score=0.0, raw_response=response, latency_ms=latency_ms
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- Blocks ---
    blocks = parsed.get("blocks", [])
    block_types = {b.get("type", "").lower() for b in blocks} if isinstance(blocks, list) else set()

    # Must have RSI block
    checks["01_has_rsi_block"] = "rsi" in block_types
    # Must have static_sltp block
    checks["02_has_static_sltp_block"] = "static_sltp" in block_types
    # Must have strategy block
    checks["03_has_strategy_block"] = "strategy" in block_types or any(
        str(b.get("type", "")).lower() == "strategy" or str(b.get("id", "")).lower() == "strategy" for b in blocks
    )
    # At least 3 blocks (RSI + static_sltp + strategy)
    checks["04_min_3_blocks"] = len(blocks) >= 3

    # --- Connections ---
    connections = parsed.get("connections", [])

    # Check RSI signal flow to strategy entry ports
    # Correct flow: RSI.value(data) → condition_block(data→condition) → Strategy.entry_long
    # We accept: direct RSI.long→entry_long OR RSI.value→less_than→...→entry_long

    def has_conn(src_block_sub: str, src_port: str, tgt_block_sub: str, tgt_port: str) -> bool:
        for c in connections:
            src = c.get("source", {})
            tgt = c.get("target", {})
            if (
                src_block_sub in str(src.get("blockId", "")).lower()
                and src.get("portId") == src_port
                and tgt_block_sub in str(tgt.get("blockId", "")).lower()
                and tgt.get("portId") == tgt_port
            ):
                return True
        return False

    def has_any_conn_to_port(tgt_block_sub: str, tgt_port: str) -> bool:
        """Check if ANY block connects to the target port."""
        for c in connections:
            tgt = c.get("target", {})
            if tgt_block_sub in str(tgt.get("blockId", "")).lower() and tgt.get("portId") == tgt_port:
                return True
        return False

    def rsi_flows_to_entry(entry_port: str) -> bool:
        """Check if RSI signal eventually reaches Strategy entry port.
        Accept: RSI.value → condition → strategy.entry OR RSI.long/short → strategy.entry
        """
        # Direct RSI → strategy (if RSI long/short treated as condition)
        if has_conn("rsi", "long", "strat", entry_port) or has_conn("rsi", "short", "strat", entry_port):
            return True
        # Via condition blocks: anything → strategy.entry_port
        # AND RSI connects to some condition block
        rsi_to_condition = any(
            "rsi" in str(c.get("source", {}).get("blockId", "")).lower()
            and c.get("source", {}).get("portId") == "value"
            for c in connections
        )
        return rsi_to_condition and has_any_conn_to_port("strat", entry_port)

    checks["05_rsi_signal_to_entry_long"] = rsi_flows_to_entry("entry_long")
    checks["06_rsi_signal_to_entry_short"] = rsi_flows_to_entry("entry_short")
    checks["07_sltp_config_to_sl_tp"] = has_conn("sltp", "config", "strat", "sl_tp") or has_conn(
        "static", "config", "strat", "sl_tp"
    )

    # At least 3 connections (rsi→entry_long, rsi→entry_short, sltp→sl_tp)
    checks["08_min_3_connections"] = len(connections) >= 3

    # --- Port types ---
    pt = parsed.get("port_types_explanation", {})
    checks["09_data_port_explained"] = isinstance(pt.get("data"), str) and len(pt.get("data", "")) > 5
    checks["10_condition_port_explained"] = isinstance(pt.get("condition"), str) and len(pt.get("condition", "")) > 5
    checks["11_config_port_explained"] = isinstance(pt.get("config"), str) and len(pt.get("config", "")) > 5

    # --- Strategy node ports ---
    snp = parsed.get("strategy_node_ports", {})
    checks["12_entry_long_is_condition"] = snp.get("entry_long", "").lower() == "condition"
    checks["13_entry_short_is_condition"] = snp.get("entry_short", "").lower() == "condition"
    checks["14_exit_long_is_condition"] = snp.get("exit_long", "").lower() == "condition"
    checks["15_exit_short_is_condition"] = snp.get("exit_short", "").lower() == "condition"
    checks["16_sl_tp_is_config"] = snp.get("sl_tp", "").lower() == "config"

    # --- Workflow steps ---
    steps = parsed.get("workflow_steps", [])
    checks["17_has_workflow_steps"] = isinstance(steps, list) and len(steps) >= 4

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["18_reasoning_mentions_signal_flow"] = any(
            w in r_lower for w in ["flow", "connect", "rsi", "signal", "entry", "sl", "tp"]
        )
    else:
        checks["18_reasoning_mentions_signal_flow"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85  # 85% threshold

    return result


# ═══════════════════════════════════════════════════════════════════
# WIRING Validation
# ═══════════════════════════════════════════════════════════════════


def validate_wiring_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate block wiring and port compatibility understanding."""
    result = ValidationResult(
        agent=agent, node="wiring", passed=False, score=0.0, raw_response=response, latency_ms=latency_ms
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- Connections ---
    connections = parsed.get("connections", [])

    def has_conn(src_block: str, src_port: str, tgt_block: str, tgt_port: str) -> bool:
        for c in connections:
            src = c.get("source", {})
            tgt = c.get("target", {})
            if (
                src_block in str(src.get("blockId", "")).lower()
                and src.get("portId") == src_port
                and tgt_block in str(tgt.get("blockId", "")).lower()
                and tgt.get("portId") == tgt_port
            ):
                return True
        return False

    # EMA fast → crossover A
    checks["01_ema_fast_to_crossup_a"] = has_conn("ema_fast", "value", "cross_up", "a")
    # EMA slow → crossover B
    checks["02_ema_slow_to_crossup_b"] = has_conn("ema_slow", "value", "cross_up", "b")
    # EMA fast → crossunder A
    checks["03_ema_fast_to_crossdown_a"] = has_conn("ema_fast", "value", "cross_down", "a")
    # EMA slow → crossunder B
    checks["04_ema_slow_to_crossdown_b"] = has_conn("ema_slow", "value", "cross_down", "b")
    # crossover result → strategy entry_long
    checks["05_crossup_to_entry_long"] = has_conn("cross_up", "result", "strat", "entry_long")
    # crossunder result → strategy entry_short
    checks["06_crossdown_to_entry_short"] = has_conn("cross_down", "result", "strat", "entry_short")
    # atr_exit config → strategy sl_tp
    checks["07_atr_exit_to_sl_tp"] = has_conn("atr_exit", "config", "strat", "sl_tp") or has_conn(
        "atr", "config", "strat", "sl_tp"
    )

    # Total connections should be 7
    checks["08_total_connections_7"] = parsed.get("total_connections") == 7 or len(connections) == 7

    # --- Compatibility answers ---
    compat = parsed.get("compatibility_answers", {})
    # 1. RSI value → entry_long: NO
    checks["09_rsi_value_to_entry_long_false"] = compat.get("rsi_value_to_entry_long") is False
    # 2. crossover result → entry_long: YES
    checks["10_crossover_to_entry_long_true"] = compat.get("crossover_result_to_entry_long") is True
    # 3. static_sltp config → sl_tp: YES
    checks["11_sltp_config_to_sl_tp_true"] = compat.get("static_sltp_config_to_sl_tp") is True
    # 4. RSI long → crossover a: YES
    checks["12_rsi_long_to_crossover_true"] = compat.get("rsi_long_to_crossover_a") is True
    # 5. static_sltp config → entry_long: NO
    checks["13_sltp_to_entry_long_false"] = compat.get("static_sltp_config_to_entry_long") is False
    # 6. atr_exit config → and.a: NO
    checks["14_atr_to_and_false"] = compat.get("atr_exit_config_to_and_a") is False

    # --- Port type rules ---
    rules = parsed.get("port_type_rules", {})
    checks["15_data_to_data_allowed"] = "allow" in str(rules.get("data_to_data", "")).lower()
    checks["16_condition_to_condition_allowed"] = "allow" in str(rules.get("condition_to_condition", "")).lower()
    checks["17_config_to_config_allowed"] = "allow" in str(rules.get("config_to_config", "")).lower()
    checks["18_data_to_condition_not_allowed"] = (
        "not" in str(rules.get("data_to_condition", "")).lower()
        or "disallow" in str(rules.get("data_to_condition", "")).lower()
        or "forbid" in str(rules.get("data_to_condition", "")).lower()
        or "incomp" in str(rules.get("data_to_condition", "")).lower()
    )

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["19_reasoning_port_types"] = any(
            w in r_lower for w in ["type", "compat", "match", "data", "condition", "config"]
        )
    else:
        checks["19_reasoning_port_types"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# EXITS Validation
# ═══════════════════════════════════════════════════════════════════


def validate_exits_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate exit/risk block configuration understanding."""
    result = ValidationResult(
        agent=agent, node="exits", passed=False, score=0.0, raw_response=response, latency_ms=latency_ms
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- Static SL/TP ---
    sltp = parsed.get("static_sltp_params", {})
    checks["01_sltp_tp_3"] = sltp.get("take_profit_percent") == 3 or sltp.get("take_profit_percent") == 3.0
    checks["02_sltp_sl_1.5"] = sltp.get("stop_loss_percent") == 1.5
    checks["03_sltp_type_average"] = sltp.get("sl_type") == "average_price"
    checks["04_sltp_close_profit_false"] = sltp.get("close_only_in_profit") is False
    checks["05_sltp_breakeven_true"] = sltp.get("activate_breakeven") is True
    checks["06_sltp_breakeven_act_1"] = (
        sltp.get("breakeven_activation_percent") == 1.0 or sltp.get("breakeven_activation_percent") == 1
    )
    checks["07_sltp_breakeven_sl_0.1"] = sltp.get("new_breakeven_sl_percent") == 0.1
    checks["08_sltp_all_keys"] = set(sltp.keys()) >= {
        "take_profit_percent",
        "stop_loss_percent",
        "sl_type",
        "close_only_in_profit",
        "activate_breakeven",
        "breakeven_activation_percent",
        "new_breakeven_sl_percent",
    }

    # --- Trailing Stop ---
    trail = parsed.get("trailing_stop_exit_params", {})
    checks["09_trail_activation_1.5"] = trail.get("activation_percent") == 1.5
    checks["10_trail_percent_0.8"] = trail.get("trailing_percent") == 0.8
    checks["11_trail_type_percent"] = trail.get("trail_type") == "percent"

    # --- ATR Exit ---
    atr = parsed.get("atr_exit_params", {})
    checks["12_atr_sl_enabled"] = atr.get("use_atr_sl") is True
    checks["13_atr_sl_wicks_true"] = atr.get("atr_sl_on_wicks") is True
    checks["14_atr_sl_smoothing_rma"] = str(atr.get("atr_sl_smoothing", "")).upper() == "RMA"
    checks["15_atr_sl_period_14"] = atr.get("atr_sl_period") == 14
    checks["16_atr_sl_mult_2"] = atr.get("atr_sl_multiplier") == 2.0 or atr.get("atr_sl_multiplier") == 2
    checks["17_atr_tp_enabled"] = atr.get("use_atr_tp") is True
    checks["18_atr_tp_wicks_false"] = atr.get("atr_tp_on_wicks") is False
    checks["19_atr_tp_smoothing_rma"] = str(atr.get("atr_tp_smoothing", "")).upper() == "RMA"
    checks["20_atr_tp_period_14"] = atr.get("atr_tp_period") == 14
    checks["21_atr_tp_mult_3"] = atr.get("atr_tp_multiplier") == 3.0 or atr.get("atr_tp_multiplier") == 3
    checks["22_atr_all_keys"] = set(atr.keys()) >= {
        "use_atr_sl",
        "atr_sl_on_wicks",
        "atr_sl_smoothing",
        "atr_sl_period",
        "atr_sl_multiplier",
        "use_atr_tp",
        "atr_tp_on_wicks",
        "atr_tp_smoothing",
        "atr_tp_period",
        "atr_tp_multiplier",
    }

    # --- DCA ---
    dca = parsed.get("dca_params", {})
    checks["23_dca_grid_5"] = dca.get("grid_size_percent") == 5 or dca.get("grid_size_percent") == 5.0
    checks["24_dca_orders_5"] = dca.get("order_count") == 5
    checks["25_dca_martingale_1.2"] = dca.get("martingale_coefficient") == 1.2
    checks["26_dca_log_steps_1.0"] = dca.get("log_steps_coefficient") == 1.0 or dca.get("log_steps_coefficient") == 1
    checks["27_dca_offset_0.5"] = dca.get("first_order_offset") == 0.5
    checks["28_dca_trailing_2.0"] = dca.get("grid_trailing") == 2.0 or dca.get("grid_trailing") == 2

    # --- Meta understanding ---
    checks["29_exit_port_type_config"] = str(parsed.get("exit_port_type", "")).lower() == "config"
    checks["30_strategy_target_sl_tp"] = str(parsed.get("strategy_target_port", "")).lower() == "sl_tp"
    checks["31_config_to_entry_not_allowed"] = parsed.get("config_to_entry_long_allowed") is False

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["32_reasoning_exit_pattern"] = any(
            w in r_lower for w in ["config", "sl_tp", "exit", "strategy", "connect"]
        )
    else:
        checks["32_reasoning_exit_pattern"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# FILTERS Validation
# ═══════════════════════════════════════════════════════════════════


def validate_filters_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate filter block configuration understanding."""
    result = ValidationResult(
        agent=agent, node="filters", passed=False, score=0.0, raw_response=response, latency_ms=latency_ms
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- SuperTrend Filter ---
    st = parsed.get("supertrend_filter_params", {})
    # TF1
    checks["01_st_tf1_enabled"] = st.get("use_supertrend") is True
    checks["02_st_tf1_trend_change"] = st.get("generate_on_trend_change") is True
    checks["03_st_tf1_no_btc"] = st.get("use_btc_source") is False
    checks["04_st_tf1_no_opposite"] = st.get("opposite_signal") is False
    checks["05_st_tf1_show_true"] = st.get("show_supertrend") is True
    checks["06_st_tf1_period_10"] = st.get("atr_period") == 10
    checks["07_st_tf1_mult_3"] = st.get("atr_multiplier") == 3.0 or st.get("atr_multiplier") == 3
    checks["08_st_tf1_timeframe_15"] = str(st.get("timeframe", "")) == "15"
    # TF2
    checks["09_st_tf2_enabled"] = st.get("use_supertrend_tf2") is True
    checks["10_st_tf2_no_btc"] = st.get("supertrend_tf2_btc_source") is False
    checks["11_st_tf2_no_opposite"] = st.get("supertrend_tf2_opposite") is False
    checks["12_st_tf2_show_false"] = st.get("supertrend_tf2_show") is False
    checks["13_st_tf2_period_10"] = st.get("supertrend_tf2_period") == 10
    checks["14_st_tf2_mult_2"] = st.get("supertrend_tf2_multiplier") == 2.0 or st.get("supertrend_tf2_multiplier") == 2
    checks["15_st_tf2_timeframe_60"] = str(st.get("supertrend_tf2_timeframe", "")) == "60"
    # TF3
    checks["16_st_tf3_enabled"] = st.get("use_supertrend_tf3") is True
    checks["17_st_tf3_no_opposite"] = st.get("supertrend_tf3_opposite") is False
    checks["18_st_tf3_show_false"] = st.get("supertrend_tf3_show") is False
    checks["19_st_tf3_period_10"] = st.get("supertrend_tf3_period") == 10
    checks["20_st_tf3_mult_2.5"] = st.get("supertrend_tf3_multiplier") == 2.5
    checks["21_st_tf3_timeframe_240"] = str(st.get("supertrend_tf3_timeframe", "")) == "240"

    # --- Stochastic Filter ---
    sf = parsed.get("stochastic_filter_params", {})
    checks["22_stoch_k_14"] = sf.get("stoch_k_length") == 14
    checks["23_stoch_k_smooth_3"] = sf.get("stoch_k_smoothing") == 3
    checks["24_stoch_d_smooth_3"] = sf.get("stoch_d_smoothing") == 3
    checks["25_stoch_tf_chart"] = str(sf.get("stoch_timeframe", "")).lower() in ("chart", '"chart"')
    checks["26_stoch_no_btc"] = sf.get("use_btcusdt_source") is False
    # Range filter
    checks["27_stoch_range_enabled"] = sf.get("use_stoch_range_filter") is True
    long_more = sf.get("long_stoch_d_more")
    long_less = sf.get("long_stoch_d_less")
    checks["28_stoch_long_more_0"] = long_more == 0 or long_more == 0.0
    checks["29_stoch_long_less_20"] = long_less == 20 or long_less == 20.0
    checks["30_stoch_short_less_100"] = sf.get("short_stoch_d_less") == 100 or sf.get("short_stoch_d_less") == 100.0
    checks["31_stoch_short_more_80"] = sf.get("short_stoch_d_more") == 80 or sf.get("short_stoch_d_more") == 80.0
    # Cross level disabled
    checks["32_stoch_cross_level_disabled"] = sf.get("use_stoch_cross_level") is False
    # Cross K/D
    checks["33_stoch_kd_enabled"] = sf.get("use_stoch_kd_cross") is True
    checks["34_stoch_kd_no_opposite"] = sf.get("opposite_stoch_kd") is False
    checks["35_stoch_kd_memory_true"] = sf.get("activate_stoch_kd_memory") is True
    checks["36_stoch_kd_memory_bars_5"] = sf.get("stoch_kd_memory_bars") == 5

    # --- Meta ---
    checks["37_total_st_timeframes_3"] = parsed.get("total_supertrend_timeframes_used") == 3
    modes = parsed.get("stochastic_modes_enabled", [])
    if isinstance(modes, list):
        modes_lower = [str(m).lower() for m in modes]
        checks["38_stoch_modes_range_and_kd"] = any("range" in m for m in modes_lower) and any(
            "k" in m and "d" in m for m in modes_lower
        )
    else:
        checks["38_stoch_modes_range_and_kd"] = False

    # --- Reasoning ---
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["39_reasoning_multi_tf"] = any(
            w in r_lower for w in ["timeframe", "tf", "confluence", "multi", "filter"]
        )
    else:
        checks["39_reasoning_multi_tf"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.85

    return result


# ═══════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════


NODE_CONFIG = {
    "flow": {
        "prompt": FLOW_TEST_PROMPT,
        "validator": validate_flow_response,
        "checks_count": 18,
    },
    "wiring": {
        "prompt": WIRING_TEST_PROMPT,
        "validator": validate_wiring_response,
        "checks_count": 19,
    },
    "exits": {
        "prompt": EXITS_TEST_PROMPT,
        "validator": validate_exits_response,
        "checks_count": 32,
    },
    "filters": {
        "prompt": FILTERS_TEST_PROMPT,
        "validator": validate_filters_response,
        "checks_count": 39,
    },
}


async def test_agent(agent_name: str, client: Any, node: str) -> ValidationResult:
    """Send test prompt to agent and validate response."""
    system_prompt: str = SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPTS["deepseek"])
    config: dict[str, Any] = NODE_CONFIG[node]
    prompt_text: str = str(config["prompt"])

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt_text),
    ]

    start = time.perf_counter()
    try:
        response: LLMResponse = await client.chat(messages)  # type: ignore[union-attr]
        latency = (time.perf_counter() - start) * 1000
        validator: Any = config["validator"]
        result: ValidationResult = validator(agent_name, response.content, latency)  # type: ignore[misc]
        return result
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ValidationResult(
            agent=agent_name,
            node=node,
            passed=False,
            score=0.0,
            error=str(e),
            latency_ms=latency,
        )


def print_result(result: ValidationResult) -> None:
    """Print formatted test result with per-check breakdown."""
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"\n{'=' * 70}")
    print(f"  {status}  {result.agent.upper()} → {result.node.upper()}")
    print(
        f"  Score: {result.score:.0%} ({sum(v for v in result.checks.values())}/{len(result.checks)}) | Latency: {result.latency_ms:.0f}ms"
    )
    print(f"{'=' * 70}")

    if result.error:
        print(f"  ⚠ Error: {result.error}")
        return

    if result.checks:
        print(f"  {'#':<4} {'Check':<45} {'Result':>8}")
        print(f"  {'─' * 57}")
        for i, (check, passed) in enumerate(result.checks.items(), 1):
            icon = "✅" if passed else "❌"
            print(f"  {i:<4} {check:<45} {icon:>8}")

    if result.parsed_json:
        reasoning = result.parsed_json.get("reasoning", "")
        if reasoning:
            truncated = reasoning[:300] + ("..." if len(reasoning) > 300 else "")
            print(f"\n  💬 Reasoning: {truncated}")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Agent Comprehensive Understanding Test v3")
    parser.add_argument(
        "--agent",
        choices=["deepseek", "qwen", "perplexity", "all"],
        default="all",
        help="Which agent to test (default: all)",
    )
    parser.add_argument(
        "--node",
        choices=["flow", "wiring", "exits", "filters", "all"],
        default="all",
        help="Which test scenario (default: all)",
    )
    args = parser.parse_args()

    print("\n" + "═" * 70)
    print("  🧪 AI Agent Comprehensive Understanding Test v3")
    print("  Flow: 18 checks | Wiring: 19 checks | Exits: 32 checks | Filters: 39 checks")
    print("  Total: 108 checks per agent x 3 agents = 324 checks")
    print("═" * 70)

    # Initialize clients
    clients: dict[str, object] = {}

    deepseek_key = _get_api_key("DEEPSEEK_API_KEY")
    if deepseek_key:
        clients["deepseek"] = DeepSeekClient(
            LLMConfig(
                provider=LLMProvider.DEEPSEEK,
                api_key=deepseek_key,
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ DeepSeek ready")
    else:
        print("  ⚠️  DeepSeek: no API key found")

    qwen_key = _get_api_key("QWEN_API_KEY")
    if qwen_key:
        clients["qwen"] = QwenClient(
            LLMConfig(
                provider=LLMProvider.QWEN,
                api_key=qwen_key,
                model="qwen-plus",
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ Qwen ready")
    else:
        print("  ⚠️  Qwen: no API key found")

    perplexity_key = _get_api_key("PERPLEXITY_API_KEY")
    if perplexity_key:
        clients["perplexity"] = PerplexityClient(
            LLMConfig(
                provider=LLMProvider.PERPLEXITY,
                api_key=perplexity_key,
                model=os.getenv("PERPLEXITY_MODEL", "sonar-pro"),
                temperature=0.1,
                max_tokens=4096,
            )
        )
        print("  ✅ Perplexity ready")
    else:
        print("  ⚠️  Perplexity: no API key found")

    if not clients:
        print("\n  ❌ No API keys found!")
        sys.exit(1)

    # Filter agents
    if args.agent != "all":
        if args.agent not in clients:
            print(f"\n  ❌ Agent '{args.agent}' not available")
            sys.exit(1)
        clients = {args.agent: clients[args.agent]}

    # Determine nodes
    nodes = ["flow", "wiring", "exits", "filters"] if args.node == "all" else [args.node]

    # Run tests
    results: list[ValidationResult] = []

    for node in nodes:
        config = NODE_CONFIG[node]
        print(f"\n{'─' * 70}")
        print(f"  Testing {node.upper()} — {config['checks_count']} checks per agent...")
        print(f"{'─' * 70}")

        for agent_name, client in clients.items():
            print(f"\n  ⏳ {agent_name}...")
            result = await test_agent(agent_name, client, node)
            results.append(result)
            print_result(result)

    # Summary
    print(f"\n\n{'═' * 70}")
    print("  📊 FINAL SUMMARY")
    print(f"{'═' * 70}")
    print(f"  {'Agent':<15} {'Node':<12} {'Score':>10} {'Checks':>12} {'Status':>10} {'Latency':>10}")
    print(f"  {'─' * 69}")

    total_passed = 0
    total_tests = 0

    for r in results:
        passed_checks = sum(1 for v in r.checks.values() if v) if r.checks else 0
        total_checks = len(r.checks) if r.checks else 0
        status = "PASS ✅" if r.passed else "FAIL ❌"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms > 0 else "N/A"
        print(
            f"  {r.agent:<15} {r.node:<12} {r.score:>9.0%} "
            f"{passed_checks:>5}/{total_checks:<5} {status:>10} {latency:>10}"
        )
        total_tests += 1
        if r.passed:
            total_passed += 1

    # Per-agent summary
    print(f"\n  {'─' * 69}")
    agents_seen = list(dict.fromkeys(r.agent for r in results))
    for agent in agents_seen:
        agent_results = [r for r in results if r.agent == agent]
        total_agent_checks = sum(len(r.checks) for r in agent_results if r.checks)
        passed_agent_checks = sum(sum(1 for v in r.checks.values() if v) for r in agent_results if r.checks)
        agent_pass = sum(1 for r in agent_results if r.passed)
        agent_total = len(agent_results)
        pct = passed_agent_checks / total_agent_checks * 100 if total_agent_checks > 0 else 0
        print(
            f"  {agent.upper():<15} TOTAL       "
            f"{pct:>8.0f}% {passed_agent_checks:>5}/{total_agent_checks:<5} "
            f"{'  ' + str(agent_pass) + '/' + str(agent_total) + ' ✅':>10}"
        )

    print(f"\n  Overall: {total_passed}/{total_tests} tests passed (85% threshold)")

    if total_passed == total_tests:
        print("\n  🎉 All agents demonstrate comprehensive Strategy Builder understanding!")
    else:
        failed = [r for r in results if not r.passed]
        print(f"\n  ⚠️  {len(failed)} test(s) failed:")
        for r in failed:
            failed_checks = [k for k, v in r.checks.items() if not v] if r.checks else []
            print(f"     {r.agent}/{r.node}: {r.error or ', '.join(failed_checks[:5])}")

    # Cleanup clients
    for client in clients.values():
        if hasattr(client, "close"):
            await client.close()  # type: ignore[union-attr]

    # Save results
    results_path = Path(__file__).parent.parent / "logs" / "agent_comprehensive_test_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    results_data = []
    for r in results:
        results_data.append(
            {
                "agent": r.agent,
                "node": r.node,
                "passed": r.passed,
                "score": round(r.score, 4),
                "checks": r.checks,
                "failed_checks": [k for k, v in r.checks.items() if not v] if r.checks else [],
                "latency_ms": round(r.latency_ms, 1),
                "error": r.error,
                "reasoning": r.parsed_json.get("reasoning", "") if r.parsed_json else "",
                "parsed_json": r.parsed_json,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"\n  📁 Results saved to: {results_path}")
    sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    asyncio.run(main())
