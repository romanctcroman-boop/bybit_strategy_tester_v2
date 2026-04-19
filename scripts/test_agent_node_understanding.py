r"""
AI Agent Node Understanding Test v2 — RSI & MACD (Per-Parameter) + Optimization Ranges

Tests whether DeepSeek, Qwen, and Perplexity correctly understand
EVERY parameter of the RSI and MACD universal nodes — exact field names,
types, defaults, value constraints, and logic (AND vs OR).

Also tests whether agents understand OPTIMIZATION RANGES — the ability to
set min/max/step per optimizable parameter for grid search optimization.

Each parameter from the UI popup is listed in the prompt in order,
and validated individually in the response.

Usage:
    cd D:\bybit_strategy_tester_v2
    .venv\Scripts\python.exe scripts\test_agent_node_understanding.py

    # Test only one agent:
    .venv\Scripts\python.exe scripts\test_agent_node_understanding.py --agent deepseek

    # Test only RSI or MACD or optimization:
    .venv\Scripts\python.exe scripts\test_agent_node_understanding.py --node rsi
    .venv\Scripts\python.exe scripts\test_agent_node_understanding.py --node optimization
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
# System prompts (match real_llm_deliberation.py)
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "deepseek": (
        "You are a quantitative trading analyst configuring indicator nodes in a Strategy Builder. "
        "You must use the EXACT parameter names and follow ALL constraints described in the prompt. "
        "Commission is 0.07%. Always respond with valid JSON only — no markdown, no extra text."
    ),
    "qwen": (
        "You are a technical analysis expert configuring indicator nodes in a Strategy Builder. "
        "RSI Range filter: RSI > long_rsi_more AND RSI < long_rsi_less. "
        "more = LOWER bound (min), less = UPPER bound (max). Always more < less. "
        "RSI modes combine with AND logic. MACD modes combine with OR logic. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
    "perplexity": (
        "You are a market research analyst configuring indicator nodes in a Strategy Builder. "
        "Use EXACT parameter names from the prompt. Pay attention to field semantics: "
        "long_rsi_more = LOWER bound (engine: RSI > more), long_rsi_less = UPPER bound (engine: RSI < less). "
        "Always more < less. "
        "Always respond with valid JSON only — no markdown, no extra text."
    ),
}


# ═══════════════════════════════════════════════════════════════════
# RSI TEST PROMPT — every parameter in UI order
# ═══════════════════════════════════════════════════════════════════

RSI_TEST_PROMPT = """
You must configure the RSI universal node. Below is the COMPLETE list of parameters
in the EXACT order they appear in the UI popup. You must return ALL of them.

=== RSI POPUP PARAMETERS (in order) ===

1.  period          (int, default=14, range 1-200, optimizable)
    UI label: "RSI TF Long(14):"
    → RSI calculation period

2.  timeframe       (string, default="Chart", options: "1","5","15","30","60","240","D","W","M","Chart")
    UI label: "RSI TimeFrame:"
    → Timeframe for RSI calculation. "Chart" means use current chart TF.

3.  use_btc_source  (bool, default=false)
    UI label: "Use BTCUSDT as Source for RSI 1 ?"
    → If true, calculates RSI on BTCUSDT price instead of current symbol

4.  use_long_range  (bool, default=false)
    UI label: "Use RSI LONG Range"
    → Enables Range filter for LONG signals

5.  long_rsi_more   (number, default=30, range 0.1-100, optimizable)
    UI label: "(LONG) RSI is More"
    → LOWER bound of long range. Engine: RSI > long_rsi_more
    ⚠ MUST be LESS than long_rsi_less

6.  long_rsi_less   (number, default=70, range 0.1-100, optimizable)
    UI label: "& RSI Less"
    → UPPER bound of long range. Engine: RSI < long_rsi_less
    ⚠ MUST be GREATER than long_rsi_more

    Engine logic: LONG range active when RSI > long_rsi_more AND RSI < long_rsi_less
    Example: long_rsi_more=0, long_rsi_less=30 → long when RSI is in 0..30 (oversold)

7.  use_short_range (bool, default=false)
    UI label: "Use RSI SHORT Range"
    → Enables Range filter for SHORT signals

