"""
Prompt Templates for LLM Trading Strategy Generation.

Structured prompt templates organized by task type:
- strategy_generation: Create new trading strategies
- market_analysis: Analyze market conditions
- optimization_suggestions: Improve existing strategies
- strategy_validation: Validate strategy correctness

Each template supports agent specialization and few-shot examples.
"""

from __future__ import annotations

# =============================================================================
# STRATEGY GENERATION PROMPT
# =============================================================================

STRATEGY_GENERATION_TEMPLATE = """ROLE: You are a professional algorithmic trader with 10+ years of experience.
SPECIALIZATION: {specialization}

CURRENT MARKET CONTEXT:
{symbol} ({timeframe_display}) - Market Regime: {market_regime}
Current Price: ${current_price:,.2f}
Volatility (ATR): {atr_value}
Trend: {trend_direction}
Volume Profile: {volume_profile}
Key Support Levels: {support_levels}
Key Resistance Levels: {resistance_levels}

PLATFORM CONSTRAINTS:
- Position type: {position_type} (long/short/both)
- Leverage: {leverage}x
- Commission: {commission}% per trade
- Initial capital: ${initial_capital:,.0f}
- Data period: {start_date} to {end_date}
- Available timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1D

AVAILABLE INDICATORS:
RSI (Universal: Range filter + Cross level + Legacy modes, 3 outputs: value/long/short),
MACD, EMA, SMA, Bollinger Bands, SuperTrend, Stochastic, CCI, ATR, ADX,
Williams %R, VWAP, Volume MA, OBV

RSI UNIVERSAL NODE (Strategy Builder):
  The RSI block supports 3 combinable signal modes (combined with AND logic):
  1) RANGE filter: use_long_range=true → long signal when RSI > long_rsi_more AND RSI < long_rsi_less.
     long_rsi_more = LOWER bound (min), long_rsi_less = UPPER bound (max). MUST have more < less.
     Example: long_rsi_more=0, long_rsi_less=30 → long when RSI in 0..30 (oversold zone).
     use_short_range=true → short signal when RSI > short_rsi_more AND RSI < short_rsi_less.
     short_rsi_more = LOWER bound (min), short_rsi_less = UPPER bound (max). MUST have more < less.
     Example: short_rsi_more=70, short_rsi_less=100 → short when RSI in 70..100 (overbought zone).
  2) CROSS level: use_cross_level=true → long when RSI crosses UP through cross_long_level,
     short when RSI crosses DOWN through cross_short_level.
     opposite_signal=true swaps cross long/short. use_cross_memory=true + cross_memory_bars=N
     keeps the cross signal active for N bars.
  3) LEGACY (auto-fallback): if no mode enabled but overbought/oversold params exist,
     uses classic RSI < oversold → long, RSI > overbought → short.
  If no mode is enabled and no legacy params → passthrough (always True, RSI acts as value source only).
  Outputs: value (0-100 RSI series), long (boolean), short (boolean).
  All numeric params are optimizable: period(14), long_rsi_more(30), long_rsi_less(70),
  short_rsi_less(70), short_rsi_more(30), cross_long_level(30), cross_short_level(70),
  cross_memory_bars(5).
  OPTIMIZATION RANGES (RSI): Each optimizable param can have a range for grid search.
  Format per param: {{"enabled": true/false, "min": <low>, "max": <high>, "step": <step>}}
  Default ranges from optimizer:
    period: {{low: 5, high: 30, step: 1}}, long_rsi_more: {{low: 10, high: 45, step: 5}},
    long_rsi_less: {{low: 55, high: 90, step: 5}}, short_rsi_less: {{low: 55, high: 90, step: 5}},
    short_rsi_more: {{low: 10, high: 45, step: 5}}, cross_long_level: {{low: 15, high: 45, step: 5}},
    cross_short_level: {{low: 55, high: 85, step: 5}}, cross_memory_bars: {{low: 1, high: 20, step: 1}}.
  Only enabled params with their mode active are included in optimization grid.

MACD UNIVERSAL NODE (Strategy Builder):
  The MACD block supports 2 signal modes (combined with OR logic):
  1) CROSS ZERO: use_macd_cross_zero=true → long when MACD line crosses above level
     (default 0), short when crosses below. opposite_macd_cross_zero=true swaps signals.
     macd_cross_zero_level adjusts the crossing threshold (optimizable).
  2) CROSS SIGNAL: use_macd_cross_signal=true → long when MACD crosses above Signal line,
     short when crosses below. signal_only_if_macd_positive=true filters: long only when
     MACD<0 (mean-reversion), short only when MACD>0.
     opposite_macd_cross_signal=true swaps signals.
  If no mode is enabled → data-only (MACD/Signal/Hist output, long/short always False).
  Signal Memory: enabled by default. disable_signal_memory=true turns off.
  signal_memory_bars(5) controls how many bars cross signals persist.
  Outputs: macd (series), signal (series), hist (series), long (boolean), short (boolean).
  Optimizable params: fast_period(12), slow_period(26), signal_period(9),
  macd_cross_zero_level(0), signal_memory_bars(5).
  OPTIMIZATION RANGES (MACD): Each optimizable param can have a range for grid search.
  Format per param: {{"enabled": true/false, "min": <low>, "max": <high>, "step": <step>}}
  Default ranges from optimizer:
    fast_period: {{low: 8, high: 16, step: 1}}, slow_period: {{low: 20, high: 30, step: 1}},
    signal_period: {{low: 6, high: 12, step: 1}}, macd_cross_zero_level: {{low: -50, high: 50, step: 1}},
    signal_memory_bars: {{low: 1, high: 20, step: 1}}.
  Only params whose mode is enabled are included in optimization grid.
  IMPORTANT: fast_period must be < slow_period.

TASK: Create a trading strategy that maximizes {primary_metric} while keeping Max Drawdown < {max_drawdown_target}%.

STRATEGY REQUIREMENTS:
1. Use {min_indicators}-{max_indicators} indicators for signal generation
2. Add at least {min_filters} filter condition
3. Clear entry/exit conditions
4. Risk management (stop-loss, take-profit)
5. Account for commission ({commission}%) and slippage
6. Be specific with parameter values - avoid generic/default values

RESPONSE FORMAT - Return ONLY valid JSON (no markdown, no explanation):
{{
  "strategy_name": "Unique descriptive name",
  "description": "2-3 sentence description of the strategy logic",
  "signals": [
    {{
      "id": "signal_1",
      "type": "RSI|MACD|EMA_Crossover|SMA_Crossover|Bollinger|SuperTrend|Stochastic|CCI",
      "params": {{"period": 14, "use_cross_level": true, "cross_long_level": 30, "cross_short_level": 70}},
      "weight": 0.5,
      "condition": "RSI crosses up through 30 for long, crosses down through 70 for short"
    }}
  ],
  "filters": [
    {{
      "id": "filter_1",
      "type": "Volume|Trend|Volatility|Time|ADX",
      "params": {{"min_volume_ratio": 1.5}},
      "condition": "Volume > 1.5x average"
    }}
  ],
  "entry_conditions": {{
    "long": "Specific condition for long entry",
    "short": "Specific condition for short entry",
    "logic": "AND|OR combination of signals and filters"
  }},
  "exit_conditions": {{
    "take_profit": {{
      "type": "fixed_pct|trailing|atr_based",
      "value": 2.0,
      "description": "Close at 2% profit"
    }},
    "stop_loss": {{
      "type": "fixed_pct|atr_based",
      "value": 1.5,
      "description": "Stop at 1.5% loss"
    }}
  }},
  "position_management": {{
    "size_pct": 100,
    "max_positions": 1
  }},
  "optimization_hints": {{
    "parameters_to_optimize": ["param1", "param2"],
    "ranges": {{"param1": [5, 20], "param2": [20, 50]}},
    "primary_objective": "sharpe_ratio",
    "optimizationParams": {{
      "param1": {{"enabled": true, "min": 5, "max": 20, "step": 1}},
      "param2": {{"enabled": true, "min": 20, "max": 50, "step": 5}}
    }}
  }}
}}

IMPORTANT: Be specific with parameter values. Return ONLY the JSON object."""


