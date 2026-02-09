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
RSI, MACD, EMA, SMA, Bollinger Bands, SuperTrend, Stochastic, CCI, ATR, ADX,
Williams %R, VWAP, Volume MA, OBV

TASK: Create a trading strategy that maximizes Sharpe Ratio while keeping Max Drawdown < 15%.

STRATEGY REQUIREMENTS:
1. Use 2-4 indicators for signal generation
2. Add at least 1 filter condition
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
      "params": {{"period": 14, "overbought": 70, "oversold": 30}},
      "weight": 0.5,
      "condition": "RSI < 30 for long, RSI > 70 for short"
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
    "primary_objective": "sharpe_ratio"
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
  "description": "Mean reversion strategy using RSI oversold/overbought with ADX trend filter to avoid trending markets",
  "signals": [
    {
      "id": "signal_1",
      "type": "RSI",
      "params": {"period": 14, "overbought": 70, "oversold": 30},
      "weight": 0.6,
      "condition": "RSI < 30 for long, RSI > 70 for short"
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
    "long": "RSI < 30 AND price below Bollinger lower band AND ADX < 25",
    "short": "RSI > 70 AND price above Bollinger upper band AND ADX < 25",
    "logic": "signal_1 AND signal_2 AND filter_1"
  },
  "exit_conditions": {
    "take_profit": {"type": "fixed_pct", "value": 1.5, "description": "1.5% take profit"},
    "stop_loss": {"type": "fixed_pct", "value": 1.0, "description": "1% stop loss"}
  },
  "position_management": {"size_pct": 100, "max_positions": 1},
  "optimization_hints": {
    "parameters_to_optimize": ["rsi_period", "rsi_oversold", "rsi_overbought", "bb_period"],
    "ranges": {"rsi_period": [7, 21], "rsi_oversold": [20, 35], "rsi_overbought": [65, 80], "bb_period": [15, 30]},
    "primary_objective": "sharpe_ratio"
  }
}"""

STRATEGY_EXAMPLE_MACD_TREND = """{
  "strategy_name": "MACD Trend Following with EMA Filter",
  "description": "Trend following using MACD crossover confirmed by EMA 200 trend direction",
  "signals": [
    {
      "id": "signal_1",
      "type": "MACD",
      "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
      "weight": 0.7,
      "condition": "MACD line crosses above signal for long, below for short"
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
    "long": "MACD bullish crossover AND EMA 9/21 bullish crossover AND price > EMA 200",
    "short": "MACD bearish crossover AND EMA 9/21 bearish crossover AND price < EMA 200",
    "logic": "signal_1 AND signal_2 AND filter_1"
  },
  "exit_conditions": {
    "take_profit": {"type": "trailing", "value": 2.0, "description": "2% trailing stop"},
    "stop_loss": {"type": "atr_based", "value": 2.0, "description": "2x ATR stop loss"}
  },
  "position_management": {"size_pct": 100, "max_positions": 1},
  "optimization_hints": {
    "parameters_to_optimize": ["macd_fast", "macd_slow", "macd_signal", "ema_fast", "ema_slow"],
    "ranges": {"macd_fast": [8, 16], "macd_slow": [20, 32], "macd_signal": [7, 12]},
    "primary_objective": "sharpe_ratio"
  }
}"""