8.  short_rsi_less  (number, default=70, range 0.1-100, optimizable)
    UI label: "(SHORT) RSI is Less"
    → UPPER bound of short range. Engine: RSI < short_rsi_less
    ⚠ MUST be GREATER than short_rsi_more

9.  short_rsi_more  (number, default=30, range 0.1-100, optimizable)
    UI label: "& RSI More"
    → LOWER bound of short range. Engine: RSI > short_rsi_more
    ⚠ MUST be LESS than short_rsi_less

    Engine logic: SHORT range active when RSI > short_rsi_more AND RSI < short_rsi_less
    Example: short_rsi_more=70, short_rsi_less=100 → short when RSI is in 70..100 (overbought)

10. use_cross_level (bool, default=false)
    UI label: "Use RSI Cross Level"
    → Enables Cross Level mode — event-based signal on RSI crossing a threshold

11. cross_long_level  (number, default=30, range 0.1-100, optimizable)
    UI label: "Level to Cross RSI for LONG"
    → Long signal fires when RSI crosses UP through this level

12. cross_short_level (number, default=70, range 0.1-100, optimizable)
    UI label: "Level to Cross RSI for SHORT"
    → Short signal fires when RSI crosses DOWN through this level

13. opposite_signal   (bool, default=false)
    UI label: "Opposite Signal - RSI Cross Level"
    → Swaps cross long/short signal directions

14. use_cross_memory  (bool, default=false)
    UI label: "Activate RSI Cross Signal Memory"
    → Keeps cross signal active for N bars (so other conditions can still match)

15. cross_memory_bars (int, default=5, range 1-100, optimizable)
    UI label: "Keep RSI Cross Signal Memory for XX bars"
    → Number of bars to keep cross signal in memory

=== RSI OUTPUTS (3 ports) ===
- value: RSI value (0-100 series)
- long:  boolean long signal
- short: boolean short signal

=== RSI MODE LOGIC ===
- Range + Cross modes combine with AND logic (both must be true)
- If no mode enabled → passthrough (long/short always True)

=== OPTIMIZATION POPUP (8 optimizable params) ===
period, long_rsi_more, long_rsi_less, short_rsi_less, short_rsi_more,
cross_long_level, cross_short_level, cross_memory_bars

=== YOUR TASK ===
Configure RSI for a BTC mean-reversion strategy:
- Enable Range filter for oversold (0-30) longs AND overbought (70-100) shorts
- Enable Cross level at 30 (long) and 70 (short)
- Enable signal memory for 3 bars
- Use period 14, timeframe "Chart", no BTC source

Return ONLY valid JSON:
{
  "rsi_params": {
    "period": <int>,
    "timeframe": "<string>",
    "use_btc_source": <bool>,
    "use_long_range": <bool>,
    "long_rsi_more": <number>,
    "long_rsi_less": <number>,
    "use_short_range": <bool>,
    "short_rsi_less": <number>,
    "short_rsi_more": <number>,
    "use_cross_level": <bool>,
    "cross_long_level": <number>,
    "cross_short_level": <number>,
    "opposite_signal": <bool>,
    "use_cross_memory": <bool>,
    "cross_memory_bars": <int>
  },
  "reasoning": "Explain AND logic between Range and Cross modes"
}
"""


# ═══════════════════════════════════════════════════════════════════
# MACD TEST PROMPT — every parameter in UI order
# ═══════════════════════════════════════════════════════════════════

MACD_TEST_PROMPT = """
You must configure the MACD universal node. Below is the COMPLETE list of parameters
in the EXACT order they appear in the UI popup. You must return ALL of them.

=== MACD POPUP PARAMETERS (in order) ===

1.  enable_visualization (bool, default=false)
    UI label: "Enable Visualisation MACD"
    → Shows MACD histogram on the chart

2.  timeframe       (string, default="Chart", options: "1","5","15","30","60","240","D","W","M","Chart")
    UI label: "MACD TimeFrame:"
    → Timeframe for MACD calculation

3.  use_btc_source  (bool, default=false)
    UI label: "Use BTCUSDT as Source for MACD ?"
    → If true, uses BTCUSDT price for calculation

4.  fast_period     (int, default=12, range 1-500, optimizable)
    UI label: "MACD Fast Length (12)"
    → Fast EMA period. ⚠ MUST be LESS than slow_period