# =============================================================================
# MARKET ANALYSIS PROMPT
# =============================================================================

MARKET_ANALYSIS_TEMPLATE = """You are a senior market analyst. Analyze the following market data
and provide a structured assessment.

MARKET DATA:
Symbol: {symbol}
Timeframe: {timeframe_display}
Period: {start_date} to {end_date}
Data points: {data_points}

PRICE STATISTICS:
- Current price: ${current_price:,.2f}
- Period high: ${period_high:,.2f}
- Period low: ${period_low:,.2f}
- Price change: {price_change_pct:.2f}%

TECHNICAL INDICATORS:
{indicators_summary}

VOLUME:
{volume_summary}

Provide your analysis in the following JSON format:
{{
  "market_regime": "trending_up|trending_down|ranging|volatile|consolidating",
  "trend_strength": "strong|moderate|weak|none",
  "volatility_level": "high|medium|low",
  "key_levels": {{
    "support": [level1, level2],
    "resistance": [level1, level2]
  }},
  "volume_assessment": "increasing|decreasing|stable|divergent",
  "recommended_strategy_type": "trend_following|mean_reversion|breakout|scalping",
  "recommended_timeframe": "1m|5m|15m|1h|4h|1D",
  "risk_assessment": "low|medium|high",
  "confidence": 0.75,
  "reasoning": "Brief explanation of your analysis"
}}"""


