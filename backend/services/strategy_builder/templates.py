"""
Strategy Templates

Pre-built strategy templates that users can use as starting points.

Includes:
- Popular trading strategies (RSI, MACD, Bollinger, etc.)
- Risk management templates
- Multi-indicator templates
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .builder import (
    BlockType,
    StrategyBuilder,
    StrategyGraph,
)

logger = logging.getLogger(__name__)


class TemplateCategory(Enum):
    """Categories of strategy templates"""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    SWING_TRADING = "swing_trading"
    MULTI_INDICATOR = "multi_indicator"
    RISK_MANAGEMENT = "risk_management"
    BEGINNER = "beginner"
    ADVANCED = "advanced"


@dataclass
class StrategyTemplate:
    """
    Pre-built strategy template

    Provides a starting point for building strategies.
    """

    id: str
    name: str
    category: TemplateCategory
    description: str
    tags: list[str] = field(default_factory=list)
    difficulty: str = "beginner"  # beginner, intermediate, advanced
    timeframes: list[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    author: str = "System"
    version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Template data
    graph_data: dict[str, Any] = field(default_factory=dict)

    # Documentation
    how_it_works: str = ""
    parameters_description: str = ""
    recommended_markets: list[str] = field(default_factory=list)
    expected_performance: str = ""
    risks: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "timeframes": self.timeframes,
            "author": self.author,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "graph_data": self.graph_data,
            "how_it_works": self.how_it_works,
            "parameters_description": self.parameters_description,
            "recommended_markets": self.recommended_markets,
            "expected_performance": self.expected_performance,
            "risks": self.risks,
        }


class StrategyTemplateManager:
    """
    Manages strategy templates

    Provides CRUD operations and template instantiation.
    """

    def __init__(self):
        self.templates: dict[str, StrategyTemplate] = {}
        self.builder = StrategyBuilder()

        # Load built-in templates
        self._load_builtin_templates()

    def _load_builtin_templates(self) -> None:
        """Load built-in strategy templates"""
        # RSI Overbought/Oversold
        self.templates["rsi_basic"] = self._create_rsi_template()

        # MACD Crossover
        self.templates["macd_crossover"] = self._create_macd_template()

        # Bollinger Band Bounce
        self.templates["bb_bounce"] = self._create_bollinger_template()

        # EMA Crossover
        self.templates["ema_crossover"] = self._create_ema_crossover_template()

        # Triple EMA
        self.templates["triple_ema"] = self._create_triple_ema_template()

        # RSI + MACD Combo
        self.templates["rsi_macd_combo"] = self._create_rsi_macd_template()

        # Trend Following with ATR
        self.templates["trend_atr"] = self._create_trend_atr_template()

        # Breakout Strategy
        self.templates["breakout"] = self._create_breakout_template()

        # Mean Reversion
        self.templates["mean_reversion"] = self._create_mean_reversion_template()

        # Scalping Strategy
        self.templates["scalping"] = self._create_scalping_template()

    def get_template(self, template_id: str) -> StrategyTemplate | None:
        """Get a template by ID"""
        return self.templates.get(template_id)

    def list_templates(
        self,
        category: TemplateCategory | None = None,
        difficulty: str | None = None,
        tags: list[str] | None = None,
    ) -> list[StrategyTemplate]:
        """List templates with optional filtering"""
        result = list(self.templates.values())

        if category:
            result = [t for t in result if t.category == category]

        if difficulty:
            result = [t for t in result if t.difficulty == difficulty]

        if tags:
            result = [t for t in result if any(tag in t.tags for tag in tags)]

        return result

    def instantiate_template(
        self,
        template_id: str,
        name: str | None = None,
        symbols: list[str] | None = None,
        timeframe: str | None = None,
    ) -> StrategyGraph | None:
        """
        Create a new strategy from a template

        Args:
            template_id: Template to instantiate
            name: Name for the new strategy
            symbols: Trading symbols
            timeframe: Timeframe

        Returns:
            New StrategyGraph or None if template not found
        """
        template = self.get_template(template_id)
        if not template:
            return None

        # Create graph from template data
        graph_data = template.graph_data.copy()
        graph_data["id"] = str(uuid.uuid4())
        graph_data["name"] = name or f"{template.name} Strategy"
        graph_data["created_at"] = datetime.now(UTC).isoformat()
        graph_data["updated_at"] = datetime.now(UTC).isoformat()

        if symbols:
            graph_data["symbols"] = symbols
        if timeframe:
            graph_data["timeframe"] = timeframe

        return StrategyGraph.from_dict(graph_data)

    def add_template(self, template: StrategyTemplate) -> None:
        """Add a custom template"""
        self.templates[template.id] = template

    def remove_template(self, template_id: str) -> bool:
        """Remove a template (only custom templates)"""
        if template_id in self.templates:
            del self.templates[template_id]
            return True
        return False

    def create_template_from_graph(
        self,
        graph: StrategyGraph,
        name: str,
        category: TemplateCategory,
        description: str,
        **kwargs,
    ) -> StrategyTemplate:
        """Create a new template from an existing strategy graph"""
        template = StrategyTemplate(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            description=description,
            graph_data=graph.to_dict(),
            **kwargs,
        )
        self.templates[template.id] = template
        return template

    # === Built-in Template Creators ===

    def _create_rsi_template(self) -> StrategyTemplate:
        """Create RSI overbought/oversold template"""
        graph = self.builder.create_strategy(
            name="RSI Strategy",
            description="Buy when RSI is oversold, sell when overbought",
            timeframe="1h",
        )

        # Add blocks
        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)
        rsi = self.builder.add_block(
            graph, BlockType.INDICATOR_RSI, x=300, y=200, parameters={"period": 14}
        )

        # Oversold condition (RSI < 30)
        oversold = self.builder.add_block(
            graph,
            BlockType.CONDITION_THRESHOLD,
            x=500,
            y=100,
            parameters={"threshold": 30},
        )

        # Overbought condition (RSI > 70)
        overbought = self.builder.add_block(
            graph,
            BlockType.CONDITION_THRESHOLD,
            x=500,
            y=300,
            parameters={"threshold": 70},
        )

        buy = self.builder.add_block(
            graph,
            BlockType.ACTION_BUY,
            x=700,
            y=100,
            parameters={"size_pct": 100, "order_type": "market"},
        )

        sell = self.builder.add_block(
            graph,
            BlockType.ACTION_SELL,
            x=700,
            y=300,
            parameters={"size_pct": 100, "order_type": "market"},
        )

        # Connect blocks
        self.builder.connect(graph, candles.id, "close", rsi.id, "source")
        self.builder.connect(graph, rsi.id, "rsi", oversold.id, "value")
        self.builder.connect(graph, rsi.id, "rsi", overbought.id, "value")
        self.builder.connect(graph, oversold.id, "below", buy.id, "trigger")
        self.builder.connect(graph, overbought.id, "above", sell.id, "trigger")

        return StrategyTemplate(
            id="rsi_basic",
            name="RSI Overbought/Oversold",
            category=TemplateCategory.MEAN_REVERSION,
            description="Classic RSI strategy that buys when oversold (RSI < 30) and sells when overbought (RSI > 70)",
            tags=["rsi", "momentum", "mean-reversion", "beginner"],
            difficulty="beginner",
            timeframes=["1h", "4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            The RSI (Relative Strength Index) measures the speed and magnitude of price changes.

            - RSI below 30: Asset is oversold, potential buying opportunity
            - RSI above 70: Asset is overbought, potential selling opportunity

            This strategy automatically triggers buy signals when RSI drops below 30
            and sell signals when RSI rises above 70.
            """,
            parameters_description="""
            - RSI Period: Number of periods for RSI calculation (default: 14)
            - Oversold Level: RSI threshold for buy signals (default: 30)
            - Overbought Level: RSI threshold for sell signals (default: 70)
            """,
            recommended_markets=["BTCUSDT", "ETHUSDT", "Major crypto pairs"],
            expected_performance="Works best in ranging markets with clear overbought/oversold conditions",
            risks="May generate false signals in strong trending markets",
        )

    def _create_macd_template(self) -> StrategyTemplate:
        """Create MACD crossover template"""
        graph = self.builder.create_strategy(
            name="MACD Crossover",
            description="Trade MACD line crossing signal line",
            timeframe="4h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)
        macd = self.builder.add_block(
            graph,
            BlockType.INDICATOR_MACD,
            x=300,
            y=200,
            parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        )

        cross = self.builder.add_block(graph, BlockType.CONDITION_CROSS, x=500, y=200)

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=100)
        sell = self.builder.add_block(graph, BlockType.ACTION_SELL, x=700, y=300)

        self.builder.connect(graph, candles.id, "close", macd.id, "source")
        self.builder.connect(graph, macd.id, "macd_line", cross.id, "fast")
        self.builder.connect(graph, macd.id, "signal_line", cross.id, "slow")
        self.builder.connect(graph, cross.id, "cross_above", buy.id, "trigger")
        self.builder.connect(graph, cross.id, "cross_below", sell.id, "trigger")

        return StrategyTemplate(
            id="macd_crossover",
            name="MACD Crossover",
            category=TemplateCategory.TREND_FOLLOWING,
            description="Buy when MACD line crosses above signal line, sell when it crosses below",
            tags=["macd", "trend", "crossover", "intermediate"],
            difficulty="intermediate",
            timeframes=["4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            MACD (Moving Average Convergence Divergence) shows the relationship between two EMAs.

            - MACD line crosses above signal line: Bullish signal
            - MACD line crosses below signal line: Bearish signal

            The strategy generates trade signals on these crossovers.
            """,
            parameters_description="""
            - Fast Period: Fast EMA period (default: 12)
            - Slow Period: Slow EMA period (default: 26)
            - Signal Period: Signal line EMA period (default: 9)
            """,
            recommended_markets=["All crypto pairs", "Works well on higher timeframes"],
            expected_performance="Captures medium to long-term trends effectively",
            risks="Lagging indicator, may miss fast moves",
        )

    def _create_bollinger_template(self) -> StrategyTemplate:
        """Create Bollinger Bands bounce template"""
        graph = self.builder.create_strategy(
            name="Bollinger Band Bounce",
            description="Trade bounces off Bollinger Bands",
            timeframe="1h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)
        bb = self.builder.add_block(
            graph,
            BlockType.INDICATOR_BOLLINGER,
            x=300,
            y=200,
            parameters={"period": 20, "std_dev": 2.0},
        )

        # Price below lower band
        lower_cond = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=100,
            parameters={"operator": "<"},
        )

        # Price above upper band
        upper_cond = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=300,
            parameters={"operator": ">"},
        )

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=100)
        sell = self.builder.add_block(graph, BlockType.ACTION_SELL, x=700, y=300)

        self.builder.connect(graph, candles.id, "close", bb.id, "source")
        self.builder.connect(graph, candles.id, "close", lower_cond.id, "left")
        self.builder.connect(graph, bb.id, "lower", lower_cond.id, "right")
        self.builder.connect(graph, candles.id, "close", upper_cond.id, "left")
        self.builder.connect(graph, bb.id, "upper", upper_cond.id, "right")
        self.builder.connect(graph, lower_cond.id, "result", buy.id, "trigger")
        self.builder.connect(graph, upper_cond.id, "result", sell.id, "trigger")

        return StrategyTemplate(
            id="bb_bounce",
            name="Bollinger Band Bounce",
            category=TemplateCategory.MEAN_REVERSION,
            description="Buy when price touches lower band, sell when it touches upper band",
            tags=["bollinger", "volatility", "mean-reversion", "intermediate"],
            difficulty="intermediate",
            timeframes=["15m", "1h", "4h"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Bollinger Bands create a channel around price using standard deviations.

            - Price at lower band: Potential oversold, buy opportunity
            - Price at upper band: Potential overbought, sell opportunity

            Works best in ranging markets where price oscillates between bands.
            """,
            parameters_description="""
            - Period: Moving average period (default: 20)
            - Standard Deviations: Band width multiplier (default: 2.0)
            """,
            recommended_markets=["Ranging crypto pairs", "Low volatility periods"],
            expected_performance="Profitable in sideways markets",
            risks="Losses during breakout/trending periods",
        )

    def _create_ema_crossover_template(self) -> StrategyTemplate:
        """Create EMA crossover template"""
        graph = self.builder.create_strategy(
            name="EMA Crossover", description="Trade EMA crossovers", timeframe="4h"
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        fast_ema = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=100, parameters={"period": 9}
        )
        slow_ema = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=300, parameters={"period": 21}
        )

        cross = self.builder.add_block(graph, BlockType.CONDITION_CROSS, x=500, y=200)

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=100)
        sell = self.builder.add_block(graph, BlockType.ACTION_SELL, x=700, y=300)

        self.builder.connect(graph, candles.id, "close", fast_ema.id, "source")
        self.builder.connect(graph, candles.id, "close", slow_ema.id, "source")
        self.builder.connect(graph, fast_ema.id, "ema", cross.id, "fast")
        self.builder.connect(graph, slow_ema.id, "ema", cross.id, "slow")
        self.builder.connect(graph, cross.id, "cross_above", buy.id, "trigger")
        self.builder.connect(graph, cross.id, "cross_below", sell.id, "trigger")

        return StrategyTemplate(
            id="ema_crossover",
            name="EMA Crossover (9/21)",
            category=TemplateCategory.TREND_FOLLOWING,
            description="Classic golden/death cross strategy using 9 and 21 period EMAs",
            tags=["ema", "trend", "crossover", "beginner"],
            difficulty="beginner",
            timeframes=["1h", "4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Uses two Exponential Moving Averages to identify trend direction.

            - Fast EMA crosses above slow EMA: Bullish (Golden Cross)
            - Fast EMA crosses below slow EMA: Bearish (Death Cross)
            """,
            parameters_description="""
            - Fast EMA Period: Short-term trend (default: 9)
            - Slow EMA Period: Long-term trend (default: 21)
            """,
            recommended_markets=["All crypto pairs"],
            expected_performance="Good for capturing medium-term trends",
            risks="Whipsaws in ranging markets",
        )

    def _create_triple_ema_template(self) -> StrategyTemplate:
        """Create triple EMA template"""
        graph = self.builder.create_strategy(
            name="Triple EMA",
            description="Three EMA confluence strategy",
            timeframe="4h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        ema_fast = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=100, parameters={"period": 8}
        )
        ema_mid = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=200, parameters={"period": 21}
        )
        ema_slow = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=300, parameters={"period": 55}
        )

        # Fast > Mid
        cond1 = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=100,
            parameters={"operator": ">"},
        )
        # Mid > Slow
        cond2 = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=200,
            parameters={"operator": ">"},
        )

        # All bullish
        and_cond = self.builder.add_block(graph, BlockType.CONDITION_AND, x=650, y=150)

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=800, y=150)

        self.builder.connect(graph, candles.id, "close", ema_fast.id, "source")
        self.builder.connect(graph, candles.id, "close", ema_mid.id, "source")
        self.builder.connect(graph, candles.id, "close", ema_slow.id, "source")
        self.builder.connect(graph, ema_fast.id, "ema", cond1.id, "left")
        self.builder.connect(graph, ema_mid.id, "ema", cond1.id, "right")
        self.builder.connect(graph, ema_mid.id, "ema", cond2.id, "left")
        self.builder.connect(graph, ema_slow.id, "ema", cond2.id, "right")
        self.builder.connect(graph, cond1.id, "result", and_cond.id, "condition1")
        self.builder.connect(graph, cond2.id, "result", and_cond.id, "condition2")
        self.builder.connect(graph, and_cond.id, "result", buy.id, "trigger")

        return StrategyTemplate(
            id="triple_ema",
            name="Triple EMA Stack",
            category=TemplateCategory.TREND_FOLLOWING,
            description="Buy when EMAs are stacked bullishly (8 > 21 > 55)",
            tags=["ema", "trend", "confluence", "intermediate"],
            difficulty="intermediate",
            timeframes=["4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Uses three EMAs to confirm trend strength.

            - Bullish Stack: 8 EMA > 21 EMA > 55 EMA
            - Bearish Stack: 8 EMA < 21 EMA < 55 EMA

            Only trades in the direction of the confirmed trend.
            """,
            parameters_description="""
            - Fast EMA: 8 periods
            - Medium EMA: 21 periods
            - Slow EMA: 55 periods
            """,
            recommended_markets=["Trending crypto pairs"],
            expected_performance="High win rate in trending markets",
            risks="Few signals in ranging markets",
        )

    def _create_rsi_macd_template(self) -> StrategyTemplate:
        """Create RSI + MACD combo template"""
        graph = self.builder.create_strategy(
            name="RSI + MACD Combo",
            description="Multi-indicator confirmation strategy",
            timeframe="4h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        rsi = self.builder.add_block(
            graph, BlockType.INDICATOR_RSI, x=300, y=100, parameters={"period": 14}
        )
        macd = self.builder.add_block(
            graph,
            BlockType.INDICATOR_MACD,
            x=300,
            y=300,
            parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        )

        # RSI < 40 (bullish)
        rsi_cond = self.builder.add_block(
            graph,
            BlockType.CONDITION_THRESHOLD,
            x=500,
            y=100,
            parameters={"threshold": 40},
        )

        # MACD crossover
        macd_cross = self.builder.add_block(
            graph, BlockType.CONDITION_CROSS, x=500, y=300
        )

        # Both conditions
        and_cond = self.builder.add_block(graph, BlockType.CONDITION_AND, x=700, y=200)

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=900, y=200)

        self.builder.connect(graph, candles.id, "close", rsi.id, "source")
        self.builder.connect(graph, candles.id, "close", macd.id, "source")
        self.builder.connect(graph, rsi.id, "rsi", rsi_cond.id, "value")
        self.builder.connect(graph, macd.id, "macd_line", macd_cross.id, "fast")
        self.builder.connect(graph, macd.id, "signal_line", macd_cross.id, "slow")
        self.builder.connect(graph, rsi_cond.id, "below", and_cond.id, "condition1")
        self.builder.connect(
            graph, macd_cross.id, "cross_above", and_cond.id, "condition2"
        )
        self.builder.connect(graph, and_cond.id, "result", buy.id, "trigger")

        return StrategyTemplate(
            id="rsi_macd_combo",
            name="RSI + MACD Confluence",
            category=TemplateCategory.MULTI_INDICATOR,
            description="Buy when RSI is low AND MACD crosses bullish",
            tags=["rsi", "macd", "confluence", "advanced"],
            difficulty="advanced",
            timeframes=["4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Combines RSI and MACD for higher probability trades.

            Buy signal requires:
            1. RSI below 40 (oversold zone)
            2. MACD bullish crossover

            Both conditions must be true simultaneously.
            """,
            parameters_description="""
            - RSI Period: 14
            - RSI Threshold: 40
            - MACD Fast/Slow/Signal: 12/26/9
            """,
            recommended_markets=["Major crypto pairs"],
            expected_performance="High win rate due to confirmation",
            risks="Fewer trading opportunities",
        )

    def _create_trend_atr_template(self) -> StrategyTemplate:
        """Create trend following with ATR stop template"""
        graph = self.builder.create_strategy(
            name="Trend + ATR Stop",
            description="Trend following with dynamic ATR-based stops",
            timeframe="4h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        ema = self.builder.add_block(
            graph, BlockType.INDICATOR_EMA, x=300, y=100, parameters={"period": 50}
        )
        atr = self.builder.add_block(
            graph, BlockType.INDICATOR_ATR, x=300, y=300, parameters={"period": 14}
        )

        # Price > EMA
        trend_cond = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=100,
            parameters={"operator": ">"},
        )

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=100)
        stop_loss = self.builder.add_block(
            graph,
            BlockType.ACTION_SET_STOP_LOSS,
            x=700,
            y=300,
            parameters={"stop_type": "atr", "value": 2.0},
        )

        self.builder.connect(graph, candles.id, "close", ema.id, "source")
        self.builder.connect(graph, candles.id, "high", atr.id, "high")
        self.builder.connect(graph, candles.id, "low", atr.id, "low")
        self.builder.connect(graph, candles.id, "close", atr.id, "close")
        self.builder.connect(graph, candles.id, "close", trend_cond.id, "left")
        self.builder.connect(graph, ema.id, "ema", trend_cond.id, "right")
        self.builder.connect(graph, trend_cond.id, "result", buy.id, "trigger")
        self.builder.connect(graph, trend_cond.id, "result", stop_loss.id, "trigger")

        return StrategyTemplate(
            id="trend_atr",
            name="Trend Following + ATR Stop",
            category=TemplateCategory.TREND_FOLLOWING,
            description="Trend trades with volatility-adjusted stop losses",
            tags=["trend", "atr", "stop-loss", "risk-management"],
            difficulty="intermediate",
            timeframes=["4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Combines trend detection with dynamic risk management.

            - Buy when price is above 50 EMA (uptrend)
            - Set stop loss at 2x ATR below entry
            - Stop adjusts to market volatility
            """,
            parameters_description="""
            - EMA Period: 50
            - ATR Period: 14
            - Stop Loss: 2x ATR
            """,
            recommended_markets=["All crypto pairs"],
            expected_performance="Good risk-adjusted returns",
            risks="Stop may be hit in volatile markets",
        )

    def _create_breakout_template(self) -> StrategyTemplate:
        """Create breakout strategy template"""
        graph = self.builder.create_strategy(
            name="Donchian Breakout",
            description="Trade breakouts from price channels",
            timeframe="1d",
        )

        # Simplified breakout template
        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        # Use custom indicator for Donchian (or Bollinger as proxy)
        bb = self.builder.add_block(
            graph,
            BlockType.INDICATOR_BOLLINGER,
            x=300,
            y=200,
            parameters={"period": 20, "std_dev": 2.0},
        )

        # Price breaks upper band
        break_up = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=100,
            parameters={"operator": ">"},
        )

        # Volume filter
        volume_filter = self.builder.add_block(
            graph,
            BlockType.FILTER_VOLUME,
            x=700,
            y=100,
            parameters={"min_volume_ratio": 1.5, "lookback": 20},
        )

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=900, y=100)

        self.builder.connect(graph, candles.id, "close", bb.id, "source")
        self.builder.connect(graph, candles.id, "close", break_up.id, "left")
        self.builder.connect(graph, bb.id, "upper", break_up.id, "right")
        self.builder.connect(graph, break_up.id, "result", volume_filter.id, "signal")
        self.builder.connect(graph, candles.id, "volume", volume_filter.id, "volume")
        self.builder.connect(graph, volume_filter.id, "filtered", buy.id, "trigger")

        return StrategyTemplate(
            id="breakout",
            name="Volume Breakout",
            category=TemplateCategory.BREAKOUT,
            description="Trade breakouts confirmed by volume",
            tags=["breakout", "volume", "momentum", "intermediate"],
            difficulty="intermediate",
            timeframes=["4h", "1d"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Trades breakouts from price channels with volume confirmation.

            - Buy when price breaks above upper band
            - Volume must be 1.5x average volume
            - Higher volume = stronger breakout
            """,
            parameters_description="""
            - Channel Period: 20
            - Volume Multiplier: 1.5x average
            """,
            recommended_markets=["All crypto pairs"],
            expected_performance="Captures strong breakout moves",
            risks="False breakouts in low-volume conditions",
        )

    def _create_mean_reversion_template(self) -> StrategyTemplate:
        """Create mean reversion template"""
        graph = self.builder.create_strategy(
            name="Mean Reversion",
            description="Trade pullbacks to moving average",
            timeframe="1h",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        sma = self.builder.add_block(
            graph, BlockType.INDICATOR_SMA, x=300, y=100, parameters={"period": 20}
        )
        bb = self.builder.add_block(
            graph,
            BlockType.INDICATOR_BOLLINGER,
            x=300,
            y=300,
            parameters={"period": 20, "std_dev": 2.0},
        )

        # Price near lower band
        oversold = self.builder.add_block(
            graph,
            BlockType.CONDITION_COMPARE,
            x=500,
            y=200,
            parameters={"operator": "<"},
        )

        buy = self.builder.add_block(graph, BlockType.ACTION_BUY, x=700, y=200)
        tp = self.builder.add_block(
            graph,
            BlockType.ACTION_SET_TAKE_PROFIT,
            x=900,
            y=200,
            parameters={"tp_type": "percent", "value": 2.0},
        )

        self.builder.connect(graph, candles.id, "close", sma.id, "source")
        self.builder.connect(graph, candles.id, "close", bb.id, "source")
        self.builder.connect(graph, candles.id, "close", oversold.id, "left")
        self.builder.connect(graph, bb.id, "lower", oversold.id, "right")
        self.builder.connect(graph, oversold.id, "result", buy.id, "trigger")
        self.builder.connect(graph, oversold.id, "result", tp.id, "trigger")

        return StrategyTemplate(
            id="mean_reversion",
            name="Mean Reversion",
            category=TemplateCategory.MEAN_REVERSION,
            description="Buy dips, target mean (moving average)",
            tags=["mean-reversion", "dip-buying", "beginner"],
            difficulty="beginner",
            timeframes=["15m", "1h", "4h"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Buys when price deviates significantly from average.

            - Buy when price touches lower Bollinger Band
            - Take profit at 2% gain or return to mean
            - Works in ranging markets
            """,
            parameters_description="""
            - SMA Period: 20
            - Bollinger Bands: 20 period, 2 std dev
            - Take Profit: 2%
            """,
            recommended_markets=["Ranging crypto pairs"],
            expected_performance="Consistent in sideways markets",
            risks="Trend continuation may cause losses",
        )

    def _create_scalping_template(self) -> StrategyTemplate:
        """Create scalping template"""
        graph = self.builder.create_strategy(
            name="Scalping RSI",
            description="Quick trades on RSI extremes",
            timeframe="5m",
        )

        candles = self.builder.add_block(graph, BlockType.CANDLE_DATA, x=100, y=200)

        rsi = self.builder.add_block(
            graph, BlockType.INDICATOR_RSI, x=300, y=200, parameters={"period": 7}
        )

        # RSI < 20 (very oversold)
        oversold = self.builder.add_block(
            graph,
            BlockType.CONDITION_THRESHOLD,
            x=500,
            y=100,
            parameters={"threshold": 20},
        )

        # RSI > 80 (very overbought)
        overbought = self.builder.add_block(
            graph,
            BlockType.CONDITION_THRESHOLD,
            x=500,
            y=300,
            parameters={"threshold": 80},
        )

        buy = self.builder.add_block(
            graph, BlockType.ACTION_BUY, x=700, y=100, parameters={"size_pct": 50}
        )
        sell = self.builder.add_block(
            graph, BlockType.ACTION_SELL, x=700, y=300, parameters={"size_pct": 100}
        )

        sl = self.builder.add_block(
            graph,
            BlockType.ACTION_SET_STOP_LOSS,
            x=900,
            y=100,
            parameters={"stop_type": "percent", "value": 0.5},
        )
        tp = self.builder.add_block(
            graph,
            BlockType.ACTION_SET_TAKE_PROFIT,
            x=900,
            y=300,
            parameters={"tp_type": "percent", "value": 1.0},
        )

        self.builder.connect(graph, candles.id, "close", rsi.id, "source")
        self.builder.connect(graph, rsi.id, "rsi", oversold.id, "value")
        self.builder.connect(graph, rsi.id, "rsi", overbought.id, "value")
        self.builder.connect(graph, oversold.id, "below", buy.id, "trigger")
        self.builder.connect(graph, overbought.id, "above", sell.id, "trigger")
        self.builder.connect(graph, oversold.id, "below", sl.id, "trigger")
        self.builder.connect(graph, oversold.id, "below", tp.id, "trigger")

        return StrategyTemplate(
            id="scalping",
            name="RSI Scalping",
            category=TemplateCategory.SCALPING,
            description="Quick trades on extreme RSI readings",
            tags=["scalping", "rsi", "short-term", "advanced"],
            difficulty="advanced",
            timeframes=["1m", "5m", "15m"],
            graph_data=graph.to_dict(),
            how_it_works="""
            Fast trades on RSI extremes with tight stops.

            - Buy when RSI < 20 (extremely oversold)
            - Sell when RSI > 80 (extremely overbought)
            - Tight stop loss: 0.5%
            - Quick take profit: 1%
            """,
            parameters_description="""
            - RSI Period: 7 (fast)
            - Oversold: 20
            - Overbought: 80
            - Stop Loss: 0.5%
            - Take Profit: 1%
            """,
            recommended_markets=["High liquidity pairs only"],
            expected_performance="Many small wins, requires low fees",
            risks="High trading frequency, spread/fee sensitive",
        )