5.  slow_period     (int, default=26, range 1-500, optimizable)
    UI label: "MACD Slow Length (26)"
    → Slow EMA period. ⚠ MUST be GREATER than fast_period

6.  signal_period   (int, default=9, range 1-100, optimizable)
    UI label: "MACD Signal Smoothing (9)"
    → Signal line EMA smoothing period

7.  source          (string, default="close", options: "close","open","high","low","hl2","hlc3","ohlc4")
    UI label: "MACD Source"
    → Price source for MACD calculation

--- divider (Cross with Level section) ---

8.  use_macd_cross_zero (bool, default=false)
    UI label: "Use MACD Cross with Level (0)"
    → Long when MACD crosses ABOVE level, Short when crosses BELOW

9.  opposite_macd_cross_zero (bool, default=false)
    UI label: "Opposite Signal - MACD Cross with Level (0)"
    → Swaps long/short signals for level crossing

10. macd_cross_zero_level (number, default=0, range -1000 to 1000, optimizable)
    UI label: "Cross Line Level (0)"
    → The crossing threshold (usually 0 = zero line)

--- divider (Cross with Signal Line section) ---

11. use_macd_cross_signal (bool, default=false)
    UI label: "Use MACD Cross with Signal Line"
    → Long when MACD crosses ABOVE Signal line, Short when crosses BELOW

12. signal_only_if_macd_positive (bool, default=false)
    UI label: "Signal only if MACD < 0 (Long) or > 0 (Short)"
    → Filter: long signals only when MACD < 0, short only when MACD > 0

13. opposite_macd_cross_signal (bool, default=false)
    UI label: "Opposite Signal - MACD Cross with Signal Line"
    → Swaps long/short signals for signal line crossing

--- divider (Signal Memory section) ---

14. disable_signal_memory (bool, default=false)
    UI label: "==Disable Signal Memory (for both MACD Crosses)=="
    → When false (default): cross signals persist for signal_memory_bars bars
    → When true: signals fire ONLY on the exact bar of crossing

15. signal_memory_bars (int, default=5, range 1-100, optimizable)
    UI label: (not shown in popup, shown in optimization)
    → Number of bars cross signals persist. Only effective when disable_signal_memory=false.

=== MACD OUTPUTS (5 ports) ===
- macd:   MACD line series
- signal: Signal line series
- hist:   Histogram series (MACD - Signal)
- long:   boolean long signal
- short:  boolean short signal

=== MACD MODE LOGIC ===
- Cross Zero + Cross Signal combine with OR logic (either can fire independently)
- If no mode enabled → data-only (long/short always False)

=== OPTIMIZATION POPUP (5 optimizable params) ===
fast_period, slow_period, signal_period, macd_cross_zero_level, signal_memory_bars

=== YOUR TASK ===
Configure MACD for a BTC trend-following strategy:
- Enable BOTH Cross Zero AND Cross Signal modes
- Set fast_period=12, slow_period=26, signal_period=9
- Use source "close", timeframe "Chart"
- Enable signal_only_if_macd_positive filter
- Keep signal memory ON (disable_signal_memory=false), signal_memory_bars=3
- Cross zero level = 0
- No opposite signals, no visualization, no BTC source

Return ONLY valid JSON:
{
  "macd_params": {
    "enable_visualization": <bool>,
    "timeframe": "<string>",
    "use_btc_source": <bool>,
    "fast_period": <int>,
    "slow_period": <int>,
    "signal_period": <int>,
    "source": "<string>",
    "use_macd_cross_zero": <bool>,
    "opposite_macd_cross_zero": <bool>,
    "macd_cross_zero_level": <number>,
    "use_macd_cross_signal": <bool>,
    "signal_only_if_macd_positive": <bool>,
    "opposite_macd_cross_signal": <bool>,
    "disable_signal_memory": <bool>,
    "signal_memory_bars": <int>
  },
  "reasoning": "Explain OR logic between Cross Zero and Cross Signal modes"
}
"""


# ═══════════════════════════════════════════════════════════════════
# OPTIMIZATION TEST PROMPT — optimizationParams with {enabled, min, max, step}
# ═══════════════════════════════════════════════════════════════════

OPTIMIZATION_TEST_PROMPT = """
You are configuring OPTIMIZATION RANGES for a strategy that uses RSI and MACD blocks.
The optimizer performs a grid search over parameter combinations.