# =============================================================================
# OPTIMIZATION SUGGESTIONS PROMPT
# =============================================================================

OPTIMIZATION_SUGGESTIONS_TEMPLATE = """You are an expert in trading strategy optimization.
Based on the backtest results below, suggest specific improvements.

CURRENT STRATEGY:
Name: {strategy_name}
Type: {strategy_type}
Parameters: {strategy_params}

BACKTEST RESULTS:
- Net PnL: ${net_pnl:,.2f}
- Total Return: {total_return_pct:.2f}%
- Sharpe Ratio: {sharpe_ratio:.2f}
- Max Drawdown: {max_drawdown_pct:.2f}%
- Win Rate: {win_rate:.1%}
- Profit Factor: {profit_factor:.2f}
- Total Trades: {total_trades}
- Avg Win: ${avg_win:,.2f}
- Avg Loss: ${avg_loss:,.2f}

IDENTIFIED ISSUES:
{issues}

Provide optimization suggestions in JSON format:
{{
  "overall_assessment": "good|needs_improvement|poor",
  "parameter_adjustments": [
    {{
      "parameter": "param_name",
      "current_value": 14,
      "suggested_value": 21,
      "reason": "Why this change helps"
    }}
  ],
  "filter_suggestions": [
    {{
      "type": "Volume|Trend|ADX",
      "params": {{}},
      "reason": "Why add this filter"
    }}
  ],
  "risk_management_changes": [
    {{
      "change": "Adjust stop-loss from 1.5% to 2%",
      "reason": "Current SL too tight, causing premature exits"
    }}
  ],
  "confidence": 0.7,
  "expected_improvement": "Brief description of expected result"
}}"""


# =============================================================================
# STRATEGY VALIDATION PROMPT
# =============================================================================

