"""
Real API Comprehension Test — DeepSeek, Qwen, Perplexity.

PURPOSE:
  Sends block documentation excerpts from STRATEGY_GENERATION_TEMPLATE to each
  real AI agent (DeepSeek, Qwen, Perplexity) and validates that they correctly
  parse and understand the block parameters, defaults, optimization ranges,
  and signal modes.

  This is the "live API" counterpart to test_agent_block_comprehension.py (offline).

HOW IT WORKS:
  1. Extract a block documentation section from the raw template
  2. Build a structured prompt asking the agent to parse the block
  3. Send via the project's LLM clients (DeepSeek/Qwen/Perplexity)
  4. Parse the JSON response and compare against BLOCK_GROUND_TRUTH
  5. Score each agent on: params, defaults, optimization ranges, modes

USAGE:
  pytest tests/backend/agents/test_agent_real_api_comprehension.py -v -m api_live
  pytest tests/backend/agents/test_agent_real_api_comprehension.py -v -m api_live -k deepseek
  pytest tests/backend/agents/test_agent_real_api_comprehension.py -v -m api_live -k qwen

COST ESTIMATE:
  ~34 blocks x 3 agents = 102 API calls
  ~$0.05-0.15 total (DeepSeek/Qwen are very cheap; Perplexity slightly more)

REQUIRES:
  Environment variables: DEEPSEEK_API_KEY, QWEN_API_KEY, PERPLEXITY_API_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
import textwrap
from typing import Any

import aiohttp
import pytest
from dotenv import load_dotenv
from loguru import logger

# Load .env BEFORE importing backend modules (they read env vars at import time)
load_dotenv(override=True)

from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider, LLMResponse
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient
from backend.agents.prompts.templates import STRATEGY_GENERATION_TEMPLATE

# =============================================================================
# GROUND TRUTH — ALL 34 Library blocks
# =============================================================================

TEST_BLOCKS: dict[str, dict[str, Any]] = {
    # ===== ENTRY INDICATORS =====
    "rsi": {
        "header": "RSI UNIVERSAL NODE",
        "params": {
            "period": 14,
            "long_rsi_more": 30,
            "long_rsi_less": 70,
            "short_rsi_less": 70,
            "short_rsi_more": 30,
            "cross_long_level": 30,
            "cross_short_level": 70,
            "cross_memory_bars": 5,
        },
        "optimizable": [
            "period",
            "long_rsi_more",
            "long_rsi_less",
            "cross_long_level",
            "cross_short_level",
            "cross_memory_bars",
        ],
        "modes": ["RANGE", "CROSS"],
    },
    "macd": {
        "header": "MACD UNIVERSAL NODE",
        "params": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "signal_memory_bars": 5,
        },
        "optimizable": [
            "fast_period",
            "slow_period",
            "signal_period",
            "signal_memory_bars",
        ],
        "modes": ["CROSS ZERO", "CROSS SIGNAL"],
    },
    "stochastic": {
        "header": "STOCHASTIC UNIVERSAL NODE",
        "params": {
            "stoch_k_length": 14,
            "stoch_k_smoothing": 3,
            "stoch_d_smoothing": 3,
        },
        "optimizable": [
            "stoch_k_length",
            "stoch_k_smoothing",
            "stoch_d_smoothing",
        ],
        "modes": ["RANGE", "CROSS level", "K/D CROSS"],
    },
    "supertrend": {
        "header": "SUPERTREND UNIVERSAL NODE",
        "params": {"period": 10, "multiplier": 3.0},
        "optimizable": ["period", "multiplier"],
        "modes": ["FILTER", "SIGNAL"],
    },
    "qqe": {
        "header": "QQE UNIVERSAL NODE",
        "params": {
            "rsi_period": 14,
            "qqe_factor": 4.238,
            "smoothing_period": 5,
            "qqe_signal_memory_bars": 5,
        },
        "optimizable": [
            "rsi_period",
            "qqe_factor",
            "smoothing_period",
            "qqe_signal_memory_bars",
        ],
        "modes": ["CROSS SIGNAL"],
    },
    "atr_volatility": {
        "header": "ATR VOLATILITY NODE",
        "params": {
            "atr_length1": 20,
            "atr_length2": 100,
            "atr_diff_percent": 10,
        },
        "optimizable": ["atr_length1", "atr_length2", "atr_diff_percent"],
        "modes": [],
    },
    "volume_filter": {
        "header": "VOLUME FILTER NODE",
        "params": {
            "vol_length1": 20,
            "vol_length2": 100,
            "vol_diff_percent": 10,
        },
        "optimizable": ["vol_length1", "vol_length2", "vol_diff_percent"],
        "modes": [],
    },
    "highest_lowest_bar": {
        "header": "HIGHEST/LOWEST BAR NODE",
        "params": {
            "hl_lookback_bars": 10,
            "hl_price_percent": 0,
            "hl_atr_percent": 0,
            "atr_hl_length": 50,
        },
        "optimizable": [
            "hl_lookback_bars",
            "hl_price_percent",
            "hl_atr_percent",
            "atr_hl_length",
        ],
        "modes": [],
    },
    "two_mas": {
        "header": "TWO MAs NODE",
        "params": {
            "ma1_length": 50,
            "ma2_length": 100,
            "ma_cross_memory_bars": 5,
        },
        "optimizable": ["ma1_length", "ma2_length", "ma_cross_memory_bars"],
        "modes": ["MA CROSS", "MA1 as FILTER"],
    },
    "accumulation_areas": {
        "header": "ACCUMULATION AREAS NODE",
        "params": {
            "backtracking_interval": 30,
            "min_bars_to_execute": 5,
        },
        "optimizable": ["backtracking_interval", "min_bars_to_execute"],
        "modes": [],
    },
    "keltner_bollinger": {
        "header": "KELTNER/BOLLINGER CHANNEL NODE",
        "params": {
            "keltner_length": 14,
            "keltner_mult": 1.5,
            "bb_length": 20,
            "bb_deviation": 2,
        },
        "optimizable": ["keltner_length", "keltner_mult", "bb_length", "bb_deviation"],
        "modes": ["Rebound", "Breakout"],
    },
    "rvi_filter": {
        "header": "RVI (Relative Vigor Index) NODE",
        "params": {
            "rvi_length": 10,
            "rvi_ma_length": 2,
            "rvi_long_more": 1,
            "rvi_long_less": 50,
            "rvi_short_less": 100,
            "rvi_short_more": 50,
        },
        "optimizable": [
            "rvi_length",
            "rvi_ma_length",
            "rvi_long_more",
            "rvi_long_less",
            "rvi_short_less",
            "rvi_short_more",
        ],
        "modes": [],
    },
    "mfi_filter": {
        "header": "MFI (Money Flow Index) NODE",
        "params": {
            "mfi_length": 14,
            "mfi_long_more": 1,
            "mfi_long_less": 60,
            "mfi_short_less": 100,
            "mfi_short_more": 50,
        },
        "optimizable": [
            "mfi_length",
            "mfi_long_more",
            "mfi_long_less",
            "mfi_short_less",
            "mfi_short_more",
        ],
        "modes": [],
    },
    "cci_filter": {
        "header": "CCI (Commodity Channel Index) NODE",
        "params": {
            "cci_length": 14,
            "cci_long_more": -400,
            "cci_long_less": 400,
            "cci_short_less": 400,
            "cci_short_more": 10,
        },
        "optimizable": [
            "cci_length",
            "cci_long_more",
            "cci_long_less",
            "cci_short_less",
            "cci_short_more",
        ],
        "modes": [],
    },
    "momentum_filter": {
        "header": "MOMENTUM NODE",
        "params": {
            "momentum_length": 14,
            "momentum_long_more": -100,
            "momentum_long_less": 10,
            "momentum_short_less": 95,
            "momentum_short_more": -30,
        },
        "optimizable": [
            "momentum_length",
            "momentum_long_more",
            "momentum_long_less",
            "momentum_short_less",
            "momentum_short_more",
        ],
        "modes": [],
    },
    # ===== CONDITIONS =====
    "crossover": {
        "header": "CROSSOVER NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
    },
    "crossunder": {
        "header": "CROSSUNDER NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
    },
    "greater_than": {
        "header": "GREATER THAN NODE",
        "params": {"value": 0},
        "optimizable": [],
        "modes": [],
    },
    "less_than": {
        "header": "LESS THAN NODE",
        "params": {"value": 0},
        "optimizable": [],
        "modes": [],
    },
    "equals": {
        "header": "EQUALS NODE",
        "params": {"value": 0, "tolerance": 0.001},
        "optimizable": [],
        "modes": [],
    },
    "between": {
        "header": "BETWEEN NODE",
        "params": {"min_value": 0, "max_value": 100},
        "optimizable": [],
        "modes": [],
    },
    # ===== DIVERGENCE =====
    "divergence": {
        "header": "DIVERGENCE NODE",
        "params": {
            "pivot_interval": 9,
            "rsi_period": 14,
            "stoch_length": 14,
            "momentum_length": 10,
            "cmf_period": 21,
            "mfi_length": 14,
            "keep_diver_signal_memory_bars": 5,
        },
        "optimizable": [
            "pivot_interval",
            "rsi_period",
            "stoch_length",
            "momentum_length",
            "cmf_period",
            "mfi_length",
            "keep_diver_signal_memory_bars",
        ],
        "modes": [],
    },
    # ===== DCA =====
    "dca": {
        "header": "DCA (Dollar-Cost Averaging) NODE",
        "params": {
            "grid_size_percent": 15,
            "order_count": 5,
            "martingale_coefficient": 1.0,
            "log_steps_coefficient": 1.0,
            "first_order_offset": 0,
        },
        "optimizable": [
            "grid_size_percent",
            "order_count",
            "martingale_coefficient",
            "log_steps_coefficient",
            "first_order_offset",
        ],
        "modes": [],
    },
    "manual_grid": {
        "header": "MANUAL GRID NODE",
        "params": {},
        "optimizable": [],
        "modes": [],
    },
    # ===== EXIT SL/TP BLOCKS =====
    "static_sltp": {
        "header": "STATIC SL/TP NODE",
        "params": {
            "take_profit_percent": 1.5,
            "stop_loss_percent": 1.5,
            "breakeven_activation_percent": 0.5,
            "new_breakeven_sl_percent": 0.1,
        },
        "optimizable": [
            "take_profit_percent",
            "stop_loss_percent",
            "breakeven_activation_percent",
            "new_breakeven_sl_percent",
        ],
        "modes": [],
    },
    "trailing_stop_exit": {
        "header": "TRAILING STOP EXIT NODE",
        "params": {
            "activation_percent": 1.0,
            "trailing_percent": 0.5,
        },
        "optimizable": ["activation_percent", "trailing_percent"],
        "modes": [],
    },
    "atr_exit": {
        "header": "ATR EXIT NODE",
        "params": {
            "atr_sl_period": 140,
            "atr_sl_multiplier": 4.0,
            "atr_tp_period": 140,
            "atr_tp_multiplier": 4.0,
        },
        "optimizable": [
            "atr_sl_period",
            "atr_sl_multiplier",
            "atr_tp_period",
            "atr_tp_multiplier",
        ],
        "modes": [],
    },
    "multi_tp_exit": {
        "header": "MULTI TP LEVELS NODE",
        "params": {
            "tp1_percent": 1.0,
            "tp2_percent": 2.0,
            "tp3_percent": 3.0,
            "tp1_close_percent": 33,
            "tp2_close_percent": 33,
            "tp3_close_percent": 34,
        },
        "optimizable": [
            "tp1_percent",
            "tp2_percent",
            "tp3_percent",
            "tp1_close_percent",
            "tp2_close_percent",
            "tp3_close_percent",
        ],
        "modes": [],
    },
    # ===== CLOSE BY INDICATOR =====
    "close_by_time": {
        "header": "CLOSE BY TIME NODE",
        "params": {
            "bars_since_entry": 10,
            "min_profit_percent": 0,
        },
        "optimizable": ["bars_since_entry", "min_profit_percent"],
        "modes": [],
    },
    "close_channel": {
        "header": "CHANNEL CLOSE NODE",
        "params": {
            "keltner_length": 14,
            "keltner_mult": 1.5,
            "bb_length": 20,
            "bb_deviation": 2,
        },
        "optimizable": ["keltner_length", "keltner_mult", "bb_length", "bb_deviation"],
        "modes": ["Rebound", "Breakout"],
    },
    "close_ma_cross": {
        "header": "TWO MAs CLOSE NODE",
        "params": {
            "ma1_length": 10,
            "ma2_length": 30,
            "min_profit_percent": 1,
        },
        "optimizable": ["ma1_length", "ma2_length", "min_profit_percent"],
        "modes": [],
    },
    "close_rsi": {
        "header": "CLOSE BY RSI NODE",
        "params": {
            "rsi_close_length": 14,
            "rsi_long_more": 70,
            "rsi_long_less": 100,
            "rsi_short_less": 30,
            "rsi_short_more": 1,
            "rsi_cross_long_level": 70,
            "rsi_cross_short_level": 30,
        },
        "optimizable": [
            "rsi_close_length",
            "rsi_long_more",
            "rsi_long_less",
            "rsi_short_less",
            "rsi_short_more",
            "rsi_cross_long_level",
            "rsi_cross_short_level",
        ],
        "modes": ["RSI REACH", "RSI CROSS"],
    },
    "close_stochastic": {
        "header": "CLOSE BY STOCHASTIC NODE",
        "params": {
            "stoch_close_k_length": 14,
            "stoch_close_k_smoothing": 3,
            "stoch_close_d_smoothing": 3,
            "stoch_long_more": 80,
            "stoch_long_less": 100,
            "stoch_short_less": 20,
            "stoch_short_more": 1,
            "stoch_cross_long_level": 80,
            "stoch_cross_short_level": 20,
        },
        "optimizable": [
            "stoch_close_k_length",
            "stoch_close_k_smoothing",
            "stoch_close_d_smoothing",
            "stoch_long_more",
            "stoch_long_less",
            "stoch_short_less",
            "stoch_short_more",
            "stoch_cross_long_level",
            "stoch_cross_short_level",
        ],
        "modes": ["STOCH REACH", "STOCH CROSS"],
    },
    "close_psar": {
        "header": "CLOSE BY PARABOLIC SAR NODE",
        "params": {
            "psar_start": 0.02,
            "psar_increment": 0.02,
            "psar_maximum": 0.2,
            "psar_close_nth_bar": 1,
        },
        "optimizable": [
            "psar_start",
            "psar_increment",
            "psar_maximum",
            "psar_close_nth_bar",
        ],
        "modes": [],
    },
}

# =============================================================================
# Prompt to send to each agent
# =============================================================================

COMPREHENSION_PROMPT = textwrap.dedent("""\
    You are given the documentation for a trading strategy block from a Strategy Builder.
    Parse the documentation EXACTLY and return a JSON object with these fields:

    {{
      "block_name": "<name of the block>",
      "params": {{
        "<param_name>": <default_value>,
        ...
      }},
      "optimizable_params": ["<param_name>", ...],
      "signal_modes": ["<mode_name>", ...],
      "key_constraint": "<one critical constraint you noticed>"
    }}

    RULES:
    - Include ALL numeric parameters you find with their DEFAULT values
    - Default values must be NUMBERS, not strings (e.g. 14 not "14")
    - IMPORTANT: Parameters can appear ANYWHERE in the text — in the main "Params:" line,
      inside sub-mode descriptions, or inline in parentheses like param_name=value.
      For example, "(rsi_long_more=70, rsi_long_less=100)" means two params with defaults 70 and 100.
      Scan the ENTIRE documentation text for param_name=value or param_name(value) patterns.
    - List ALL optimizable parameters (those listed in "Optimizable params:" section)
    - List ALL signal modes. Signal modes include:
      * Named modes like RANGE, CROSS, FILTER, SIGNAL
      * Numbered items like "1) MA CROSS signal" and "2) MA1 as FILTER" → ["MA CROSS", "MA1 as FILTER"]
      * Sub-modes: "Two sub-modes:" followed by names like "RSI REACH" and "RSI CROSS" → ["RSI REACH", "RSI CROSS"]
      * Mode-like option params: band_to_close with options 'Rebound'/'Breakout' → ["Rebound", "Breakout"]
    - If no signal modes are mentioned, return empty list for signal_modes
    - If no numeric parameters exist (e.g. pure logic nodes), return empty dict for params
    - If no optimizable parameters exist, return empty list for optimizable_params
    - Return ONLY the JSON object, no markdown, no explanation

    === BLOCK DOCUMENTATION ===
    {block_doc}
    === END ===