=== HOW OPTIMIZATION WORKS ===

Each block has an "optimizationParams" dictionary. For every optimizable parameter,
you set a range with EXACTLY these 4 fields:
  {
    "enabled": true/false,   ← whether this param is included in the grid search
    "min": <number>,         ← minimum value for the sweep
    "max": <number>,         ← maximum value for the sweep
    "step": <number>         ← step size between min and max
  }

The optimizer generates all combinations: [min, min+step, min+2*step, ..., max].
Only params with enabled=true are swept; disabled params keep their fixed value.

⚠ RULES:
- min MUST be < max (otherwise no sweep range)
- step MUST be > 0
- step should divide (max - min) evenly for clean grid
- Only include params whose mode is active (e.g., don't optimize long_rsi_more
  if use_long_range=false)

=== RSI OPTIMIZABLE PARAMS (8 total) ===
1. period         → int, default range: min=5,  max=30, step=1
2. long_rsi_more  → float, default range: min=10, max=45, step=5
3. long_rsi_less  → float, default range: min=55, max=90, step=5
4. short_rsi_less → float, default range: min=55, max=90, step=5
5. short_rsi_more → float, default range: min=10, max=45, step=5
6. cross_long_level  → float, default range: min=15, max=45, step=5
7. cross_short_level → float, default range: min=55, max=85, step=5
8. cross_memory_bars → int, default range: min=1,  max=20, step=1

=== MACD OPTIMIZABLE PARAMS (5 total) ===
1. fast_period          → int, default range: min=8,   max=16,  step=1
2. slow_period          → int, default range: min=20,  max=30,  step=1
3. signal_period        → int, default range: min=6,   max=12,  step=1
4. macd_cross_zero_level → float, default range: min=-50, max=50, step=1
5. signal_memory_bars   → int, default range: min=1,   max=20,  step=1

=== YOUR TASK ===
You have an RSI block with use_long_range=true, use_cross_level=true, use_cross_memory=true
(use_short_range=false), and a MACD block with use_macd_cross_signal=true (use_macd_cross_zero=false).

Configure optimizationParams for BOTH blocks:
- RSI: Enable optimization for period, long_rsi_more, long_rsi_less, cross_long_level,
  cross_short_level, cross_memory_bars.
  Do NOT enable short_rsi_less and short_rsi_more (because use_short_range=false).
  Use these specific ranges:
    period: min=7, max=21, step=2
    long_rsi_more: min=10, max=40, step=5
    long_rsi_less: min=55, max=85, step=5
    cross_long_level: min=20, max=40, step=5
    cross_short_level: min=60, max=80, step=5
    cross_memory_bars: min=1, max=10, step=1

- MACD: Enable optimization for fast_period, slow_period, signal_period, signal_memory_bars.
  Do NOT enable macd_cross_zero_level (because use_macd_cross_zero=false).
  Use these specific ranges:
    fast_period: min=8, max=16, step=2
    slow_period: min=20, max=30, step=2
    signal_period: min=6, max=12, step=1
    signal_memory_bars: min=1, max=10, step=1

Return ONLY valid JSON:
{
  "rsi_optimizationParams": {
    "period": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "long_rsi_more": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "long_rsi_less": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "short_rsi_less": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "short_rsi_more": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "cross_long_level": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "cross_short_level": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "cross_memory_bars": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>}
  },
  "macd_optimizationParams": {
    "fast_period": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "slow_period": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "signal_period": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "macd_cross_zero_level": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>},
    "signal_memory_bars": {"enabled": <bool>, "min": <number>, "max": <number>, "step": <number>}
  },
  "total_grid_combinations": <int>,
  "reasoning": "Explain why disabled params are excluded and how grid search works"
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

    # Try finding first { ... }
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
# RSI Validation — per-parameter
# ═══════════════════════════════════════════════════════════════════