STRATEGY_VALIDATION_TEMPLATE = """You are a trading strategy validator. Review the following
strategy for logical errors, edge cases, and potential issues.

STRATEGY:
{strategy_json}

PLATFORM CONSTRAINTS:
- Commission: {commission}% per trade
- Leverage: {leverage}x
- Available indicators: RSI, MACD, EMA, SMA, Bollinger Bands, SuperTrend,
  Stochastic, CCI, ATR, ADX, Williams %R

Validate and return JSON:
{{
  "is_valid": true|false,
  "issues": [
    {{
      "severity": "critical|warning|info",
      "field": "signals[0].params.period",
      "message": "RSI period of 2 is too short, will produce noisy signals"
    }}
  ],
  "suggestions": [
    "Add a trend filter to reduce false signals in ranging markets"
  ],
  "risk_score": 0.3,
  "overall_quality": "high|medium|low"
}}"""


# =============================================================================
# AGENT SPECIALIZATION PROFILES
# =============================================================================

AGENT_SPECIALIZATIONS: dict[str, dict[str, str | list[str]]] = {
    "deepseek": {
        "primary_role": "quantitative_analyst",
        "description": "Senior quantitative analyst at a hedge fund",
        "strengths": ["statistical_analysis", "mean_reversion", "risk_management"],
        "style": "conservative",
        "preferred_indicators": ["RSI", "Bollinger", "ATR", "ADX"],
        "preferred_timeframes": ["4h", "1D"],
    },
    "qwen": {
        "primary_role": "technical_analyst",
        "description": "Expert technical analyst with pattern recognition focus",
        "strengths": ["pattern_recognition", "momentum", "market_structure"],
        "style": "moderate",
        "preferred_indicators": ["MACD", "EMA", "SuperTrend", "Stochastic"],
        "preferred_timeframes": ["15m", "1h"],
    },
    "perplexity": {
        "primary_role": "market_researcher",
        "description": "Market researcher with access to latest analysis",
        "strengths": ["sentiment_analysis", "news_impact", "trend_detection"],
        "style": "adaptive",
        "preferred_indicators": ["SMA", "VWAP", "OBV", "Volume"],
        "preferred_timeframes": ["1h", "4h"],
    },
}

# =============================================================================
# FEW-SHOT EXAMPLES
# =============================================================================

STRATEGY_EXAMPLE_RSI_MEAN_REVERSION = """{
  "strategy_name": "RSI Mean Reversion with ADX Filter",
  "description": "Mean reversion strategy using RSI cross level signals with range filter and ADX trend filter to avoid trending markets",
  "signals": [
    {
      "id": "signal_1",
      "type": "RSI",
      "params": {
        "period": 14,
        "use_long_range": true, "long_rsi_more": 10, "long_rsi_less": 40,
        "use_short_range": true, "short_rsi_less": 90, "short_rsi_more": 60,
        "use_cross_level": true, "cross_long_level": 30, "cross_short_level": 70,
        "use_cross_memory": true, "cross_memory_bars": 3
      },
      "weight": 0.6,
      "condition": "RSI crosses up through 30 while in range [10,40] for long; RSI crosses down through 70 while in range [60,90] for short"
    },
    {
      "id": "signal_2",
      "type": "Bollinger",
      "params": {"period": 20, "std_dev": 2.0},
      "weight": 0.4,
      "condition": "Price below lower band for long, above upper band for short"
    }
  ],
  "filters": [
    {
      "id": "filter_1",
      "type": "ADX",
      "params": {"period": 14, "max_value": 25},
      "condition": "ADX < 25 (ranging market only)"
    }
  ],
  "entry_conditions": {
    "long": "RSI crosses up through 30 while in range [10,40] AND price below Bollinger lower band AND ADX < 25",
    "short": "RSI crosses down through 70 while in range [60,90] AND price above Bollinger upper band AND ADX < 25",
    "logic": "signal_1 AND signal_2 AND filter_1"
  },
  "exit_conditions": {
    "take_profit": {"type": "fixed_pct", "value": 1.5, "description": "1.5% take profit"},
    "stop_loss": {"type": "fixed_pct", "value": 1.0, "description": "1% stop loss"}
  },
  "position_management": {"size_pct": 100, "max_positions": 1},
  "optimization_hints": {
    "parameters_to_optimize": ["rsi_period", "cross_long_level", "cross_short_level", "long_rsi_more", "long_rsi_less", "cross_memory_bars", "bb_period"],
    "ranges": {"rsi_period": [7, 21], "cross_long_level": [20, 40], "cross_short_level": [60, 80], "long_rsi_more": [5, 25], "long_rsi_less": [35, 55], "cross_memory_bars": [1, 10], "bb_period": [15, 30]},
    "primary_objective": "sharpe_ratio",
    "optimizationParams": {
      "period": {"enabled": true, "min": 7, "max": 21, "step": 1},
      "cross_long_level": {"enabled": true, "min": 20, "max": 40, "step": 5},
      "cross_short_level": {"enabled": true, "min": 60, "max": 80, "step": 5},
      "long_rsi_more": {"enabled": true, "min": 5, "max": 25, "step": 5},
      "long_rsi_less": {"enabled": true, "min": 35, "max": 55, "step": 5},
      "cross_memory_bars": {"enabled": true, "min": 1, "max": 10, "step": 1}
    }
  }
}"""