""")


# =============================================================================
# Helpers
# =============================================================================


def _extract_block_doc(block_type: str, header: str) -> str:
    """Extract the block documentation section from the raw template."""
    template = STRATEGY_GENERATION_TEMPLATE
    idx = template.find(header)
    if idx < 0:
        raise ValueError(f"Header '{header}' not found in template")

    # Extract up to 3000 chars after header (covers full block doc)
    section = template[idx : idx + 3000]

    # Find the end of this block's section by looking for the NEXT block header
    # Patterns: "XXX NODE (Strategy Builder)", "XXX NODE:", "=== SECTION ==="
    import re

    # Look for next block/section header after current one
    next_header = re.search(
        r"\n(?:"
        r"[A-Z][A-Z /()]+NODE \(Strategy Builder\)"  # Full block headers
        r"|[A-Z][A-Z /()]+NODE:"  # Short condition node headers
        r"|=== [A-Z]"  # Section separators
        r")",
        section[len(header) :],
    )
    if next_header:
        section = section[: len(header) + next_header.start()]

    return section.strip()


def _parse_llm_json(response_text: str) -> dict[str, Any] | None:
    """Parse JSON from LLM response, handling markdown fences and extra text."""
    text = response_text.strip()

    # Remove markdown code fences
    if "```json" in text:
        text = text.split("```json", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]

    text = text.strip()

    # Try to find JSON object
    brace_start = text.find("{")
    if brace_start < 0:
        return None

    # Find matching closing brace
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[brace_start : i + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
    return None


def _score_comprehension(
    parsed: dict[str, Any],
    truth: dict[str, Any],
    block_type: str,
) -> dict[str, Any]:
    """Score how well the agent understood the block.

    Returns:
        {
            "params_found": N/M,
            "defaults_correct": N/M,
            "optimizable_found": N/M,
            "modes_found": N/M,
            "total_score": 0.0 - 1.0,
            "details": { ... }
        }
    """
    result: dict[str, Any] = {
        "block": block_type,
        "params_found": 0,
        "params_total": len(truth["params"]),
        "defaults_correct": 0,
        "optimizable_found": 0,
        "optimizable_total": len(truth["optimizable"]),
        "modes_found": 0,
        "modes_total": len(truth["modes"]),
        "details": {},
    }

    # Score params & defaults
    agent_params = parsed.get("params", {})
    for param_name, expected_default in truth["params"].items():
        if param_name in agent_params:
            result["params_found"] += 1
            agent_val = agent_params[param_name]
            # Compare with type tolerance (int vs float)
            try:
                if abs(float(agent_val) - float(expected_default)) < 0.01:
                    result["defaults_correct"] += 1
                else:
                    result["details"][param_name] = f"wrong default: got {agent_val}, expected {expected_default}"
            except (ValueError, TypeError):
                result["details"][param_name] = f"non-numeric default: got {agent_val!r}, expected {expected_default}"
        else:
            result["details"][param_name] = "MISSING from agent response"

    # Score optimizable params
    agent_opt = [p.lower() for p in parsed.get("optimizable_params", [])]
    for param in truth["optimizable"]:
        if param.lower() in agent_opt:
            result["optimizable_found"] += 1

    # Score modes — use flexible matching with normalization
    agent_modes_raw = parsed.get("signal_modes", [])
    # Normalize agent modes: uppercase, strip extra whitespace
    agent_modes = [m.upper().strip() for m in agent_modes_raw]
    for mode in truth["modes"]:
        mode_upper = mode.upper().strip()
        # Try exact match, substring, or containment
        if any(mode_upper == am or mode_upper in am or am in mode_upper for am in agent_modes):
            result["modes_found"] += 1
        else:
            # Flexible keyword matching for tricky modes like "K/D CROSS"
            # Normalize: remove punctuation, compare key words
            import re

            mode_words = set(re.findall(r"[A-Z0-9]+", mode_upper))
            matched = False
            for am in agent_modes:
                am_words = set(re.findall(r"[A-Z0-9]+", am))
                # If all significant words from expected mode appear in agent mode
                if mode_words and mode_words.issubset(am_words):
                    matched = True
                    break
                # Special case: "K/D CROSS" matches "KD CROSS", "K_D_CROSS", etc.
                if (
                    "K" in mode_words
                    and "D" in mode_words
                    and "CROSS" in mode_words
                    and ("KD" in am or "K/D" in am or "K_D" in am)
                    and "CROSS" in am
                ):
                    matched = True
                    break
            if matched:
                result["modes_found"] += 1

    # Total score (weighted: params 30%, defaults 30%, optimizable 20%, modes 20%)
    # For blocks with no params/optimizable/modes, those components score 1.0 (perfect)
    p_score = result["params_found"] / result["params_total"] if result["params_total"] > 0 else 1.0
    d_score = result["defaults_correct"] / result["params_total"] if result["params_total"] > 0 else 1.0
    o_score = result["optimizable_found"] / result["optimizable_total"] if result["optimizable_total"] > 0 else 1.0
    m_score = result["modes_found"] / result["modes_total"] if result["modes_total"] > 0 else 1.0

    result["total_score"] = round(0.30 * p_score + 0.30 * d_score + 0.20 * o_score + 0.20 * m_score, 3)

    return result


# =============================================================================
# Client factory
# =============================================================================


def _make_client(provider: str) -> DeepSeekClient | QwenClient | PerplexityClient | None:
    """Create LLM client from env vars. Returns None if key missing."""
    key_map = {
        "deepseek": ("DEEPSEEK_API_KEY", LLMProvider.DEEPSEEK, "deepseek-chat"),
        "qwen": ("QWEN_API_KEY", LLMProvider.QWEN, "qwen-plus"),
        "perplexity": ("PERPLEXITY_API_KEY", LLMProvider.PERPLEXITY, "sonar-pro"),
    }
    client_classes: dict[str, type[DeepSeekClient] | type[QwenClient] | type[PerplexityClient]] = {
        "deepseek": DeepSeekClient,
        "qwen": QwenClient,
        "perplexity": PerplexityClient,
    }
    env_key, llm_provider, model = key_map[provider]
    api_key = os.environ.get(env_key)
    if not api_key or "YOUR_" in api_key:
        return None

    # Perplexity needs longer timeout — its search-augmented generation is slower
    timeout = 120 if provider == "perplexity" else 60

    config = LLMConfig(
        provider=llm_provider,
        api_key=api_key,
        model=model,
        temperature=0.1,  # Low temperature for deterministic parsing
        max_tokens=2048,
        timeout_seconds=timeout,
        max_retries=3 if provider == "perplexity" else 2,
        retry_delay_seconds=2.0 if provider == "perplexity" else 1.0,
    )
    return client_classes[provider](config)


async def _ask_agent(
    client: DeepSeekClient | QwenClient | PerplexityClient,
    block_type: str,
    block_doc: str,
) -> dict[str, Any]:
    """Send block doc to agent and parse the JSON response."""
    prompt = COMPREHENSION_PROMPT.format(block_doc=block_doc)

    messages = [
        LLMMessage(role="system", content="You are a trading strategy block parser. Return ONLY valid JSON."),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        # Force a fresh session for each call to avoid "Event loop is closed" errors
        # when pytest-asyncio creates a new event loop per test function
        if client.session is not None and not client.session.closed:
            await client.session.close()
        client.session = None

        response: LLMResponse = await client.chat(messages)

        # Close session after use to prevent "Unclosed client session" warnings
        if client.session is not None and not client.session.closed:
            await client.session.close()
        client.session = None

        parsed = _parse_llm_json(response.content)
        if parsed is None:
            logger.warning(
                f"Failed to parse JSON from {client.PROVIDER.value} for {block_type}. "
                f"Raw response: {response.content[:200]}"
            )
            return {
                "raw": response.content,
                "parsed": None,
                "tokens": response.total_tokens,
                "latency_ms": response.latency_ms,
                "cost": response.estimated_cost,
            }
        return {
            "raw": response.content,
            "parsed": parsed,
            "tokens": response.total_tokens,
            "latency_ms": response.latency_ms,
            "cost": response.estimated_cost,
        }
    except Exception as e:
        logger.error(f"API call failed for {client.PROVIDER.value}/{block_type}: {type(e).__name__}: {e}")
        # Reset session on error too
        try:
            if client.session is not None and not client.session.closed:
                await client.session.close()
        except Exception:
            pass
        client.session = None
        # Mark network errors distinctly so tests can skip instead of fail
        error_type = type(e).__name__
        is_network_error = isinstance(
            e, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError, aiohttp.ClientError)
        )
        return {
            "raw": str(e),
            "parsed": None,
            "tokens": 0,
            "latency_ms": 0,
            "cost": 0,
            "network_error": is_network_error,
            "error_type": error_type,
        }


# =============================================================================
# Pytest markers and fixtures
# =============================================================================

pytestmark = [
    pytest.mark.api_live,
    pytest.mark.timeout(300),  # Allow up to 5 min for Perplexity's search-augmented responses
]


# Module-level client cache (avoids creating new clients per test)
_client_cache: dict[str, DeepSeekClient | QwenClient | PerplexityClient | None] = {}


def _get_cached_client(provider: str):
    """Get or create cached client for provider."""
    if provider not in _client_cache:
        _client_cache[provider] = _make_client(provider)
    return _client_cache[provider]


@pytest.fixture
def deepseek_client():
    """DeepSeek client (cached at module level)."""
    client = _get_cached_client("deepseek")
    if client is None:
        pytest.skip("DEEPSEEK_API_KEY not set or invalid")
    return client


@pytest.fixture
def qwen_client():
    """Qwen client (cached at module level)."""
    client = _get_cached_client("qwen")
    if client is None:
        pytest.skip("QWEN_API_KEY not set or invalid")
    return client


@pytest.fixture
def perplexity_client():
    """Perplexity client (cached at module level)."""
    client = _get_cached_client("perplexity")
    if client is None:
        pytest.skip("PERPLEXITY_API_KEY not set or invalid")
    return client


# =============================================================================
# Results collector (module-scoped for summary report)
# =============================================================================


_all_results: dict[str, dict[str, dict[str, Any]]] = {}


def _record_result(agent: str, block: str, score: dict[str, Any]) -> None:
    """Store result for final summary."""
    if agent not in _all_results:
        _all_results[agent] = {}
    _all_results[agent][block] = score


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestDeepSeekComprehension:
    """Test DeepSeek's understanding of block parameters."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("block_type", list(TEST_BLOCKS.keys()))
    async def test_block_comprehension(self, deepseek_client, block_type: str):
        """DeepSeek should correctly parse block params, defaults, and modes."""
        truth = TEST_BLOCKS[block_type]
        block_doc = _extract_block_doc(block_type, truth["header"])
        result = await _ask_agent(deepseek_client, block_type, block_doc)

        assert result["parsed"] is not None, (
            f"DeepSeek failed to return valid JSON for {block_type}. Raw: {result['raw'][:300]}"
        )

        score = _score_comprehension(result["parsed"], truth, block_type)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("deepseek", block_type, score)

        logger.info(
            f"🔵 DeepSeek/{block_type}: score={score['total_score']:.0%} "
            f"params={score['params_found']}/{score['params_total']} "
            f"defaults={score['defaults_correct']}/{score['params_total']} "
            f"opt={score['optimizable_found']}/{score['optimizable_total']} "
            f"modes={score['modes_found']}/{score['modes_total']} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        # Minimum threshold: 60% overall
        assert score["total_score"] >= 0.6, (
            f"DeepSeek comprehension too low for {block_type}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


class TestQwenComprehension:
    """Test Qwen's understanding of block parameters."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("block_type", list(TEST_BLOCKS.keys()))
    async def test_block_comprehension(self, qwen_client, block_type: str):
        """Qwen should correctly parse block params, defaults, and modes."""
        truth = TEST_BLOCKS[block_type]
        block_doc = _extract_block_doc(block_type, truth["header"])
        result = await _ask_agent(qwen_client, block_type, block_doc)

        assert result["parsed"] is not None, (
            f"Qwen failed to return valid JSON for {block_type}. Raw: {result['raw'][:300]}"
        )

        score = _score_comprehension(result["parsed"], truth, block_type)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("qwen", block_type, score)

        logger.info(
            f"🟢 Qwen/{block_type}: score={score['total_score']:.0%} "
            f"params={score['params_found']}/{score['params_total']} "
            f"defaults={score['defaults_correct']}/{score['params_total']} "
            f"opt={score['optimizable_found']}/{score['optimizable_total']} "
            f"modes={score['modes_found']}/{score['modes_total']} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        if score["total_score"] < 0.8:
            logger.warning(f"🟢 Qwen/{block_type} RAW response:\n{result['raw'][:500]}")

        assert score["total_score"] >= 0.6, (
            f"Qwen comprehension too low for {block_type}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


class TestPerplexityComprehension:
    """Test Perplexity's understanding of block parameters.

    Perplexity uses search-augmented generation which can be slower.
    Tests will skip (not fail) if the API is unreachable due to network issues.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("block_type", list(TEST_BLOCKS.keys()))
    async def test_block_comprehension(self, perplexity_client, block_type: str):
        """Perplexity should correctly parse block params, defaults, and modes."""
        truth = TEST_BLOCKS[block_type]
        block_doc = _extract_block_doc(block_type, truth["header"])
        result = await _ask_agent(perplexity_client, block_type, block_doc)

        # Skip on network errors (timeout, connection refused, etc.)
        if result.get("network_error"):
            pytest.skip(
                f"Perplexity API unreachable for {block_type}: "
                f"{result.get('error_type', 'unknown')} — check network/VPN/API status"
            )

        assert result["parsed"] is not None, (
            f"Perplexity failed to return valid JSON for {block_type}. Raw: {result['raw'][:300]}"
        )

        score = _score_comprehension(result["parsed"], truth, block_type)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("perplexity", block_type, score)

        logger.info(
            f"🟣 Perplexity/{block_type}: score={score['total_score']:.0%} "
            f"params={score['params_found']}/{score['params_total']} "
            f"defaults={score['defaults_correct']}/{score['params_total']} "
            f"opt={score['optimizable_found']}/{score['optimizable_total']} "
            f"modes={score['modes_found']}/{score['modes_total']} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        assert score["total_score"] >= 0.6, (
            f"Perplexity comprehension too low for {block_type}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


# =============================================================================
# SUMMARY TEST — runs after all agents, prints comparison table
# =============================================================================


class TestSummaryReport:
    """Print summary comparison after all agent tests complete."""

    def test_print_summary(self):
        """Print the comparative summary of all agent results."""
        if not _all_results:
            pytest.skip("No API results collected (all agents skipped?)")

        print("\n")
        print("=" * 90)
        print("  СВОДКА: ПОНИМАНИЕ БЛОКОВ AI-АГЕНТАМИ (Real API)")
        print("=" * 90)

        agents = sorted(_all_results.keys())
        blocks = sorted({b for agent_results in _all_results.values() for b in agent_results})

        # Header
        header = f"{'Блок':<20}"
        for agent in agents:
            header += f" | {agent:>12}"
        print(header)
        print("-" * len(header))

        # Per-block scores
        agent_totals: dict[str, list[float]] = {a: [] for a in agents}
        for block in blocks:
            row = f"{block:<20}"
            for agent in agents:
                if agent in _all_results and block in _all_results[agent]:
                    s = _all_results[agent][block]["total_score"]
                    agent_totals[agent].append(s)
                    emoji = "✅" if s >= 0.8 else ("⚠️" if s >= 0.6 else "❌")
                    row += f" | {s:>8.0%} {emoji}"
                else:
                    row += f" | {'—':>10}"
            print(row)

        # Average row
        print("-" * len(header))
        avg_row = f"{'СРЕДНИЙ БАЛЛ':<20}"
        for agent in agents:
            scores = agent_totals[agent]
            if scores:
                avg = sum(scores) / len(scores)
                avg_row += f" | {avg:>8.0%}   "
            else:
                avg_row += f" | {'—':>10}"
        print(avg_row)

        # Token/cost summary
        print()
        print("  СТОИМОСТЬ:")
        for agent in agents:
            if agent in _all_results:
                total_tokens = sum(r.get("tokens", 0) for r in _all_results[agent].values())
                total_cost = sum(r.get("cost", 0) for r in _all_results[agent].values())
                avg_latency = sum(r.get("latency_ms", 0) for r in _all_results[agent].values()) / max(
                    len(_all_results[agent]), 1
                )
                print(f"  {agent:<12}: {total_tokens:>6} tokens, ${total_cost:.4f}, avg latency {avg_latency:.0f}ms")

        print("=" * 90)

    def test_all_agents_above_threshold(self):
        """All agents must achieve >= 70% average score."""
        if not _all_results:
            pytest.skip("No API results collected")

        for agent, blocks in _all_results.items():
            scores = [b["total_score"] for b in blocks.values()]
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            assert avg >= 0.7, (
                f"Агент {agent}: средний балл {avg:.0%} ниже порога 70%. "
                f"Агент недостаточно хорошо понимает документацию блоков!"
            )