def validate_rsi_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate RSI params — every single field checked individually."""
    result = ValidationResult(
        agent=agent,
        node="rsi",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    params = parsed.get("rsi_params", parsed)
    checks: dict[str, bool] = {}

    # 1. period = 14 (task specified 14)
    checks["01_period_is_14"] = params.get("period") == 14

    # 2. timeframe = "Chart"
    checks["02_timeframe_chart"] = params.get("timeframe") == "Chart"

    # 3. use_btc_source = false
    checks["03_btc_source_false"] = params.get("use_btc_source") is False

    # 4. use_long_range = true (task required)
    checks["04_use_long_range_true"] = params.get("use_long_range") is True

    # 5. long_rsi_more — LOWER bound, task said 0-30 oversold, so more should be ~0
    long_more = params.get("long_rsi_more")
    checks["05_long_rsi_more_valid"] = isinstance(long_more, (int, float)) and 0 <= long_more <= 30

    # 6. long_rsi_less — UPPER bound, task said 0-30 oversold, so less should be ~30
    long_less = params.get("long_rsi_less")
    checks["06_long_rsi_less_valid"] = isinstance(long_less, (int, float)) and 20 <= long_less <= 40

    # 7. more < less constraint
    checks["07_long_more_lt_less"] = (
        isinstance(long_more, (int, float)) and isinstance(long_less, (int, float)) and long_more < long_less
    )

    # 8. use_short_range = true (task required)
    checks["08_use_short_range_true"] = params.get("use_short_range") is True

    # 9. short_rsi_less — UPPER bound, task said 70-100, so less should be ~100
    short_less = params.get("short_rsi_less")
    checks["09_short_rsi_less_valid"] = isinstance(short_less, (int, float)) and 70 <= short_less <= 100

    # 10. short_rsi_more — LOWER bound, task said 70-100, so more should be ~70
    short_more = params.get("short_rsi_more")
    checks["10_short_rsi_more_valid"] = isinstance(short_more, (int, float)) and 60 <= short_more <= 80

    # 11. more < less constraint for short
    checks["11_short_more_lt_less"] = (
        isinstance(short_more, (int, float)) and isinstance(short_less, (int, float)) and short_more < short_less
    )

    # 12. use_cross_level = true (task required)
    checks["12_use_cross_level_true"] = params.get("use_cross_level") is True

    # 13. cross_long_level = 30
    checks["13_cross_long_level_30"] = params.get("cross_long_level") == 30

    # 14. cross_short_level = 70
    checks["14_cross_short_level_70"] = params.get("cross_short_level") == 70

    # 15. opposite_signal = false (task: no opposite)
    checks["15_opposite_signal_false"] = params.get("opposite_signal") is False

    # 16. use_cross_memory = true (task required)
    checks["16_use_cross_memory_true"] = params.get("use_cross_memory") is True

    # 17. cross_memory_bars = 3 (task specified)
    checks["17_cross_memory_bars_3"] = params.get("cross_memory_bars") == 3

    # 18. All 15 params present
    expected_keys = {
        "period",
        "timeframe",
        "use_btc_source",
        "use_long_range",
        "long_rsi_more",
        "long_rsi_less",
        "use_short_range",
        "short_rsi_less",
        "short_rsi_more",
        "use_cross_level",
        "cross_long_level",
        "cross_short_level",
        "opposite_signal",
        "use_cross_memory",
        "cross_memory_bars",
    }
    checks["18_all_params_present"] = expected_keys.issubset(set(params.keys()))

    # 19. Reasoning mentions AND logic
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["19_understands_and_logic"] = any(
            w in r_lower for w in ["and", "both", "combine", "together", "intersection"]
        )
    else:
        checks["19_understands_and_logic"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.95  # 95% = max 1 miss out of 19

    return result


# ═══════════════════════════════════════════════════════════════════
# MACD Validation — per-parameter
# ═══════════════════════════════════════════════════════════════════


def validate_macd_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate MACD params — every single field checked individually."""
    result = ValidationResult(
        agent=agent,
        node="macd",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    params = parsed.get("macd_params", parsed)
    checks: dict[str, bool] = {}

    # 1. enable_visualization = false
    checks["01_visualization_false"] = params.get("enable_visualization") is False

    # 2. timeframe = "Chart"
    checks["02_timeframe_chart"] = params.get("timeframe") == "Chart"

    # 3. use_btc_source = false
    checks["03_btc_source_false"] = params.get("use_btc_source") is False

    # 4. fast_period = 12
    checks["04_fast_period_12"] = params.get("fast_period") == 12

    # 5. slow_period = 26
    checks["05_slow_period_26"] = params.get("slow_period") == 26

    # 6. fast < slow constraint
    fast = params.get("fast_period", 0)
    slow = params.get("slow_period", 0)
    checks["06_fast_lt_slow"] = isinstance(fast, (int, float)) and isinstance(slow, (int, float)) and fast < slow

    # 7. signal_period = 9
    checks["07_signal_period_9"] = params.get("signal_period") == 9

    # 8. source = "close"
    checks["08_source_close"] = params.get("source") == "close"

    # 9. use_macd_cross_zero = true (task required)
    checks["09_use_cross_zero_true"] = params.get("use_macd_cross_zero") is True

    # 10. opposite_macd_cross_zero = false
    checks["10_opposite_cross_zero_false"] = params.get("opposite_macd_cross_zero") is False

    # 11. macd_cross_zero_level = 0
    checks["11_cross_zero_level_0"] = params.get("macd_cross_zero_level") == 0

    # 12. use_macd_cross_signal = true (task required)
    checks["12_use_cross_signal_true"] = params.get("use_macd_cross_signal") is True

    # 13. signal_only_if_macd_positive = true (task required)
    checks["13_signal_positive_true"] = params.get("signal_only_if_macd_positive") is True

    # 14. opposite_macd_cross_signal = false
    checks["14_opposite_cross_signal_false"] = params.get("opposite_macd_cross_signal") is False

    # 15. disable_signal_memory = false (keep memory ON)
    checks["15_disable_memory_false"] = params.get("disable_signal_memory") is False

    # 16. signal_memory_bars = 3 (task specified)
    # Some agents might put 5 (default) if they missed the task value
    checks["16_memory_bars_3"] = params.get("signal_memory_bars") == 3

    # 17. All 15 params present
    expected_keys = {
        "enable_visualization",
        "timeframe",
        "use_btc_source",
        "fast_period",
        "slow_period",
        "signal_period",
        "source",
        "use_macd_cross_zero",
        "opposite_macd_cross_zero",
        "macd_cross_zero_level",
        "use_macd_cross_signal",
        "signal_only_if_macd_positive",
        "opposite_macd_cross_signal",
        "disable_signal_memory",
        "signal_memory_bars",
    }
    checks["17_all_params_present"] = expected_keys.issubset(set(params.keys()))

    # 18. Reasoning mentions OR logic
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["18_understands_or_logic"] = any(w in r_lower for w in ["or", "either", "independen"])
    else:
        checks["18_understands_or_logic"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.95  # 95% = max 1 miss out of 18

    return result


# ═══════════════════════════════════════════════════════════════════
# OPTIMIZATION Validation — per-parameter {enabled, min, max, step}
# ═══════════════════════════════════════════════════════════════════


def _check_opt_param(
    params: dict,
    key: str,
    expected_enabled: bool,
    expected_min: float | None,
    expected_max: float | None,
    expected_step: float | None,
) -> dict[str, bool]:
    """Validate a single optimizationParam entry."""
    checks: dict[str, bool] = {}
    prefix = key

    entry = params.get(key, {})
    if not isinstance(entry, dict):
        checks[f"{prefix}_exists"] = False
        return checks

    checks[f"{prefix}_exists"] = True
    checks[f"{prefix}_enabled"] = entry.get("enabled") is expected_enabled

    if expected_enabled and expected_min is not None:
        checks[f"{prefix}_min"] = entry.get("min") == expected_min
        checks[f"{prefix}_max"] = entry.get("max") == expected_max
        checks[f"{prefix}_step"] = entry.get("step") == expected_step
        # min < max constraint
        e_min = entry.get("min", 0)
        e_max = entry.get("max", 0)
        if isinstance(e_min, (int, float)) and isinstance(e_max, (int, float)):
            checks[f"{prefix}_min_lt_max"] = e_min < e_max
        else:
            checks[f"{prefix}_min_lt_max"] = False

    return checks


def validate_optimization_response(agent: str, response: str, latency_ms: float) -> ValidationResult:
    """Validate optimization ranges — {enabled, min, max, step} per param."""
    result = ValidationResult(
        agent=agent,
        node="optimization",
        passed=False,
        score=0.0,
        raw_response=response,
        latency_ms=latency_ms,
    )

    parsed = _extract_json(response)
    if not parsed:
        result.error = "Failed to parse JSON from response"
        return result

    result.parsed_json = parsed
    checks: dict[str, bool] = {}

    # --- RSI optimizationParams ---
    rsi_opt = parsed.get("rsi_optimizationParams", {})
    checks["rsi_section_exists"] = isinstance(rsi_opt, dict) and len(rsi_opt) > 0

    # Enabled RSI params (6)
    checks.update(_check_opt_param(rsi_opt, "period", True, 7, 21, 2))
    checks.update(_check_opt_param(rsi_opt, "long_rsi_more", True, 10, 40, 5))
    checks.update(_check_opt_param(rsi_opt, "long_rsi_less", True, 55, 85, 5))
    checks.update(_check_opt_param(rsi_opt, "cross_long_level", True, 20, 40, 5))
    checks.update(_check_opt_param(rsi_opt, "cross_short_level", True, 60, 80, 5))
    checks.update(_check_opt_param(rsi_opt, "cross_memory_bars", True, 1, 10, 1))

    # Disabled RSI params (2) — use_short_range=false
    checks.update(_check_opt_param(rsi_opt, "short_rsi_less", False, None, None, None))
    checks.update(_check_opt_param(rsi_opt, "short_rsi_more", False, None, None, None))

    # --- MACD optimizationParams ---
    macd_opt = parsed.get("macd_optimizationParams", {})
    checks["macd_section_exists"] = isinstance(macd_opt, dict) and len(macd_opt) > 0

    # Enabled MACD params (4)
    checks.update(_check_opt_param(macd_opt, "fast_period", True, 8, 16, 2))
    checks.update(_check_opt_param(macd_opt, "slow_period", True, 20, 30, 2))
    checks.update(_check_opt_param(macd_opt, "signal_period", True, 6, 12, 1))
    checks.update(_check_opt_param(macd_opt, "signal_memory_bars", True, 1, 10, 1))

    # Disabled MACD param (1) — use_macd_cross_zero=false
    checks.update(_check_opt_param(macd_opt, "macd_cross_zero_level", False, None, None, None))

    # All 8 RSI keys present
    expected_rsi_keys = {
        "period",
        "long_rsi_more",
        "long_rsi_less",
        "short_rsi_less",
        "short_rsi_more",
        "cross_long_level",
        "cross_short_level",
        "cross_memory_bars",
    }
    checks["rsi_all_8_keys"] = expected_rsi_keys.issubset(set(rsi_opt.keys()))

    # All 5 MACD keys present
    expected_macd_keys = {
        "fast_period",
        "slow_period",
        "signal_period",
        "macd_cross_zero_level",
        "signal_memory_bars",
    }
    checks["macd_all_5_keys"] = expected_macd_keys.issubset(set(macd_opt.keys()))

    # Reasoning mentions grid/sweep/combinations
    reasoning = parsed.get("reasoning", "")
    if isinstance(reasoning, str):
        r_lower = reasoning.lower()
        checks["understands_grid_search"] = any(
            w in r_lower for w in ["grid", "sweep", "combin", "search", "iteration", "disabled", "excluded"]
        )
    else:
        checks["understands_grid_search"] = False

    result.checks = checks
    passed_count = sum(1 for v in checks.values() if v)
    result.score = passed_count / len(checks)
    result.passed = result.score >= 0.90  # 90% threshold (many checks)

    return result


# ═══════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════


async def test_agent(agent_name: str, client: Any, node: str) -> ValidationResult:
    """Send test prompt to agent and validate response."""
    system_prompt: str = SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPTS["deepseek"])

    if node == "rsi":
        user_prompt = RSI_TEST_PROMPT
        validator = validate_rsi_response
    elif node == "macd":
        user_prompt = MACD_TEST_PROMPT
        validator = validate_macd_response
    else:
        user_prompt = OPTIMIZATION_TEST_PROMPT
        validator = validate_optimization_response

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_prompt),
    ]

    start = time.perf_counter()
    try:
        response: LLMResponse = await client.chat(messages)  # type: ignore[union-attr]
        latency = (time.perf_counter() - start) * 1000
        return validator(agent_name, response.content, latency)
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
    """Print formatted test result with per-parameter breakdown."""
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
        print(f"  {'#':<4} {'Check':<40} {'Result':>8}")
        print(f"  {'─' * 52}")
        for i, (check, passed) in enumerate(result.checks.items(), 1):
            icon = "✅" if passed else "❌"
            print(f"  {i:<4} {check:<40} {icon:>8}")

    if result.parsed_json:
        if result.node == "optimization":
            # Show both RSI and MACD optimization params
            for section in ("rsi_optimizationParams", "macd_optimizationParams"):
                opt = result.parsed_json.get(section, {})
                if opt:
                    print(f"\n  📋 {section}:")
                    for k, v in opt.items():
                        print(f"     {k}: {v}")
        else:
            params_key = "rsi_params" if result.node == "rsi" else "macd_params"
            params = result.parsed_json.get(params_key, {})
            if params:
                print("\n  📋 Returned params:")
                for k, v in params.items():
                    print(f"     {k}: {v}")

        reasoning = result.parsed_json.get("reasoning", "")
        if reasoning:
            truncated = reasoning[:250] + ("..." if len(reasoning) > 250 else "")
            print(f"\n  💬 Reasoning: {truncated}")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Agent Node Understanding Test v2")
    parser.add_argument(
        "--agent",
        choices=["deepseek", "qwen", "perplexity", "all"],
        default="all",
        help="Which agent to test (default: all)",
    )
    parser.add_argument(
        "--node",
        choices=["rsi", "macd", "optimization", "both", "all"],
        default="all",
        help="Which node to test (default: all = rsi + macd + optimization)",
    )
    args = parser.parse_args()

    print("\n" + "═" * 70)
    print("  🧪 AI Agent Node Understanding Test v2 (Per-Parameter + Optimization)")
    print("  RSI: 15 params, 19 checks | MACD: 15 params, 18 checks | OPT: 13 params, ~55 checks")
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
                max_tokens=2048,
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
                max_tokens=2048,
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
                max_tokens=2048,
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
    if args.node == "all":
        nodes = ["rsi", "macd", "optimization"]
    elif args.node == "both":
        nodes = ["rsi", "macd"]
    else:
        nodes = [args.node]

    # Run tests
    results: list[ValidationResult] = []

    for node in nodes:
        print(f"\n{'─' * 70}")
        print(f"  Testing {node.upper()} — every parameter...")
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
    print(f"  {'Agent':<15} {'Node':<14} {'Score':>10} {'Checks':>12} {'Status':>10} {'Latency':>10}")
    print(f"  {'─' * 71}")

    total_passed = 0
    total_tests = 0

    for r in results:
        passed_checks = sum(1 for v in r.checks.values() if v) if r.checks else 0
        total_checks = len(r.checks) if r.checks else 0
        status = "PASS ✅" if r.passed else "FAIL ❌"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms > 0 else "N/A"
        print(
            f"  {r.agent:<15} {r.node:<14} {r.score:>9.0%} "
            f"{passed_checks:>5}/{total_checks:<5} {status:>10} {latency:>10}"
        )
        total_tests += 1
        if r.passed:
            total_passed += 1

    print(f"\n  Total: {total_passed}/{total_tests} agents passed (RSI/MACD: 95% threshold, OPT: 90%)")

    if total_passed == total_tests:
        print("\n  🎉 All agents understand RSI/MACD parameters AND optimization ranges!")
    else:
        failed = [r for r in results if not r.passed]
        print(f"\n  ⚠️  {len(failed)} test(s) failed:")
        for r in failed:
            failed_checks = [k for k, v in r.checks.items() if not v] if r.checks else []
            print(f"     {r.agent}/{r.node}: {r.error or ', '.join(failed_checks)}")

    # Cleanup clients
    for client in clients.values():
        if hasattr(client, "close"):
            await client.close()  # type: ignore[union-attr]

    # Save results
    results_path = Path(__file__).parent.parent / "logs" / "agent_node_test_results.json"
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
                "params": (
                    r.parsed_json.get(
                        "rsi_optimizationParams"
                        if r.node == "optimization"
                        else ("rsi_params" if r.node == "rsi" else "macd_params"),
                        {},
                    )
                    if r.parsed_json
                    else {}
                ),
                "reasoning": r.parsed_json.get("reasoning", "") if r.parsed_json else "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"\n  📁 Results saved to: {results_path}")
    sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    asyncio.run(main())