STRATEGY_EXAMPLE_MACD_TREND = """{
  "strategy_name": "MACD Trend Following with EMA Filter",
  "description": "Trend following using MACD signal-line crossover with zero-line confirmation and EMA 200 trend filter",
  "signals": [
    {
      "id": "signal_1",
      "type": "MACD",
      "params": {
        "fast_period": 12, "slow_period": 26, "signal_period": 9,
        "use_macd_cross_signal": true,
        "signal_only_if_macd_positive": true,
        "use_macd_cross_zero": true,
        "macd_cross_zero_level": 0,
        "disable_signal_memory": false,
        "signal_memory_bars": 3
      },
      "weight": 0.7,
      "condition": "MACD crosses Signal line (filtered: long only when MACD<0) OR MACD crosses zero line"
    },
    {
      "id": "signal_2",
      "type": "EMA_Crossover",
      "params": {"fast_period": 9, "slow_period": 21},
      "weight": 0.3,
      "condition": "Fast EMA crosses above slow EMA for long, below for short"
    }
  ],
  "filters": [
    {
      "id": "filter_1",
      "type": "Trend",
      "params": {"ema_period": 200},
      "condition": "Price above EMA 200 for long trades, below for short trades"
    }
  ],
  "entry_conditions": {
    "long": "MACD crosses Signal line while MACD<0 AND price > EMA 200",
    "short": "MACD crosses below Signal line while MACD>0 AND price < EMA 200",
    "logic": "signal_1 AND filter_1"
  },
  "exit_conditions": {
    "take_profit": {"type": "trailing", "value": 2.0, "description": "2% trailing stop"},
    "stop_loss": {"type": "atr_based", "value": 2.0, "description": "2x ATR stop loss"}
  },
  "position_management": {"size_pct": 100, "max_positions": 1},
  "optimization_hints": {
    "parameters_to_optimize": ["macd_fast_period", "macd_slow_period", "macd_signal_period", "macd_cross_zero_level", "signal_memory_bars", "ema_fast", "ema_slow"],
    "ranges": {"macd_fast_period": [8, 16], "macd_slow_period": [20, 32], "macd_signal_period": [7, 12], "macd_cross_zero_level": [-10, 10], "signal_memory_bars": [1, 10]},
    "primary_objective": "sharpe_ratio",
    "optimizationParams": {
      "fast_period": {"enabled": true, "min": 8, "max": 16, "step": 1},
      "slow_period": {"enabled": true, "min": 20, "max": 32, "step": 1},
      "signal_period": {"enabled": true, "min": 7, "max": 12, "step": 1},
      "macd_cross_zero_level": {"enabled": true, "min": -10, "max": 10, "step": 1},
      "signal_memory_bars": {"enabled": true, "min": 1, "max": 10, "step": 1}
    }
  }
}"""


# =============================================================================
# HIERARCHICAL MEMORY SYSTEM DOCUMENTATION
# =============================================================================

MEMORY_SYSTEM_DOCS = """
=== HIERARCHICAL MEMORY SYSTEM ===

The agent system uses a 4-tier hierarchical memory inspired by human cognition.

=== MEMORY TYPES (4 tiers) ===
1. WORKING   — Current task context. TTL: 5 minutes. Max: 10 items. Priority: 1 (lowest).
   Use for: current conversation state, active task details, temporary calculations.
   Example: "User asked to optimize RSI parameters for BTCUSDT"

2. EPISODIC  — Session experiences. TTL: 7 days. Max: 1000 items. Priority: 2.
   Use for: conversation history, backtest results, user requests, agent actions.
   Example: "Backtest #42 on BTCUSDT RSI strategy returned 12.5% with Sharpe 1.8"

3. SEMANTIC  — Long-term knowledge. TTL: 365 days. Max: 10000 items. Priority: 3.
   Use for: trading facts, indicator knowledge, learned patterns, market rules.
   Example: "RSI above 70 indicates overbought, below 30 indicates oversold"

4. PROCEDURAL — Skills and patterns. TTL: 10 years (permanent). Max: 500 items. Priority: 4 (highest).
   Use for: learned procedures, successful strategy templates, optimization workflows.
   Example: "For mean-reversion: use RSI + Bollinger Bands, SL=1.5%, TP=3%"

=== MEMORY OPERATIONS ===
- store(content, memory_type, importance=0.5, tags=[], metadata={})
  → Stores content in the specified tier. importance: 0.0-1.0 (higher = more retained).
    Tags enable filtering. Returns MemoryItem with generated ID.

- recall(query, memory_type=None, top_k=5, min_importance=0.0, tags=[], use_semantic=True)
  → Searches memories by text relevance + semantic similarity.
    memory_type=None searches ALL tiers. Returns list of MemoryItems.

- get(item_id) → Retrieve specific memory by ID. Returns MemoryItem or None.

- delete(item_id) → Remove specific memory. Returns True/False.

- consolidate() → Moves important memories UP the hierarchy:
  working→episodic (if importance >= 0.7),
  episodic→semantic (if 3+ items share tags and avg importance >= 0.6).
  Like "sleep" — strengthens important memories.

- forget() → Intelligent cleanup:
  Removes expired items (TTL exceeded).
  Applies importance decay (0.1% per hour since last access).
  Removes items with importance < 0.1 and access_count < 2.

=== IMPORTANCE GUIDELINES ===
- 0.9-1.0: Critical — strategy parameters that led to profitable backtests
- 0.7-0.8: High — user preferences, successful patterns, key decisions
- 0.5-0.6: Normal — routine observations, standard analysis results
- 0.3-0.4: Low — temporary context, intermediate calculations
- 0.1-0.2: Minimal — noise, superseded information

=== CONSOLIDATION THRESHOLDS ===
- Working → Episodic: importance >= 0.7
- Episodic → Semantic: 3+ items share same tag, avg importance >= 0.6
- Procedural: identified repeated action patterns, importance >= 0.8

=== TRADING CONTEXT USAGE ===
When starting a new task:
1. recall() relevant memories from semantic/procedural tiers
2. Load previous results from episodic memory
3. Store current task context in working memory

During analysis:
1. Store intermediate results in working memory (importance=0.3-0.5)
2. Store significant findings in episodic memory (importance=0.6-0.8)
3. Store discovered patterns in semantic memory (importance=0.7-0.9)

After completing a task:
1. Store final results + conclusions in episodic memory
2. If a new pattern was discovered → store in semantic memory
3. If a reusable workflow was identified → store in procedural memory
4. Run consolidate() to promote important working memories

=== API ENDPOINTS ===
POST /api/v1/agents/memory/store     — Store content in memory
POST /api/v1/agents/memory/recall    — Search memories by query
GET  /api/v1/agents/memory/stats     — Get memory statistics
POST /api/v1/agents/memory/consolidate — Run consolidation
"""
