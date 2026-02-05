"""
Strategy Builder Adapter

Converts Strategy Builder visual graphs (blocks + connections) into executable
BaseStrategy instances that can be used with backtesting engines.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

try:
    import vectorbt as vbt
except ImportError:
    vbt = None
    logger.warning("vectorbt not installed. Some Strategy Builder features may be unavailable.")

from backend.backtesting.strategies import BaseStrategy, SignalResult

# Import our custom indicators for extended coverage
from backend.core.indicators import (
    calculate_ad_line,
    calculate_aroon,
    calculate_atr,
    calculate_atrp,
    calculate_cci,
    calculate_cmf,
    calculate_cmo,
    calculate_dema,
    calculate_donchian,
    calculate_hull_ma,
    calculate_ichimoku,
    calculate_keltner,
    calculate_macd,
    calculate_mfi,
    calculate_obv,
    calculate_parabolic_sar,
    calculate_pivot_points,
    calculate_pvt,
    calculate_qqe,
    calculate_qqe_cross,
    calculate_roc,
    calculate_rsi,
    calculate_stddev,
    calculate_stoch_rsi,
    calculate_stochastic,
    calculate_supertrend,
    calculate_tema,
    calculate_vwap,
    calculate_williams_r,
    calculate_wma,
)

logger = logging.getLogger(__name__)


def _param(params: dict, default: Any, *keys: str) -> Any:
    """Get param value trying keys in order (supports snake_case and camelCase from frontend)."""
    for k in keys:
        v = params.get(k)
        if v is not None:
            return v
    return default


class StrategyBuilderAdapter(BaseStrategy):
    """
    Adapter for Strategy Builder generated strategies.

    Converts a visual block-based strategy graph into executable Python code
    that generates trading signals compatible with backtesting engines.

    Example:
        graph = {
            "blocks": [...],
            "connections": [...],
            "name": "My RSI Strategy"
        }
        adapter = StrategyBuilderAdapter(graph)
        signals = adapter.generate_signals(ohlcv)
    """

    def __init__(self, strategy_graph: dict[str, Any]):
        """
        Initialize adapter from strategy graph.

        Args:
            strategy_graph: Dictionary containing:
                - blocks: List of block objects
                - connections: List of connection objects
                - name: Strategy name
                - description: Strategy description (optional)
        """
        self.graph = strategy_graph
        self.name = strategy_graph.get("name", "Builder Strategy")
        self.description = strategy_graph.get("description", "")
        self.blocks = {block["id"]: block for block in strategy_graph.get("blocks", [])}
        self.connections = strategy_graph.get("connections", [])
        self.params = self._extract_params()

        # Build execution order (topological sort)
        self.execution_order = self._build_execution_order()

        # Cache for computed values
        self._value_cache: dict[str, pd.Series] = {}

        # Validate
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate strategy graph structure"""
        if not self.blocks:
            raise ValueError("Strategy graph must contain at least one block")

        # Check for main strategy node
        main_node = None
        for block in self.blocks.values():
            if block.get("type") == "strategy" or block.get("isMain"):
                main_node = block
                break

        if not main_node:
            logger.warning("No main strategy node found. Entry/exit signals may not be connected.")

    def _extract_params(self) -> dict[str, Any]:
        """Extract parameters from blocks"""
        params = {}
        for block_id, block in self.blocks.items():
            if block.get("params"):
                params[block_id] = block["params"]
        return params

    def _get_connection_source_id(self, conn: dict[str, Any]) -> str:
        """Get source block ID from connection, supporting both formats."""
        # Format 1: conn["source"]["blockId"] (old format)
        if "source" in conn and isinstance(conn["source"], dict):
            return conn["source"].get("blockId", "")
        # Format 2: conn["source_block"] (new API format)
        return conn.get("source_block", "")

    def _get_connection_target_id(self, conn: dict[str, Any]) -> str:
        """Get target block ID from connection, supporting both formats."""
        # Format 1: conn["target"]["blockId"] (old format)
        if "target" in conn and isinstance(conn["target"], dict):
            return conn["target"].get("blockId", "")
        # Format 2: conn["target_block"] (new API format)
        return conn.get("target_block", "")

    def _build_execution_order(self) -> list[str]:
        """
        Build topological sort of blocks based on connections.

        Returns:
            List of block IDs in execution order
        """
        # Build dependency graph
        dependencies: dict[str, list[str]] = {block_id: [] for block_id in self.blocks.keys()}

        for conn in self.connections:
            source_id = self._get_connection_source_id(conn)
            target_id = self._get_connection_target_id(conn)
            if target_id in dependencies and source_id:
                dependencies[target_id].append(source_id)

        # Topological sort (Kahn's algorithm)
        in_degree = {block_id: len(deps) for block_id, deps in dependencies.items()}
        queue = [block_id for block_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            block_id = queue.pop(0)
            result.append(block_id)

            # Find blocks that depend on this one
            for conn in self.connections:
                if self._get_connection_source_id(conn) == block_id:
                    target_id = self._get_connection_target_id(conn)
                    # Only decrement for actual blocks, not special targets like 'main_strategy'
                    if target_id in in_degree:
                        in_degree[target_id] -= 1
                        if in_degree[target_id] == 0:
                            queue.append(target_id)

        # Add any remaining blocks (disconnected)
        for block_id in self.blocks.keys():
            if block_id not in result:
                result.append(block_id)

        return result

    def _execute_block(self, block_id: str, ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute a single block and return its outputs.

        Args:
            block_id: Block ID to execute
            ohlcv: OHLCV DataFrame

        Returns:
            Dictionary mapping output port IDs to pd.Series values
        """
        block = self.blocks[block_id]
        block_type = block["type"]
        category = block.get("category", "")
        params = block.get("params", {})

        # Get input values from cache
        inputs = self._get_block_inputs(block_id)

        # Execute based on block type
        if category == "indicator":
            return self._execute_indicator(block_type, params, ohlcv, inputs)
        elif category == "condition":
            return self._execute_condition(block_type, params, inputs)
        elif category == "input":
            return self._execute_input(block_type, params, ohlcv)
        elif category == "logic":
            return self._execute_logic(block_type, params, inputs)
        elif category == "filter":
            return self._execute_filter(block_type, params, ohlcv, inputs)
        elif category == "action":
            # Action blocks (buy, sell, close, etc.) - return action type for engine
            return self._execute_action(block_type, params, inputs)
        elif category in ("exit", "exits"):
            # Exit condition blocks - return exit signals
            return self._execute_exit(block_type, params, ohlcv, inputs)
        elif category in ("sizing", "position_sizing"):
            # Position sizing blocks - config-only, processed by engine
            return self._execute_position_sizing(block_type, params)
        elif category in ("entry", "entry_refinement"):
            # Entry refinement blocks (DCA, pyramiding, etc.) - config-only
            return {}
        elif category in ("risk", "risk_controls"):
            # Risk control blocks - config-only
            return {}
        elif category in ("session", "session_mgmt"):
            # Session management blocks - config-only
            return {}
        elif category in ("time", "time_mgmt"):
            # Time management blocks - return time filter
            return self._execute_time_filter(block_type, params, ohlcv)
        elif category == "dca_grid":
            # DCA blocks are config-only, no signal output
            return self._execute_dca_block(block_type, params)
        elif category == "multiple_tp":
            # Multi-TP blocks are config-only
            return {}
        elif category == "atr_exit":
            # ATR exit blocks are config-only
            return {}
        elif category == "signal_memory":
            # Signal memory blocks are config-only
            return {}
        elif category == "price_action":
            # Price action pattern blocks
            return self._execute_price_action(block_type, params, ohlcv)
        elif category == "divergence":
            # Divergence detection blocks
            return self._execute_divergence(block_type, params, ohlcv)
        elif category == "close_conditions":
            # Close condition blocks - return exit signals
            return self._execute_close_condition(block_type, params, ohlcv, inputs)
        elif category == "correlation":
            # Correlation blocks - config-only for multi-symbol
            return {}
        elif category == "alerts":
            # Alert blocks - config-only, processed by alerting system
            return {}
        elif category == "visualization":
            # Visualization blocks - config-only, no signals
            return {}
        else:
            logger.warning(f"Unknown block category: {category} for block {block_id}")
            return {}

    def _get_connection_source_port(self, conn: dict[str, Any]) -> str:
        """Get source port ID from connection, supporting both formats."""
        # Format 1: conn["source"]["portId"] (old format)
        if "source" in conn and isinstance(conn["source"], dict):
            return conn["source"].get("portId", "value")
        # Format 2: conn["source_output"] (new API format)
        return conn.get("source_output", "value")

    def _get_connection_target_port(self, conn: dict[str, Any]) -> str:
        """Get target port ID from connection, supporting both formats."""
        # Format 1: conn["target"]["portId"] (old format)
        if "target" in conn and isinstance(conn["target"], dict):
            return conn["target"].get("portId", "value")
        # Format 2: conn["target_input"] (new API format)
        return conn.get("target_input", "value")

    def _get_block_inputs(self, block_id: str) -> dict[str, pd.Series]:
        """Get input values for a block from connections"""
        inputs = {}
        for conn in self.connections:
            target_id = self._get_connection_target_id(conn)
            if target_id == block_id:
                source_id = self._get_connection_source_id(conn)
                source_port = self._get_connection_source_port(conn)
                target_port = self._get_connection_target_port(conn)

                # Get value from cache
                if source_id in self._value_cache:
                    source_outputs = self._value_cache[source_id]
                    if source_port in source_outputs:
                        inputs[target_port] = source_outputs[source_port]
        return inputs

    def _execute_indicator(
        self, indicator_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute an indicator block"""
        if not vbt:
            raise ImportError("vectorbt is required for indicator execution")

        close = ohlcv["close"]

        if indicator_type == "rsi":
            period = params.get("period", 14)
            rsi = vbt.RSI.run(close, window=period).rsi
            return {"value": rsi}

        elif indicator_type == "macd":
            fast = _param(params, 12, "fast_period", "fast")
            slow = _param(params, 26, "slow_period", "slow")
            signal = _param(params, 9, "signal_period", "signal")
            macd_result = vbt.MACD.run(close, fast_window=fast, slow_window=slow, signal_window=signal)
            return {
                "macd": macd_result.macd,
                "signal": macd_result.signal,
                "hist": macd_result.histogram,
            }

        elif indicator_type == "ema":
            period = params.get("period", 20)
            ema = vbt.MA.run(close, window=period, ewm=True).ma
            return {"value": ema}

        elif indicator_type == "sma":
            period = params.get("period", 50)
            sma = vbt.MA.run(close, window=period).ma
            return {"value": sma}

        elif indicator_type == "bollinger":
            period = params.get("period", 20)
            std_dev = _param(params, 2.0, "std_dev", "stdDev")
            bb = vbt.BBANDS.run(close, window=period, num_std=std_dev)
            return {
                "upper": bb.upper,
                "middle": bb.middle,
                "lower": bb.lower,
            }

        elif indicator_type == "atr":
            period = params.get("period", 14)
            high = ohlcv["high"]
            low = ohlcv["low"]
            atr = vbt.ATR.run(high, low, close, window=period).atr
            return {"value": atr}

        elif indicator_type == "stochastic":
            k_period = _param(params, 14, "k_period", "k")
            d_period = _param(params, 3, "d_period", "d")
            high = ohlcv["high"]
            low = ohlcv["low"]
            stoch = vbt.STOCH.run(high, low, close, k_window=k_period, d_window=d_period)
            return {"k": stoch.k, "d": stoch.d}

        elif indicator_type == "adx":
            period = params.get("period", 14)
            high = ohlcv["high"]
            low = ohlcv["low"]
            adx = vbt.ADX.run(high, low, close, window=period).adx
            return {"value": adx}

        # ========== QQE Indicator ==========
        elif indicator_type == "qqe":
            rsi_period = _param(params, 14, "rsi_period", "rsiPeriod")
            smoothing = _param(params, 5, "smoothing_period", "smoothing")
            qqe_factor = _param(params, 4.236, "qqe_factor", "qqeFactor")
            qqe_result = calculate_qqe(
                close.values, rsi_period=rsi_period, smoothing_factor=smoothing, qqe_factor=qqe_factor
            )
            return {
                "qqe_line": pd.Series(qqe_result["qqe_line"], index=ohlcv.index),
                "rsi_ma": pd.Series(qqe_result["rsi_ma"], index=ohlcv.index),
                "upper_band": pd.Series(qqe_result["upper_band"], index=ohlcv.index),
                "lower_band": pd.Series(qqe_result["lower_band"], index=ohlcv.index),
                "histogram": pd.Series(qqe_result["histogram"], index=ohlcv.index),
                "trend": pd.Series(qqe_result["trend"], index=ohlcv.index),
            }

        # ========== Momentum Indicators ==========
        elif indicator_type == "stoch_rsi":
            rsi_period = _param(params, 14, "rsi_period", "rsiPeriod")
            stoch_period = _param(params, 14, "stoch_period", "stochPeriod")
            k_period = _param(params, 3, "k_period", "kPeriod")
            d_period = _param(params, 3, "d_period", "dPeriod")
            result = calculate_stoch_rsi(close.values, rsi_period, stoch_period, k_period, d_period)
            return {
                "k": pd.Series(result["k"], index=ohlcv.index),
                "d": pd.Series(result["d"], index=ohlcv.index),
            }

        elif indicator_type == "williams_r":
            period = params.get("period", 14)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_williams_r(high, low, close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "roc":
            period = params.get("period", 10)
            result = calculate_roc(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "mfi":
            period = params.get("period", 14)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            volume = ohlcv["volume"].values
            result = calculate_mfi(high, low, close.values, volume, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "cmo":
            period = params.get("period", 14)
            result = calculate_cmo(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "cci":
            period = params.get("period", 20)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_cci(high, low, close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        # ========== Trend Indicators ==========
        elif indicator_type == "wma":
            period = params.get("period", 20)
            result = calculate_wma(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "dema":
            period = params.get("period", 20)
            result = calculate_dema(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "tema":
            period = params.get("period", 20)
            result = calculate_tema(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "hull_ma":
            period = params.get("period", 20)
            result = calculate_hull_ma(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "supertrend":
            period = params.get("period", 10)
            multiplier = params.get("multiplier", 3.0)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_supertrend(high, low, close.values, period, multiplier)
            return {
                "supertrend": pd.Series(result["supertrend"], index=ohlcv.index),
                "direction": pd.Series(result["direction"], index=ohlcv.index),
                "upper": pd.Series(result["upper_band"], index=ohlcv.index),
                "lower": pd.Series(result["lower_band"], index=ohlcv.index),
            }

        elif indicator_type == "ichimoku":
            tenkan = _param(params, 9, "tenkan_period", "tenkan")
            kijun = _param(params, 26, "kijun_period", "kijun")
            senkou_b = _param(params, 52, "senkou_b_period", "senkouB")
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_ichimoku(high, low, close.values, tenkan, kijun, senkou_b)
            return {
                "tenkan_sen": pd.Series(result.tenkan_sen, index=ohlcv.index),
                "kijun_sen": pd.Series(result.kijun_sen, index=ohlcv.index),
                "senkou_span_a": pd.Series(result.senkou_span_a, index=ohlcv.index),
                "senkou_span_b": pd.Series(result.senkou_span_b, index=ohlcv.index),
                "chikou_span": pd.Series(result.chikou_span, index=ohlcv.index),
            }

        elif indicator_type == "parabolic_sar":
            af_start = _param(params, 0.02, "start", "afStart")
            af_step = _param(params, 0.02, "increment", "afStep")
            af_max = _param(params, 0.2, "max_value", "afMax")
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_parabolic_sar(high, low, af_start, af_step, af_max)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "aroon":
            period = params.get("period", 25)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_aroon(high, low, period)
            return {
                "up": pd.Series(result.aroon_up, index=ohlcv.index),
                "down": pd.Series(result.aroon_down, index=ohlcv.index),
                "oscillator": pd.Series(result.aroon_oscillator, index=ohlcv.index),
            }

        # ========== Volatility Indicators ==========
        elif indicator_type == "atrp":
            period = params.get("period", 14)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_atrp(high, low, close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "keltner":
            period = _param(params, 20, "ema_period", "period")
            multiplier = params.get("multiplier", 2.0)
            atr_period = _param(params, 10, "atr_period", "atrPeriod")
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_keltner(high, low, close.values, period, multiplier, atr_period)
            return {
                "upper": pd.Series(result["upper"], index=ohlcv.index),
                "middle": pd.Series(result["middle"], index=ohlcv.index),
                "lower": pd.Series(result["lower"], index=ohlcv.index),
            }

        elif indicator_type == "donchian":
            period = params.get("period", 20)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_donchian(high, low, period)
            return {
                "upper": pd.Series(result["upper"], index=ohlcv.index),
                "middle": pd.Series(result["middle"], index=ohlcv.index),
                "lower": pd.Series(result["lower"], index=ohlcv.index),
            }

        elif indicator_type == "stddev":
            period = params.get("period", 20)
            result = calculate_stddev(close.values, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        # ========== Volume Indicators ==========
        elif indicator_type == "obv":
            volume = ohlcv["volume"].values
            result = calculate_obv(close.values, volume)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "vwap":
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            volume = ohlcv["volume"].values
            result = calculate_vwap(high, low, close.values, volume)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "cmf":
            period = params.get("period", 20)
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            volume = ohlcv["volume"].values
            result = calculate_cmf(high, low, close.values, volume, period)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "ad_line":
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            volume = ohlcv["volume"].values
            result = calculate_ad_line(high, low, close.values, volume)
            return {"value": pd.Series(result, index=ohlcv.index)}

        elif indicator_type == "pvt":
            volume = ohlcv["volume"].values
            result = calculate_pvt(close.values, volume)
            return {"value": pd.Series(result, index=ohlcv.index)}

        # ========== Support/Resistance ==========
        elif indicator_type == "pivot_points":
            high = ohlcv["high"].values
            low = ohlcv["low"].values
            result = calculate_pivot_points(high, low, close.values)
            return {
                "pp": pd.Series(result.pp, index=ohlcv.index),
                "r1": pd.Series(result.r1, index=ohlcv.index),
                "r2": pd.Series(result.r2, index=ohlcv.index),
                "r3": pd.Series(result.r3, index=ohlcv.index),
                "s1": pd.Series(result.s1, index=ohlcv.index),
                "s2": pd.Series(result.s2, index=ohlcv.index),
                "s3": pd.Series(result.s3, index=ohlcv.index),
            }

        # ========== Multi-Timeframe ==========
        elif indicator_type == "mtf":
            # Multi-timeframe indicator
            # Resamples current data to higher timeframe and calculates indicator
            htf = params.get("timeframe", "1h")  # Higher timeframe
            indicator = params.get("indicator", "ema")  # Indicator to calculate
            period = params.get("period", 20)
            source = params.get("source", "close")

            # Get source data
            src = ohlcv[source] if source in ohlcv.columns else close

            # Resample to higher timeframe
            # Map timeframe string to pandas resample rule
            tf_map = {
                "5m": "5min",
                "15m": "15min",
                "30m": "30min",
                "1h": "1h",
                "2h": "2h",
                "4h": "4h",
                "1d": "1D",
                "1w": "1W",
            }
            resample_rule = tf_map.get(htf, "1h")

            try:
                # Resample OHLCV
                ohlcv_htf = (
                    ohlcv.resample(resample_rule)
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                    .dropna()
                )

                src_htf = ohlcv_htf["close"]

                # Calculate indicator on HTF data
                if indicator == "ema":
                    htf_values = src_htf.ewm(span=period, adjust=False).mean()
                elif indicator == "sma":
                    htf_values = src_htf.rolling(period).mean()
                elif indicator == "rsi":
                    htf_values = pd.Series(calculate_rsi(src_htf.values, period=period), index=src_htf.index)
                elif indicator == "atr":
                    htf_values = pd.Series(calculate_atr(ohlcv_htf, period=period), index=ohlcv_htf.index)
                else:
                    htf_values = src_htf.rolling(period).mean()

                # Forward fill to match original timeframe
                htf_reindexed = htf_values.reindex(ohlcv.index, method="ffill")

                return {"value": htf_reindexed.fillna(method="bfill")}

            except Exception as e:
                logger.warning(f"MTF calculation error: {e}")
                # Fallback to regular calculation
                if indicator == "ema":
                    fallback = src.ewm(span=period, adjust=False).mean()
                else:
                    fallback = src.rolling(period).mean()
                return {"value": fallback}

        else:
            logger.warning(f"Unknown indicator type: {indicator_type}")
            return {}

    def _execute_condition(
        self, condition_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute a condition block"""
        if condition_type == "crossover":
            a = inputs.get("a", pd.Series([False] * 100))
            b = inputs.get("b", pd.Series([False] * 100))
            result = (a > b) & (a.shift(1) <= b.shift(1))
            return {"result": result}

        elif condition_type == "crossunder":
            a = inputs.get("a", pd.Series([False] * 100))
            b = inputs.get("b", pd.Series([False] * 100))
            result = (a < b) & (a.shift(1) >= b.shift(1))
            return {"result": result}

        elif condition_type == "greater_than":
            a = inputs.get("a", pd.Series([0] * 100))
            b = inputs.get("b", pd.Series([0] * 100))
            result = a > b
            return {"result": result}

        elif condition_type == "less_than":
            a = inputs.get("a", pd.Series([0] * 100))
            b = inputs.get("b", pd.Series([0] * 100))
            result = a < b
            return {"result": result}

        elif condition_type == "equals":
            a = inputs.get("a", pd.Series([0] * 100))
            b = inputs.get("b", pd.Series([0] * 100))
            result = a == b
            return {"result": result}

        elif condition_type == "between":
            value = inputs.get("value", pd.Series([0] * 100))
            min_val = inputs.get("min", pd.Series([0] * 100))
            max_val = inputs.get("max", pd.Series([0] * 100))
            result = (value >= min_val) & (value <= max_val)
            return {"result": result}

        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return {"result": pd.Series([False] * 100)}

    def _execute_input(self, input_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """Execute an input block"""
        if input_type == "price":
            return {
                "open": ohlcv["open"],
                "high": ohlcv["high"],
                "low": ohlcv["low"],
                "close": ohlcv["close"],
            }
        elif input_type == "volume":
            return {"value": ohlcv["volume"]}
        elif input_type == "constant":
            value = params.get("value", 0)
            n = len(ohlcv)
            return {"value": pd.Series([value] * n, index=ohlcv.index)}
        else:
            logger.warning(f"Unknown input type: {input_type}")
            return {}

    def _execute_logic(
        self, logic_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """Execute a logic block"""
        if logic_type == "and":
            a = inputs.get("a", pd.Series([False] * 100))
            b = inputs.get("b", pd.Series([False] * 100))
            return {"result": a & b}

        elif logic_type == "or":
            a = inputs.get("a", pd.Series([False] * 100))
            b = inputs.get("b", pd.Series([False] * 100))
            return {"result": a | b}

        elif logic_type == "not":
            input_val = inputs.get("input", pd.Series([False] * 100))
            return {"result": ~input_val}

        elif logic_type == "delay":
            bars = params.get("bars", 1)
            input_val = inputs.get("input", pd.Series([False] * 100))
            return {"result": input_val.shift(bars).fillna(False)}

        elif logic_type == "filter":
            signal = inputs.get("signal", pd.Series([False] * 100))
            filter_val = inputs.get("filter", pd.Series([True] * 100))
            return {"result": signal & filter_val}

        else:
            logger.warning(f"Unknown logic type: {logic_type}")
            return {"result": pd.Series([False] * 100)}

    def _execute_filter(
        self, filter_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute a filter block - generates buy/sell signals based on indicator conditions.

        Filters are self-contained signal generators that compute indicators internally
        and return buy/sell boolean series.
        """
        n = len(ohlcv)
        close = ohlcv["close"].values
        high = ohlcv["high"].values
        low = ohlcv["low"].values
        volume = ohlcv["volume"].values

        # Helper for crossover detection
        def crossover(a, b):
            return (a > b) & (np.roll(a, 1) <= np.roll(b, 1))

        def crossunder(a, b):
            return (a < b) & (np.roll(a, 1) >= np.roll(b, 1))

        def apply_signal_memory(
            buy_events: np.ndarray,
            sell_events: np.ndarray,
            memory_bars: int,
        ) -> tuple[np.ndarray, np.ndarray]:
            """
            Extend buy/sell signals for N bars after each event; opposite signal cancels.

            If a buy occurs at bar i, buy is True for bars i..i+N unless a sell occurs
            in that window (then buy memory stops at that bar). Same for sell.
            """
            n = len(buy_events)
            buy_out = np.zeros(n, dtype=bool)
            sell_out = np.zeros(n, dtype=bool)
            active_buy_until = -1
            active_sell_until = -1
            for i in range(n):
                if sell_events[i]:
                    active_buy_until = -1
                if buy_events[i]:
                    active_buy_until = i + memory_bars
                buy_out[i] = active_buy_until >= i
                if buy_events[i]:
                    active_sell_until = -1
                if sell_events[i]:
                    active_sell_until = i + memory_bars
                sell_out[i] = active_sell_until >= i
            return buy_out, sell_out

        # ========== RSI Filter ==========
        if filter_type == "rsi_filter":
            from backend.core.indicators import calculate_rsi

            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            overbought = params.get("overbought", 70)
            mode = params.get("mode", "range")  # range, cross

            rsi = calculate_rsi(close, period)

            if mode == "range":
                buy = rsi < oversold
                sell = rsi > overbought
            else:  # cross
                buy = crossunder(rsi, np.full(n, oversold))
                sell = crossover(rsi, np.full(n, overbought))

            mem_bars = int(params.get("signal_memory_bars", 0))
            if mem_bars > 0 and (
                params.get("signal_memory_enable", False) or params.get("use_signal_memory", False)
            ):
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(rsi, index=ohlcv.index),
            }

        # ========== QQE Filter ==========
        elif filter_type == "qqe_filter":
            rsi_period = _param(params, 14, "rsi_period", "rsiPeriod")
            smoothing = _param(params, 5, "smoothing_period", "smoothing")
            qqe_factor = _param(params, 4.236, "qqe_factor", "qqeFactor")

            qqe_result = calculate_qqe_cross(
                close, rsi_period=rsi_period, smoothing_factor=smoothing, qqe_factor=qqe_factor
            )

            return {
                "buy": pd.Series(qqe_result["buy_signal"], index=ohlcv.index),
                "sell": pd.Series(qqe_result["sell_signal"], index=ohlcv.index),
                "qqe_line": pd.Series(qqe_result["qqe_line"], index=ohlcv.index),
                "trend": pd.Series(qqe_result["trend"], index=ohlcv.index),
            }

        # ========== SuperTrend Filter ==========
        elif filter_type == "supertrend_filter":
            period = params.get("period", 10)
            multiplier = params.get("multiplier", 3.0)

            result = calculate_supertrend(high, low, close, period, multiplier)
            direction = result["direction"]

            # Buy when direction changes to 1 (uptrend), sell when -1 (downtrend)
            buy = (direction == 1) & (np.roll(direction, 1) == -1)
            sell = (direction == -1) & (np.roll(direction, 1) == 1)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "supertrend": pd.Series(result["supertrend"], index=ohlcv.index),
                "direction": pd.Series(direction, index=ohlcv.index),
            }

        # ========== Two MA Filter ==========
        elif filter_type == "two_ma_filter":
            from backend.core.indicators import calculate_ema, calculate_sma

            fast_period = _param(params, 9, "fast_period", "fastPeriod")
            slow_period = _param(params, 21, "slow_period", "slowPeriod")
            ma_type = _param(params, "ema", "ma_type", "maType")

            if ma_type == "ema":
                fast = calculate_ema(close, fast_period)
                slow = calculate_ema(close, slow_period)
            else:
                fast = calculate_sma(close, fast_period)
                slow = calculate_sma(close, slow_period)

            buy = crossover(fast, slow)
            sell = crossunder(fast, slow)

            mem_bars = int(params.get("ma_cross_memory_bars", 0))
            if mem_bars > 0:
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "fast": pd.Series(fast, index=ohlcv.index),
                "slow": pd.Series(slow, index=ohlcv.index),
            }

        # ========== Stochastic Filter ==========
        elif filter_type == "stochastic_filter":
            k_period = _param(params, 14, "k_period", "kPeriod")
            d_period = _param(params, 3, "d_period", "dPeriod")
            oversold = params.get("oversold", 20)
            overbought = params.get("overbought", 80)
            mode = params.get("mode", "cross")  # range, cross, kd_cross

            k, d = calculate_stochastic(high, low, close, k_period, d_period)

            if mode == "range":
                buy = k < oversold
                sell = k > overbought
            elif mode == "kd_cross":
                buy = crossover(k, d) & (k < oversold)
                sell = crossunder(k, d) & (k > overbought)
            else:  # cross
                buy = crossunder(k, np.full(n, oversold))
                sell = crossover(k, np.full(n, overbought))

            mem_bars = 0
            if mode == "cross" and params.get("activate_stoch_cross_memory", False):
                mem_bars = int(params.get("stoch_cross_memory_bars", 0))
            elif mode == "kd_cross" and params.get("activate_stoch_kd_memory", False):
                mem_bars = int(params.get("stoch_kd_memory_bars", 0))
            if mem_bars > 0:
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "k": pd.Series(k, index=ohlcv.index),
                "d": pd.Series(d, index=ohlcv.index),
            }

        # ========== MACD Filter ==========
        elif filter_type == "macd_filter":
            from backend.core.indicators import calculate_macd

            fast = _param(params, 12, "fast_period", "fast")
            slow = _param(params, 26, "slow_period", "slow")
            signal_period = _param(params, 9, "signal_period", "signal")
            mode = params.get("mode", "signal_cross")  # signal_cross, zero_cross, histogram

            macd_line, signal_line, histogram = calculate_macd(close, fast, slow, signal_period)

            if mode == "zero_cross":
                buy = crossover(macd_line, np.zeros(n))
                sell = crossunder(macd_line, np.zeros(n))
            elif mode == "histogram":
                buy = (histogram > 0) & (np.roll(histogram, 1) <= 0)
                sell = (histogram < 0) & (np.roll(histogram, 1) >= 0)
            else:  # signal_cross
                buy = crossover(macd_line, signal_line)
                sell = crossunder(macd_line, signal_line)

            mem_bars = int(params.get("macd_signal_memory_bars", 0))
            if mem_bars > 0 and not params.get("disable_macd_signal_memory", True):
                buy, sell = apply_signal_memory(np.asarray(buy, dtype=bool), np.asarray(sell, dtype=bool), mem_bars)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "macd": pd.Series(macd_line, index=ohlcv.index),
                "signal": pd.Series(signal_line, index=ohlcv.index),
                "histogram": pd.Series(histogram, index=ohlcv.index),
            }

        # ========== CCI Filter ==========
        elif filter_type == "cci_filter":
            period = params.get("period", 20)
            oversold = params.get("oversold", -100)
            overbought = params.get("overbought", 100)

            cci = calculate_cci(high, low, close, period)

            buy = crossunder(cci, np.full(n, oversold))
            sell = crossover(cci, np.full(n, overbought))

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(cci, index=ohlcv.index),
            }

        # ========== DMI/ADX Filter ==========
        elif filter_type == "dmi_filter":
            period = params.get("period", 14)
            adx_threshold = _param(params, 25, "threshold", "adxThreshold")

            from backend.core.indicators import calculate_adx

            adx_result = calculate_adx(high, low, close, period)
            adx = adx_result.adx
            plus_di = adx_result.plus_di
            minus_di = adx_result.minus_di

            # Buy when +DI crosses above -DI and ADX > threshold
            buy = crossover(plus_di, minus_di) & (adx > adx_threshold)
            sell = crossunder(plus_di, minus_di) & (adx > adx_threshold)

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "adx": pd.Series(adx, index=ohlcv.index),
                "plus_di": pd.Series(plus_di, index=ohlcv.index),
                "minus_di": pd.Series(minus_di, index=ohlcv.index),
            }

        # ========== ATR Filter ==========
        elif filter_type == "atr_filter":
            from backend.core.indicators import calculate_atr

            period = params.get("period", 14)
            threshold = params.get("threshold", 1.5)  # ATR multiplier

            atr = calculate_atr(high, low, close, period)
            atr_ma = pd.Series(atr).rolling(period).mean().values

            # High volatility when ATR > threshold * average ATR
            high_volatility = atr > (threshold * atr_ma)

            return {
                "pass": pd.Series(high_volatility, index=ohlcv.index),
                "value": pd.Series(atr, index=ohlcv.index),
            }

        # ========== Volume Filter ==========
        elif filter_type == "volume_filter":
            period = params.get("period", 20)
            multiplier = params.get("multiplier", 1.5)

            volume_ma = pd.Series(volume).rolling(period).mean().values
            high_volume = volume > (multiplier * volume_ma)

            return {
                "pass": pd.Series(high_volume, index=ohlcv.index),
                "value": pd.Series(volume, index=ohlcv.index),
                "ma": pd.Series(volume_ma, index=ohlcv.index),
            }

        # ========== Volume Compare Filter ==========
        elif filter_type == "volume_compare_filter":
            period = params.get("period", 20)
            multiplier = params.get("multiplier", 2.0)

            volume_ma = pd.Series(volume).rolling(period).mean().values
            above_avg = volume > (multiplier * volume_ma)

            return {
                "pass": pd.Series(above_avg, index=ohlcv.index),
                "ratio": pd.Series(volume / np.maximum(volume_ma, 1), index=ohlcv.index),
            }

        # ========== CMF Filter ==========
        elif filter_type == "cmf_filter":
            period = params.get("period", 20)
            threshold = params.get("threshold", 0.05)

            cmf = calculate_cmf(high, low, close, volume, period)

            buy = cmf > threshold
            sell = cmf < -threshold

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(cmf, index=ohlcv.index),
            }

        # ========== Trend Filter ==========
        elif filter_type == "trend_filter":
            from backend.core.indicators import calculate_adx, calculate_ema

            ema_period = params.get("emaPeriod", 50)
            adx_period = params.get("adxPeriod", 14)
            adx_threshold = _param(params, 25, "threshold", "adxThreshold")

            ema = calculate_ema(close, ema_period)
            adx_result = calculate_adx(high, low, close, adx_period)

            uptrend = (close > ema) & (adx_result.adx > adx_threshold)
            downtrend = (close < ema) & (adx_result.adx > adx_threshold)

            return {
                "uptrend": pd.Series(uptrend, index=ohlcv.index),
                "downtrend": pd.Series(downtrend, index=ohlcv.index),
                "ema": pd.Series(ema, index=ohlcv.index),
                "adx": pd.Series(adx_result.adx, index=ohlcv.index),
            }

        # ========== Price Filter ==========
        elif filter_type == "price_filter":
            level = params.get("level", 0)
            mode = params.get("mode", "above")  # above, below

            if mode == "above":
                result = close > level
            else:
                result = close < level

            return {"pass": pd.Series(result, index=ohlcv.index)}

        # ========== Volatility Filter ==========
        elif filter_type == "volatility_filter":
            from backend.core.indicators import calculate_atr, calculate_bollinger

            period = params.get("period", 20)
            mode = params.get("mode", "atr")  # atr, bb_width
            threshold = params.get("threshold", 1.0)

            if mode == "bb_width":
                bb = calculate_bollinger(close, period, 2.0)
                bb_width = (bb["upper"] - bb["lower"]) / bb["middle"]
                bb_width_ma = pd.Series(bb_width).rolling(period).mean().values
                high_vol = bb_width > (threshold * bb_width_ma)
                return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(bb_width, index=ohlcv.index)}
            else:
                atr = calculate_atr(high, low, close, period)
                atr_ma = pd.Series(atr).rolling(period).mean().values
                high_vol = atr > (threshold * atr_ma)
                return {"pass": pd.Series(high_vol, index=ohlcv.index), "value": pd.Series(atr, index=ohlcv.index)}

        # ========== Highest/Lowest Filter ==========
        elif filter_type == "highest_lowest_filter":
            period = params.get("period", 20)

            highest = pd.Series(high).rolling(period).max().values
            lowest = pd.Series(low).rolling(period).min().values

            breakout_up = close >= highest
            breakout_down = close <= lowest

            return {
                "buy": pd.Series(breakout_up, index=ohlcv.index),
                "sell": pd.Series(breakout_down, index=ohlcv.index),
                "highest": pd.Series(highest, index=ohlcv.index),
                "lowest": pd.Series(lowest, index=ohlcv.index),
            }

        # ========== Momentum Filter ==========
        elif filter_type == "momentum_filter":
            period = params.get("period", 10)
            threshold = params.get("threshold", 0)

            momentum = close - np.roll(close, period)

            buy = momentum > threshold
            sell = momentum < -threshold

            return {
                "buy": pd.Series(buy, index=ohlcv.index),
                "sell": pd.Series(sell, index=ohlcv.index),
                "value": pd.Series(momentum, index=ohlcv.index),
            }

        # ========== Time Filter ==========
        elif filter_type == "time_filter":
            start_hour = params.get("startHour", 9)
            end_hour = params.get("endHour", 17)

            hours = ohlcv.index.hour if hasattr(ohlcv.index, "hour") else np.zeros(n)
            in_session = (hours >= start_hour) & (hours < end_hour)

            return {"pass": pd.Series(in_session, index=ohlcv.index)}

        # ========== Accumulation Filter ==========
        elif filter_type == "accumulation_filter":
            # Detect volume accumulation zones
            period = params.get("period", 20)
            volume_mult = params.get("volume_multiplier", 1.5)
            range_threshold = params.get("range_threshold", 0.5)  # ATR multiplier

            volume = ohlcv["volume"]
            avg_volume = volume.rolling(period).mean()
            high_volume = volume > avg_volume * volume_mult

            # Price range compression (consolidation)
            atr = pd.Series(calculate_atr(ohlcv, period=period), index=ohlcv.index)
            price_range = ohlcv["high"] - ohlcv["low"]
            avg_range = price_range.rolling(period).mean()
            tight_range = price_range < avg_range * range_threshold

            # Accumulation: high volume + tight range
            accumulation = high_volume & tight_range

            # Distribution: high volume + wide range
            distribution = high_volume & ~tight_range

            return {
                "accumulation": accumulation.fillna(False),
                "distribution": distribution.fillna(False),
                "buy": accumulation.fillna(False),
                "sell": distribution.fillna(False),
            }

        # ========== Linear Regression Filter ==========
        elif filter_type == "linreg_filter":
            # Linear regression channel filter
            period = params.get("period", 20)
            dev_mult = params.get("deviation", 2.0)
            mode = params.get("mode", "trend")  # trend, channel_break, slope

            close = ohlcv["close"]

            # Calculate linear regression
            def linreg(series, length):
                """Calculate linear regression value."""
                x = np.arange(length)
                result = np.full(len(series), np.nan)
                for i in range(length - 1, len(series)):
                    y = series.iloc[i - length + 1 : i + 1].values
                    if len(y) == length:
                        slope, intercept = np.polyfit(x, y, 1)
                        result[i] = intercept + slope * (length - 1)
                return result

            def linreg_slope(series, length):
                """Calculate linear regression slope."""
                x = np.arange(length)
                result = np.full(len(series), np.nan)
                for i in range(length - 1, len(series)):
                    y = series.iloc[i - length + 1 : i + 1].values
                    if len(y) == length:
                        slope, _ = np.polyfit(x, y, 1)
                        result[i] = slope
                return result

            linreg_val = pd.Series(linreg(close, period), index=ohlcv.index)
            slope = pd.Series(linreg_slope(close, period), index=ohlcv.index)

            # Standard deviation for channel
            residuals = close - linreg_val
            std = residuals.rolling(period).std()
            upper = linreg_val + dev_mult * std
            lower = linreg_val - dev_mult * std

            if mode == "trend":
                # Uptrend: positive slope, price above linreg
                buy = (slope > 0) & (close > linreg_val)
                sell = (slope < 0) & (close < linreg_val)
            elif mode == "channel_break":
                # Buy on upper break, sell on lower break
                buy = close > upper
                sell = close < lower
            else:  # slope
                # Buy on positive slope, sell on negative
                buy = slope > 0
                sell = slope < 0

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "linreg": linreg_val,
                "slope": slope,
                "upper": upper,
                "lower": lower,
            }

        # ========== Divergence Filter ==========
        elif filter_type == "divergence_filter":
            # Redirect to divergence category handler
            indicator = params.get("indicator", "rsi")
            period = params.get("period", 14)
            lookback = params.get("lookback", 14)

            close = ohlcv["close"]
            high = ohlcv["high"]
            low = ohlcv["low"]

            if indicator == "rsi":
                ind_val = pd.Series(calculate_rsi(close.values, period=period), index=ohlcv.index)
            elif indicator == "macd":
                macd_line, signal_line, histogram = calculate_macd(close.values, 12, 26, 9)
                ind_val = pd.Series(histogram, index=ohlcv.index)
            elif indicator == "obv":
                ind_val = pd.Series(calculate_obv(ohlcv), index=ohlcv.index)
            else:
                ind_val = pd.Series(calculate_rsi(close.values, period=period), index=ohlcv.index)

            # Bullish divergence: price lower low, indicator higher low
            price_lower_low = low < low.shift(lookback)
            ind_higher_low = ind_val > ind_val.shift(lookback)
            bullish = price_lower_low & ind_higher_low

            # Bearish divergence: price higher high, indicator lower high
            price_higher_high = high > high.shift(lookback)
            ind_lower_high = ind_val < ind_val.shift(lookback)
            bearish = price_higher_high & ind_lower_high

            return {
                "buy": bullish.fillna(False),
                "sell": bearish.fillna(False),
                "bullish": bullish.fillna(False),
                "bearish": bearish.fillna(False),
            }

        # ========== Balance of Power Filter ==========
        elif filter_type == "bop_filter":
            # Balance of Power indicator filter
            period = params.get("period", 14)
            threshold = params.get("threshold", 0.0)
            mode = params.get("mode", "level")  # level, cross, trend

            # BOP = (Close - Open) / (High - Low)
            high = ohlcv["high"]
            low = ohlcv["low"]
            open_price = ohlcv["open"]
            close = ohlcv["close"]

            bop = (close - open_price) / (high - low + 1e-10)
            bop_smooth = bop.rolling(period).mean()

            if mode == "level":
                # Buy when BOP above threshold, sell when below
                buy = bop_smooth > threshold
                sell = bop_smooth < -threshold
            elif mode == "cross":
                # Buy on cross above zero, sell on cross below
                buy = (bop_smooth > 0) & (bop_smooth.shift(1) <= 0)
                sell = (bop_smooth < 0) & (bop_smooth.shift(1) >= 0)
            else:  # trend
                # Buy on rising BOP, sell on falling
                buy = bop_smooth > bop_smooth.shift(1)
                sell = bop_smooth < bop_smooth.shift(1)

            return {
                "buy": buy.fillna(False),
                "sell": sell.fillna(False),
                "value": bop_smooth,
            }

        # ========== Levels Break Filter ==========
        elif filter_type == "levels_filter":
            # Pivot/Support/Resistance break filter
            period = params.get("period", 20)
            level_type = params.get("level_type", "pivot")  # pivot, swing, fixed

            high = ohlcv["high"]
            low = ohlcv["low"]
            close = ohlcv["close"]

            if level_type == "pivot":
                # Use pivot points
                pp = (high.shift(1) + low.shift(1) + close.shift(1)) / 3
                r1 = 2 * pp - low.shift(1)
                s1 = 2 * pp - high.shift(1)

                buy = close > r1  # Break above R1
                sell = close < s1  # Break below S1

                return {
                    "buy": buy.fillna(False),
                    "sell": sell.fillna(False),
                    "pivot": pp,
                    "r1": r1,
                    "s1": s1,
                }
            else:  # swing
                # Swing high/low breaks
                swing_high = high.rolling(period).max()
                swing_low = low.rolling(period).min()

                buy = close > swing_high.shift(1)  # Break above swing high
                sell = close < swing_low.shift(1)  # Break below swing low

                return {
                    "buy": buy.fillna(False),
                    "sell": sell.fillna(False),
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                }

        # ========== Price Action Filter ==========
        elif filter_type == "price_action_filter":
            # Candlestick pattern filter
            pattern = params.get("pattern", "engulfing")

            o = ohlcv["open"]
            h = ohlcv["high"]
            l = ohlcv["low"]
            c = ohlcv["close"]
            body = abs(c - o)

            if pattern == "engulfing":
                # Bullish engulfing
                prev_red = o.shift(1) > c.shift(1)
                curr_green = c > o
                engulfs = (c > o.shift(1)) & (o < c.shift(1))
                bullish = prev_red & curr_green & engulfs

                # Bearish engulfing
                prev_green = c.shift(1) > o.shift(1)
                curr_red = o > c
                engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
                bearish = prev_green & curr_red & engulfs_bear

            elif pattern == "doji":
                # Doji: small body
                avg_body = body.rolling(20).mean()
                doji = body < avg_body * 0.1
                bullish = doji & (c > o)
                bearish = doji & (c < o)

            elif pattern == "hammer":
                # Hammer: long lower wick
                lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
                upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
                bullish = (lower_wick > body * 2) & (upper_wick < body * 0.5)
                bearish = (upper_wick > body * 2) & (lower_wick < body * 0.5)

            else:
                bullish = pd.Series([False] * n, index=ohlcv.index)
                bearish = pd.Series([False] * n, index=ohlcv.index)

            return {
                "buy": bullish.fillna(False),
                "sell": bearish.fillna(False),
            }

        # ========== Default: Unknown filter ==========
        else:
            logger.warning(f"Unknown filter type: {filter_type}")
            return {
                "buy": pd.Series([False] * n, index=ohlcv.index),
                "sell": pd.Series([False] * n, index=ohlcv.index),
            }

    def _execute_action(
        self, action_type: str, params: dict[str, Any], inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute action blocks (buy, sell, close, etc.).

        Action blocks generate entry/exit signals based on input conditions.

        Supported action types:
            - buy, buy_market, buy_limit: Long entry
            - sell, sell_market, sell_limit: Short entry
            - close_long, close_short, close_all: Exit signals
            - stop_loss, take_profit: Exit with price levels
            - trailing_stop: Exit with trailing
        """
        # Get input signal (from condition or filter block)
        input_signal = None
        for key in ["signal", "condition", "output"]:
            if key in inputs:
                input_signal = inputs[key]
                break

        if input_signal is None:
            # No input - action doesn't trigger
            n = len(next(iter(inputs.values()))) if inputs else 0
            empty_signal = pd.Series([False] * n)
            return {"signal": empty_signal}

        # Pass through signal based on action type
        result: dict[str, pd.Series] = {}

        if action_type in ["buy", "buy_market", "buy_limit"]:
            result["entry_long"] = input_signal
            result["signal"] = input_signal

        elif action_type in ["sell", "sell_market", "sell_limit"]:
            result["entry_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_long":
            result["exit_long"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_short":
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "close_all":
            result["exit_long"] = input_signal
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        elif action_type == "stop_loss":
            # Stop loss configuration
            percent = params.get("percent", 2.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["stop_loss_percent"] = percent

        elif action_type == "take_profit":
            # Take profit configuration
            percent = params.get("percent", 3.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["take_profit_percent"] = percent

        elif action_type == "trailing_stop":
            # Trailing stop configuration
            percent = params.get("percent", 1.5)
            activation = params.get("activation", 1.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["trailing_percent"] = percent
            result["trailing_activation"] = activation

        elif action_type == "atr_stop":
            # ATR-based stop loss
            period = params.get("period", 14)
            multiplier = params.get("multiplier", 2.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["atr_period"] = period
            result["atr_multiplier"] = multiplier

        elif action_type == "chandelier_stop":
            # Chandelier stop (from highest high - ATR)
            period = params.get("period", 22)
            multiplier = params.get("multiplier", 3.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["chandelier_period"] = period
            result["chandelier_multiplier"] = multiplier

        elif action_type == "break_even":
            # Move stop to entry price after X% profit
            trigger = params.get("trigger_percent", 1.0)
            offset = params.get("offset", 0.0)  # Small offset above/below entry
            result["signal"] = input_signal
            result["breakeven_trigger"] = trigger
            result["breakeven_offset"] = offset

        elif action_type == "profit_lock":
            # Lock minimum profit after threshold
            trigger = params.get("trigger_percent", 2.0)
            lock = params.get("lock_percent", 1.0)
            result["signal"] = input_signal
            result["profit_lock_trigger"] = trigger
            result["profit_lock_amount"] = lock

        elif action_type == "scale_out":
            # Partial position close
            percent = params.get("close_percent", 50.0)
            at_profit = params.get("at_profit", 1.0)
            result["exit"] = input_signal
            result["signal"] = input_signal
            result["scale_out_percent"] = percent
            result["scale_out_at_profit"] = at_profit

        elif action_type == "multi_tp":
            # Multi take profit levels
            tp1 = params.get("tp1_percent", 1.0)
            tp1_close = params.get("tp1_close", 30.0)
            tp2 = params.get("tp2_percent", 2.0)
            tp2_close = params.get("tp2_close", 30.0)
            tp3 = params.get("tp3_percent", 3.0)
            tp3_close = params.get("tp3_close", 40.0)
            result["signal"] = input_signal
            result["multi_tp_levels"] = [
                {"percent": tp1, "close": tp1_close},
                {"percent": tp2, "close": tp2_close},
                {"percent": tp3, "close": tp3_close},
            ]

        elif action_type == "limit_entry":
            # Limit order entry at specific price
            price = params.get("price", 0)
            offset = params.get("offset_percent", 0)
            result["entry_long"] = input_signal
            result["signal"] = input_signal
            result["limit_price"] = price
            result["limit_offset"] = offset
            result["order_type"] = "limit"

        elif action_type == "stop_entry":
            # Stop order entry on breakout
            price = params.get("price", 0)
            offset = params.get("offset_percent", 0)
            result["entry_long"] = input_signal
            result["signal"] = input_signal
            result["stop_price"] = price
            result["stop_offset"] = offset
            result["order_type"] = "stop"

        elif action_type == "close":
            # Close current position (any direction)
            result["exit_long"] = input_signal
            result["exit_short"] = input_signal
            result["signal"] = input_signal

        else:
            result["signal"] = input_signal

        return result

    def _execute_exit(
        self, exit_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute exit condition blocks.

        Exit blocks generate exit signals based on price conditions or indicators.

        Supported exit types:
            - tp_percent, sl_percent: Fixed % take profit / stop loss
            - trailing_stop_exit: Trailing stop
            - atr_stop, atr_tp: ATR-based exits
            - time_exit: Exit after N bars
            - breakeven_exit: Move stop to breakeven
            - chandelier_exit: Chandelier exit
        """
        n = len(ohlcv)
        result: dict[str, pd.Series] = {}

        if exit_type == "tp_percent":
            # Take profit is handled by engine config, return empty
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        elif exit_type == "sl_percent":
            # Stop loss is handled by engine config, return empty
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        elif exit_type == "trailing_stop_exit":
            # Trailing stop is handled by engine
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        elif exit_type == "atr_stop":
            # ATR-based stop loss
            period = params.get("period", 14)
            multiplier = params.get("multiplier", 2.0)
            atr = calculate_atr(ohlcv, period=period)
            # Exit signal: price breaks below entry - ATR*multiplier
            # This needs position tracking, return empty for now
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["atr"] = atr

        elif exit_type == "time_exit":
            # Exit after N bars - needs position tracking
            bars = params.get("bars", 10)
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["max_bars"] = pd.Series([bars] * n, index=ohlcv.index)

        elif exit_type in ("breakeven_exit", "break_even_exit"):
            # Move to breakeven after X% profit
            trigger_pct = params.get("trigger_percent", 1.0)
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["breakeven_trigger"] = trigger_pct

        elif exit_type == "chandelier_exit":
            # Chandelier exit - ATR-based trailing
            period = params.get("period", 22)
            multiplier = params.get("multiplier", 3.0)
            atr = calculate_atr(ohlcv, period=period)
            high_n = ohlcv["high"].rolling(period).max()
            low_n = ohlcv["low"].rolling(period).min()

            # Long exit: close below highest high - ATR*mult
            long_exit_level = high_n - atr * multiplier
            # Short exit: close above lowest low + ATR*mult
            short_exit_level = low_n + atr * multiplier

            result["exit_long"] = ohlcv["close"] < long_exit_level
            result["exit_short"] = ohlcv["close"] > short_exit_level
            result["exit"] = result["exit_long"] | result["exit_short"]

        elif exit_type == "atr_exit":
            # ATR-based TP/SL exit
            period = params.get("period", params.get("atr_period", 14))
            sl_mult = params.get("sl_multiplier", 2.0)
            tp_mult = params.get("tp_multiplier", 3.0)
            atr = pd.Series(
                calculate_atr(
                    ohlcv["high"].values,
                    ohlcv["low"].values,
                    ohlcv["close"].values,
                    period=period,
                ),
                index=ohlcv.index,
            )
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["atr"] = atr
            result["atr_sl_mult"] = sl_mult
            result["atr_tp_mult"] = tp_mult

        elif exit_type == "session_exit":
            # Exit at session end (specific hour)
            exit_hour = params.get("exit_hour", 21)
            idx = ohlcv.index
            hours = idx.hour if hasattr(idx, "hour") else pd.to_datetime(idx).hour
            at_session_end = hours == exit_hour
            result["exit"] = pd.Series(at_session_end, index=ohlcv.index)

        elif exit_type == "signal_exit":
            # Exit on opposite signal (reverse of entry)
            # This is handled by engine logic, return empty
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["signal_exit_mode"] = True

        elif exit_type == "indicator_exit":
            # Exit on indicator condition - generic
            indicator = params.get("indicator", "rsi")
            threshold = params.get("threshold", 50)
            mode = params.get("mode", "above")  # above, below, cross_above, cross_below

            if indicator == "rsi":
                ind_val = pd.Series(calculate_rsi(ohlcv["close"].values, 14), index=ohlcv.index)
            else:
                ind_val = pd.Series(calculate_rsi(ohlcv["close"].values, 14), index=ohlcv.index)

            if mode == "above":
                exit_signal = ind_val > threshold
            elif mode == "below":
                exit_signal = ind_val < threshold
            elif mode == "cross_above":
                exit_signal = (ind_val > threshold) & (ind_val.shift(1) <= threshold)
            else:  # cross_below
                exit_signal = (ind_val < threshold) & (ind_val.shift(1) >= threshold)

            result["exit"] = exit_signal.fillna(False)

        elif exit_type == "partial_close":
            # Partial close at targets
            targets = params.get("targets", [{"profit": 1.0, "close_pct": 50}])
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["partial_targets"] = targets

        elif exit_type == "multi_tp_exit":
            # Multi TP levels with % allocation
            tp1 = params.get("tp1_percent", 1.0)
            tp1_alloc = params.get("tp1_allocation", 30)
            tp2 = params.get("tp2_percent", 2.0)
            tp2_alloc = params.get("tp2_allocation", 30)
            tp3 = params.get("tp3_percent", 3.0)
            tp3_alloc = params.get("tp3_allocation", 40)
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)
            result["multi_tp_config"] = [
                {"percent": tp1, "allocation": tp1_alloc},
                {"percent": tp2, "allocation": tp2_alloc},
                {"percent": tp3, "allocation": tp3_alloc},
            ]

        else:
            result["exit"] = pd.Series([False] * n, index=ohlcv.index)

        return result

    def _execute_position_sizing(self, sizing_type: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute position sizing blocks.

        Sizing blocks are config-only and return sizing parameters.

        Supported sizing types:
            - fixed_size: Fixed position size
            - percent_equity: % of equity
            - risk_based: Risk % per trade
            - kelly_criterion: Kelly formula
            - volatility_sized: ATR-based sizing
        """
        result: dict[str, Any] = {}

        if sizing_type == "fixed_size":
            result["size"] = params.get("size", 1.0)
            result["sizing_mode"] = "fixed"

        elif sizing_type == "percent_equity":
            result["equity_percent"] = params.get("percent", 10.0)
            result["sizing_mode"] = "percent"

        elif sizing_type == "risk_based":
            result["risk_percent"] = params.get("risk_percent", 1.0)
            result["sizing_mode"] = "risk"

        elif sizing_type == "kelly_criterion":
            result["kelly_fraction"] = params.get("fraction", 0.5)
            result["sizing_mode"] = "kelly"

        elif sizing_type == "volatility_sized":
            result["atr_period"] = params.get("period", 14)
            result["target_risk"] = params.get("target_risk", 1.0)
            result["sizing_mode"] = "volatility"

        return result

    def _execute_time_filter(self, time_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute time-based filter blocks.

        Time filters return boolean series based on time conditions.

        Supported time filter types:
            - trading_hours: Filter by time of day
            - trading_days: Filter by day of week
            - session_filter: Trading sessions (Asia, London, NY)
            - date_range: Filter by date range
            - exclude_news: Avoid news times
        """
        n = len(ohlcv)
        idx = ohlcv.index
        result: dict[str, pd.Series] = {}

        if time_type == "trading_hours":
            start_hour = params.get("start_hour", 9)
            end_hour = params.get("end_hour", 17)

            if hasattr(idx, "hour"):
                hours = idx.hour
            else:
                hours = pd.to_datetime(idx).hour

            result["allow"] = pd.Series((hours >= start_hour) & (hours < end_hour), index=idx)

        elif time_type == "trading_days":
            allowed_days = params.get("days", [0, 1, 2, 3, 4])  # Mon-Fri

            if hasattr(idx, "dayofweek"):
                dow = idx.dayofweek
            else:
                dow = pd.to_datetime(idx).dayofweek

            result["allow"] = pd.Series([d in allowed_days for d in dow], index=idx)

        elif time_type == "session_filter":
            session = params.get("session", "all")

            if hasattr(idx, "hour"):
                hours = idx.hour
            else:
                hours = pd.to_datetime(idx).hour

            if session == "asia":
                # Asia session: 00:00 - 09:00 UTC
                result["allow"] = pd.Series((hours >= 0) & (hours < 9), index=idx)
            elif session == "london":
                # London session: 08:00 - 17:00 UTC
                result["allow"] = pd.Series((hours >= 8) & (hours < 17), index=idx)
            elif session == "ny":
                # NY session: 13:00 - 22:00 UTC
                result["allow"] = pd.Series((hours >= 13) & (hours < 22), index=idx)
            else:
                result["allow"] = pd.Series([True] * n, index=idx)

        elif time_type == "date_range":
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            dates = pd.to_datetime(idx)
            allow = pd.Series([True] * n, index=idx)

            if start_date:
                allow = allow & (dates >= pd.to_datetime(start_date))
            if end_date:
                allow = allow & (dates <= pd.to_datetime(end_date))

            result["allow"] = allow

        else:
            result["allow"] = pd.Series([True] * n, index=idx)

        return result

    def _execute_price_action(
        self, pattern_type: str, params: dict[str, Any], ohlcv: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """
        Execute price action pattern detection blocks.

        Returns signals when specific candlestick patterns are detected.

        Supported pattern types:
            - engulfing: Bullish/bearish engulfing
            - hammer: Hammer/hanging man
            - doji: Doji patterns
            - pin_bar: Pin bar / rejection
            - inside_bar: Inside bar
            - outside_bar: Outside bar
            - three_white_soldiers: 3 white soldiers / black crows
            - morning_star: Morning/evening star
        """
        n = len(ohlcv)
        idx = ohlcv.index
        result: dict[str, pd.Series] = {}

        o = ohlcv["open"]
        h = ohlcv["high"]
        l = ohlcv["low"]
        c = ohlcv["close"]
        body = abs(c - o)
        upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
        lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l

        if pattern_type == "engulfing":
            # Bullish engulfing: prev red, current green, current body > prev body
            prev_red = o.shift(1) > c.shift(1)
            curr_green = c > o
            engulfs = (c > o.shift(1)) & (o < c.shift(1))
            bullish = prev_red & curr_green & engulfs

            prev_green = c.shift(1) > o.shift(1)
            curr_red = o > c
            engulfs_bear = (o > c.shift(1)) & (c < o.shift(1))
            bearish = prev_green & curr_red & engulfs_bear

            result["bullish"] = bullish.fillna(False)
            result["bearish"] = bearish.fillna(False)
            result["signal"] = bullish.fillna(False)

        elif pattern_type == "hammer":
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_upper_ratio = params.get("max_upper_ratio", 0.3)

            hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
            hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

            result["hammer"] = hammer.fillna(False)
            result["hanging_man"] = hanging.fillna(False)
            result["signal"] = hammer.fillna(False)

        elif pattern_type == "doji":
            threshold = params.get("body_threshold", 0.1)
            avg_range = (h - l).rolling(20).mean()

            doji = body < avg_range * threshold
            result["doji"] = doji.fillna(False)
            result["signal"] = doji.fillna(False)

        elif pattern_type == "pin_bar":
            min_wick = params.get("min_wick_ratio", 2.0)

            # Bullish pin: long lower wick
            bull_pin = (lower_wick > body * min_wick) & (lower_wick > upper_wick * 2)
            # Bearish pin: long upper wick
            bear_pin = (upper_wick > body * min_wick) & (upper_wick > lower_wick * 2)

            result["bullish"] = bull_pin.fillna(False)
            result["bearish"] = bear_pin.fillna(False)
            result["signal"] = bull_pin.fillna(False)

        elif pattern_type == "inside_bar":
            # Current bar inside previous bar
            inside = (h <= h.shift(1)) & (l >= l.shift(1))
            result["inside"] = inside.fillna(False)
            result["signal"] = inside.fillna(False)

        elif pattern_type == "outside_bar":
            # Current bar engulfs previous bar
            outside = (h > h.shift(1)) & (l < l.shift(1))
            result["outside"] = outside.fillna(False)
            result["signal"] = outside.fillna(False)

        elif pattern_type == "three_white_soldiers":
            # 3 consecutive bullish bars with higher closes
            green = c > o
            three_green = green & green.shift(1) & green.shift(2)
            higher_close = (c > c.shift(1)) & (c.shift(1) > c.shift(2))

            soldiers = three_green & higher_close

            # 3 black crows
            red = o > c
            three_red = red & red.shift(1) & red.shift(2)
            lower_close = (c < c.shift(1)) & (c.shift(1) < c.shift(2))
            crows = three_red & lower_close

            result["soldiers"] = soldiers.fillna(False)
            result["crows"] = crows.fillna(False)
            result["signal"] = soldiers.fillna(False)

        elif pattern_type == "hammer_hangman":
            # Hammer (bullish) and Hanging Man (bearish) patterns
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_upper_ratio = params.get("max_upper_ratio", 0.3)

            hammer = (lower_wick > body * min_wick_ratio) & (upper_wick < body * max_upper_ratio)
            hanging = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_upper_ratio)

            result["bullish"] = hammer.fillna(False)
            result["bearish"] = hanging.fillna(False)
            result["signal"] = hammer.fillna(False)

        elif pattern_type == "doji_patterns":
            # Multiple doji types: standard, dragonfly, gravestone
            threshold = params.get("body_threshold", 0.1)
            avg_range = (h - l).rolling(20).mean()

            small_body = body < avg_range * threshold
            # Dragonfly doji: small body at top, long lower wick
            dragonfly = small_body & (lower_wick > body * 3) & (upper_wick < body)
            # Gravestone doji: small body at bottom, long upper wick
            gravestone = small_body & (upper_wick > body * 3) & (lower_wick < body)
            # Standard doji
            standard_doji = small_body & ~dragonfly & ~gravestone

            result["doji"] = small_body.fillna(False)
            result["dragonfly"] = dragonfly.fillna(False)
            result["gravestone"] = gravestone.fillna(False)
            result["bullish"] = dragonfly.fillna(False)  # Dragonfly is bullish
            result["bearish"] = gravestone.fillna(False)  # Gravestone is bearish
            result["signal"] = small_body.fillna(False)

        elif pattern_type == "shooting_star":
            # Shooting star: small body at bottom, long upper wick (bearish)
            min_wick_ratio = params.get("min_wick_ratio", 2.0)
            max_lower_ratio = params.get("max_lower_ratio", 0.3)

            shooting = (upper_wick > body * min_wick_ratio) & (lower_wick < body * max_lower_ratio)
            # Only valid if after uptrend
            uptrend = c.shift(1) > c.shift(3)
            valid_shooting = shooting & uptrend

            result["bearish"] = valid_shooting.fillna(False)
            result["bullish"] = pd.Series([False] * n, index=idx)
            result["signal"] = valid_shooting.fillna(False)

        elif pattern_type == "marubozu":
            # Marubozu: strong momentum candle with no/tiny wicks
            max_wick_ratio = params.get("max_wick_ratio", 0.1)

            tiny_wicks = (upper_wick < body * max_wick_ratio) & (lower_wick < body * max_wick_ratio)
            bullish_marubozu = tiny_wicks & (c > o)
            bearish_marubozu = tiny_wicks & (o > c)

            result["bullish"] = bullish_marubozu.fillna(False)
            result["bearish"] = bearish_marubozu.fillna(False)
            result["signal"] = bullish_marubozu.fillna(False)

        elif pattern_type == "tweezer":
            # Tweezer top/bottom: two candles with same high/low
            tolerance = params.get("tolerance", 0.001)

            # Tweezer bottom: same lows, first red then green
            same_low = abs(l - l.shift(1)) < (l * tolerance)
            first_red = o.shift(1) > c.shift(1)
            second_green = c > o
            tweezer_bottom = same_low & first_red & second_green

            # Tweezer top: same highs, first green then red
            same_high = abs(h - h.shift(1)) < (h * tolerance)
            first_green = c.shift(1) > o.shift(1)
            second_red = o > c
            tweezer_top = same_high & first_green & second_red

            result["bullish"] = tweezer_bottom.fillna(False)
            result["bearish"] = tweezer_top.fillna(False)
            result["signal"] = tweezer_bottom.fillna(False)

        elif pattern_type == "three_methods":
            # Rising/Falling three methods (continuation patterns)
            green = c > o
            red = o > c

            # Rising three methods: big green, 3 small reds inside, big green
            big_green_1 = green.shift(4) & (body.shift(4) > body.shift(4).rolling(10).mean())
            small_reds = red.shift(3) & red.shift(2) & red.shift(1)
            contained = (l.shift(1) > l.shift(4)) & (h.shift(1) < h.shift(4))
            big_green_2 = green & (c > h.shift(4))
            rising_three = big_green_1 & small_reds & contained & big_green_2

            # Falling three methods: opposite
            big_red_1 = red.shift(4) & (body.shift(4) > body.shift(4).rolling(10).mean())
            small_greens = green.shift(3) & green.shift(2) & green.shift(1)
            contained_fall = (h.shift(1) < h.shift(4)) & (l.shift(1) > l.shift(4))
            big_red_2 = red & (c < l.shift(4))
            falling_three = big_red_1 & small_greens & contained_fall & big_red_2

            result["bullish"] = rising_three.fillna(False)
            result["bearish"] = falling_three.fillna(False)
            result["signal"] = rising_three.fillna(False)

        elif pattern_type == "piercing_darkcloud":
            # Piercing line (bullish) and Dark cloud cover (bearish)

            # Piercing line: red candle, then green opens below prev low, closes above midpoint
            prev_red = o.shift(1) > c.shift(1)
            curr_green = c > o
            opens_below = o < l.shift(1)
            closes_above_mid = c > (o.shift(1) + c.shift(1)) / 2
            piercing = prev_red & curr_green & opens_below & closes_above_mid

            # Dark cloud: green candle, then red opens above prev high, closes below midpoint
            prev_green = c.shift(1) > o.shift(1)
            curr_red = o > c
            opens_above = o > h.shift(1)
            closes_below_mid = c < (o.shift(1) + c.shift(1)) / 2
            dark_cloud = prev_green & curr_red & opens_above & closes_below_mid

            result["bullish"] = piercing.fillna(False)
            result["bearish"] = dark_cloud.fillna(False)
            result["signal"] = piercing.fillna(False)

        elif pattern_type == "harami":
            # Harami (inside bar reversal)

            # Bullish harami: big red, then small green inside
            big_red = (o.shift(1) > c.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
            small_green = (c > o) & (body < body.shift(1) * 0.5)
            inside_prev = (o > c.shift(1)) & (c < o.shift(1))
            bullish_harami = big_red & small_green & inside_prev

            # Bearish harami: big green, then small red inside
            big_green = (c.shift(1) > o.shift(1)) & (body.shift(1) > body.shift(1).rolling(10).mean())
            small_red = (o > c) & (body < body.shift(1) * 0.5)
            inside_prev_bear = (o < c.shift(1)) & (c > o.shift(1))
            bearish_harami = big_green & small_red & inside_prev_bear

            result["bullish"] = bullish_harami.fillna(False)
            result["bearish"] = bearish_harami.fillna(False)
            result["signal"] = bullish_harami.fillna(False)

        else:
            result["signal"] = pd.Series([False] * n, index=idx)

        return result

    def _execute_divergence(self, div_type: str, params: dict[str, Any], ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Execute divergence detection blocks.

        Detects divergences between price and indicators.

        Supported divergence types:
            - rsi_divergence: RSI divergence
            - macd_divergence: MACD divergence
            - cci_divergence: CCI divergence
            - obv_divergence: OBV divergence
        """
        n = len(ohlcv)
        idx = ohlcv.index
        result: dict[str, pd.Series] = {}

        lookback = params.get("lookback", 14)

        # Get price highs/lows as Series
        close = ohlcv["close"]
        high = ohlcv["high"]
        low = ohlcv["low"]

        if div_type == "rsi_divergence":
            period = params.get("period", 14)
            rsi = pd.Series(calculate_rsi(close.values, period=period), index=idx)

            # Bullish divergence: price makes lower low, RSI makes higher low
            price_lower_low = low < low.shift(lookback)
            rsi_higher_low = rsi > rsi.shift(lookback)
            bullish_div = price_lower_low & rsi_higher_low

            # Bearish divergence: price makes higher high, RSI makes lower high
            price_higher_high = high > high.shift(lookback)
            rsi_lower_high = rsi < rsi.shift(lookback)
            bearish_div = price_higher_high & rsi_lower_high

            result["bullish"] = bullish_div.fillna(False)
            result["bearish"] = bearish_div.fillna(False)
            result["signal"] = bullish_div.fillna(False)

        elif div_type == "macd_divergence":
            fast = params.get("fast_period", 12)
            slow = params.get("slow_period", 26)
            signal_period = params.get("signal_period", 9)

            _macd_line, _signal_line, hist = calculate_macd(close.values, fast, slow, signal_period)
            histogram = pd.Series(hist, index=idx)

            price_lower_low = low < low.shift(lookback)
            macd_higher_low = histogram > histogram.shift(lookback)
            bullish_div = price_lower_low & macd_higher_low

            price_higher_high = high > high.shift(lookback)
            macd_lower_high = histogram < histogram.shift(lookback)
            bearish_div = price_higher_high & macd_lower_high

            result["bullish"] = bullish_div.fillna(False)
            result["bearish"] = bearish_div.fillna(False)
            result["signal"] = bullish_div.fillna(False)

        elif div_type == "obv_divergence":
            obv = pd.Series(calculate_obv(ohlcv), index=idx)

            price_lower_low = low < low.shift(lookback)
            obv_higher_low = obv > obv.shift(lookback)
            bullish_div = price_lower_low & obv_higher_low

            price_higher_high = high > high.shift(lookback)
            obv_lower_high = obv < obv.shift(lookback)
            bearish_div = price_higher_high & obv_lower_high

            result["bullish"] = bullish_div.fillna(False)
            result["bearish"] = bearish_div.fillna(False)
            result["signal"] = bullish_div.fillna(False)

        elif div_type == "stoch_divergence":
            # Stochastic divergence
            k_period = params.get("k_period", 14)
            d_period = params.get("d_period", 3)

            k_arr, _d_arr = calculate_stochastic(high.values, low.values, close.values, k_period, d_period)
            stoch_k = pd.Series(k_arr, index=idx)

            price_lower_low = low < low.shift(lookback)
            stoch_higher_low = stoch_k > stoch_k.shift(lookback)
            bullish_div = price_lower_low & stoch_higher_low

            price_higher_high = high > high.shift(lookback)
            stoch_lower_high = stoch_k < stoch_k.shift(lookback)
            bearish_div = price_higher_high & stoch_lower_high

            result["bullish"] = bullish_div.fillna(False)
            result["bearish"] = bearish_div.fillna(False)
            result["signal"] = bullish_div.fillna(False)

        elif div_type == "mfi_divergence":
            # Money Flow Index divergence
            period = params.get("period", 14)

            mfi = pd.Series(
                calculate_mfi(high.values, low.values, close.values, ohlcv["volume"].values, period=period),
                index=idx,
            )

            price_lower_low = low < low.shift(lookback)
            mfi_higher_low = mfi > mfi.shift(lookback)
            bullish_div = price_lower_low & mfi_higher_low

            price_higher_high = high > high.shift(lookback)
            mfi_lower_high = mfi < mfi.shift(lookback)
            bearish_div = price_higher_high & mfi_lower_high

            result["bullish"] = bullish_div.fillna(False)
            result["bearish"] = bearish_div.fillna(False)
            result["signal"] = bullish_div.fillna(False)

        else:
            result["signal"] = pd.Series([False] * n, index=idx)
            result["bullish"] = pd.Series([False] * n, index=idx)
            result["bearish"] = pd.Series([False] * n, index=idx)

        return result

    def _execute_close_condition(
        self, close_type: str, params: dict[str, Any], ohlcv: pd.DataFrame, inputs: dict[str, pd.Series]
    ) -> dict[str, pd.Series]:
        """
        Execute close condition blocks from frontend close_conditions category.

        These blocks define when to close positions based on indicators or time.

        Supported close types:
            - close_by_time: Close after N bars
            - close_rsi_reach: Close when RSI reaches level
            - close_rsi_cross: Close when RSI crosses level
            - close_stoch_reach: Close when Stochastic reaches level
            - close_stoch_cross: Close when Stochastic crosses level
            - close_channel_break: Close on Keltner/BB breakout
            - close_ma_cross: Close on MA1/MA2 cross
            - close_psar: Close on Parabolic SAR signal
            - close_profit_only: Require minimum profit to close
        """
        n = len(ohlcv)
        idx = ohlcv.index
        close = ohlcv["close"]
        result: dict[str, pd.Series] = {}

        if close_type == "close_by_time":
            # Close after N bars since entry - needs position tracking
            bars = params.get("bars", 10)
            # Return config, actual implementation in engine
            result["exit"] = pd.Series([False] * n, index=idx)
            result["max_bars"] = pd.Series([bars] * n, index=idx)

        elif close_type == "close_rsi_reach":
            # Close when RSI reaches level
            period = params.get("period", 14)
            level = params.get("level", 70)
            direction = params.get("direction", "above")  # above or below

            rsi = calculate_rsi(close, period=period)

            if direction == "above":
                result["exit"] = rsi >= level
            else:
                result["exit"] = rsi <= level
            result["signal"] = result["exit"]

        elif close_type == "close_rsi_cross":
            # Close when RSI crosses level
            period = params.get("period", 14)
            level = params.get("level", 50)
            cross_type = params.get("cross_type", "above")  # above or below

            rsi = calculate_rsi(close, period=period)

            if cross_type == "above":
                # Cross above level
                result["exit"] = (rsi > level) & (rsi.shift(1) <= level)
            else:
                # Cross below level
                result["exit"] = (rsi < level) & (rsi.shift(1) >= level)
            result["signal"] = result["exit"].fillna(False)

        elif close_type == "close_stoch_reach":
            # Close when Stochastic reaches level
            k_period = params.get("k_period", 14)
            d_period = params.get("d_period", 3)
            level = params.get("level", 80)
            direction = params.get("direction", "above")

            stoch_k, stoch_d = calculate_stochastic(ohlcv, k_period=k_period, d_period=d_period)

            if direction == "above":
                result["exit"] = stoch_k >= level
            else:
                result["exit"] = stoch_k <= level
            result["signal"] = result["exit"]

        elif close_type == "close_stoch_cross":
            # Close when Stochastic K crosses D
            k_period = params.get("k_period", 14)
            d_period = params.get("d_period", 3)
            cross_type = params.get("cross_type", "k_above_d")

            stoch_k, stoch_d = calculate_stochastic(ohlcv, k_period=k_period, d_period=d_period)

            if cross_type == "k_above_d":
                result["exit"] = (stoch_k > stoch_d) & (stoch_k.shift(1) <= stoch_d.shift(1))
            else:
                result["exit"] = (stoch_k < stoch_d) & (stoch_k.shift(1) >= stoch_d.shift(1))
            result["signal"] = result["exit"].fillna(False)

        elif close_type == "close_channel_break":
            # Close on Keltner/BB breakout
            channel = params.get("channel", "keltner")
            period = params.get("period", 20)
            multiplier = params.get("multiplier", 2.0)
            break_type = params.get("break_type", "above")  # above or below

            if channel == "keltner":
                upper, middle, lower = calculate_keltner(ohlcv, period=period, multiplier=multiplier)
            else:
                # Bollinger bands - use stddev
                middle = close.rolling(period).mean()
                std = close.rolling(period).std()
                upper = middle + multiplier * std
                lower = middle - multiplier * std

            if break_type == "above":
                result["exit"] = close > upper
            else:
                result["exit"] = close < lower
            result["signal"] = result["exit"].fillna(False)

        elif close_type == "close_ma_cross":
            # Close on MA1/MA2 cross
            fast_period = params.get("fast_period", 9)
            slow_period = params.get("slow_period", 21)
            ma_type = params.get("ma_type", "ema")
            cross_type = params.get("cross_type", "fast_below")

            if ma_type == "ema":
                fast_ma = close.ewm(span=fast_period, adjust=False).mean()
                slow_ma = close.ewm(span=slow_period, adjust=False).mean()
            else:
                fast_ma = close.rolling(fast_period).mean()
                slow_ma = close.rolling(slow_period).mean()

            if cross_type == "fast_below":
                # Fast MA crosses below slow MA
                result["exit"] = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
            else:
                # Fast MA crosses above slow MA
                result["exit"] = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            result["signal"] = result["exit"].fillna(False)

        elif close_type == "close_psar":
            # Close on Parabolic SAR signal
            af_start = _param(params, 0.02, "af_start", "start", "afStart")
            af_step = _param(params, 0.02, "af_step", "increment", "afStep")
            af_max = _param(params, 0.2, "af_max", "max_value", "afMax")

            psar = calculate_parabolic_sar(ohlcv, af_start=af_start, af_step=af_step, af_max=af_max)

            # Long exit: price crosses below PSAR
            long_exit = (close < psar) & (close.shift(1) >= psar.shift(1))
            # Short exit: price crosses above PSAR
            short_exit = (close > psar) & (close.shift(1) <= psar.shift(1))

            result["exit_long"] = long_exit.fillna(False)
            result["exit_short"] = short_exit.fillna(False)
            result["exit"] = (long_exit | short_exit).fillna(False)
            result["signal"] = result["exit"]

        elif close_type == "close_profit_only":
            # Require minimum profit to close - needs position tracking
            min_profit = params.get("min_profit_percent", 0.5)
            # This is config-only, actual logic in engine
            result["exit"] = pd.Series([False] * n, index=idx)
            result["min_profit"] = pd.Series([min_profit] * n, index=idx)

        else:
            result["exit"] = pd.Series([False] * n, index=idx)
            result["signal"] = pd.Series([False] * n, index=idx)

        return result

    def _execute_dca_block(self, block_type: str, params: dict[str, Any]) -> dict[str, pd.Series]:
        """
        Process DCA/Grid configuration blocks.

        DCA blocks are configuration-only and don't produce signal outputs.
        Their parameters are collected by extract_dca_config() for BacktestConfig.

        Supported block types:
            - dca_grid_enable: Master enable switch
            - dca_grid_settings: Grid order count and size
            - dca_martingale_config: Martingale coefficient settings
            - dca_log_steps: Logarithmic step distribution
            - dca_dynamic_tp: Multi-level take profit
            - dca_safety_close: Safety close on drawdown
        """
        # DCA blocks are config-only, no signal outputs
        # They're processed via extract_dca_config()
        return {}

    def extract_dca_config(self) -> dict[str, Any]:
        """
        Extract DCA Grid configuration from strategy blocks.

        Scans all blocks with category="dca_grid" or "multiple_tp" and
        assembles a configuration dictionary compatible with BacktestConfig.

        Returns:
            Dictionary with DCA configuration fields:
                - dca_enabled: bool
                - dca_direction: str
                - dca_order_count: int
                - dca_grid_size_percent: float
                - dca_martingale_coef: float
                - dca_martingale_mode: str
                - dca_log_step_enabled: bool
                - dca_log_step_coef: float
                - dca_drawdown_threshold: float
                - dca_safety_close_enabled: bool
                - dca_multi_tp_enabled: bool
                - dca_tp{1-4}_percent: float
                - dca_tp{1-4}_close_percent: float
        """
        dca_config: dict[str, Any] = {
            "dca_enabled": False,
            "dca_direction": "both",
            "dca_order_count": 5,
            "dca_grid_size_percent": 1.0,
            "dca_martingale_coef": 1.5,
            "dca_martingale_mode": "multiply_each",
            "dca_log_step_enabled": False,
            "dca_log_step_coef": 1.2,
            "dca_drawdown_threshold": 30.0,
            "dca_safety_close_enabled": True,
            "dca_multi_tp_enabled": False,
            "dca_tp1_percent": 0.5,
            "dca_tp1_close_percent": 25.0,
            "dca_tp2_percent": 1.0,
            "dca_tp2_close_percent": 25.0,
            "dca_tp3_percent": 2.0,
            "dca_tp3_close_percent": 25.0,
            "dca_tp4_percent": 3.0,
            "dca_tp4_close_percent": 25.0,
        }

        for block_id, block in self.blocks.items():
            category = block.get("category", "")
            block_type = block.get("type", "")
            params = block.get("params", {})

            if category == "dca_grid":
                if block_type == "dca_grid_enable":
                    dca_config["dca_enabled"] = params.get("enabled", True)
                    dca_config["dca_direction"] = params.get("direction", "both")

                elif block_type == "dca_grid_settings":
                    dca_config["dca_order_count"] = params.get("order_count", 5)
                    dca_config["dca_grid_size_percent"] = params.get("grid_size_percent", 1.0)

                elif block_type == "dca_martingale_config":
                    dca_config["dca_martingale_coef"] = params.get("martingale_coef", 1.5)
                    dca_config["dca_martingale_mode"] = params.get("martingale_mode", "multiply_each")

                elif block_type == "dca_log_steps":
                    dca_config["dca_log_step_enabled"] = params.get("enabled", False)
                    dca_config["dca_log_step_coef"] = params.get("log_step_coef", 1.2)

                elif block_type == "dca_safety_close":
                    dca_config["dca_safety_close_enabled"] = params.get("enabled", True)
                    dca_config["dca_drawdown_threshold"] = params.get("drawdown_threshold", 30.0)

                elif block_type == "dca_dynamic_tp":
                    dca_config["dca_multi_tp_enabled"] = params.get("enabled", False)

            elif category == "multiple_tp":
                if block_type == "multi_tp_levels":
                    dca_config["dca_multi_tp_enabled"] = True
                    levels = params.get("levels", [])
                    for i, level in enumerate(levels[:4], start=1):
                        dca_config[f"dca_tp{i}_percent"] = level.get("percent", i * 0.5)
                        dca_config[f"dca_tp{i}_close_percent"] = level.get("close_percent", 25.0)

        # Close Conditions (Session 5.5): extract from exit blocks
        close_conditions: dict[str, Any] = {}
        for block_id, block in self.blocks.items():
            block_type = block.get("type", "")
            params = block.get("params", {})
            if block_type == "rsi_close":
                close_conditions["rsi_close_enable"] = True
                close_conditions["rsi_close_length"] = params.get("rsi_close_length", 14)
                close_conditions["rsi_close_only_profit"] = params.get("rsi_close_only_profit", True)
                close_conditions["rsi_close_min_profit"] = params.get("rsi_close_min_profit", 0.5)
                close_conditions["rsi_close_reach_enable"] = params.get("rsi_close_reach_enable", False)
                close_conditions["rsi_close_reach_long_more"] = params.get("rsi_close_reach_long_more", 70)
                close_conditions["rsi_close_reach_long_less"] = params.get("rsi_close_reach_long_less", 0)
                close_conditions["rsi_close_reach_short_more"] = params.get("rsi_close_reach_short_more", 100)
                close_conditions["rsi_close_reach_short_less"] = params.get("rsi_close_reach_short_less", 30)
                close_conditions["rsi_close_cross_enable"] = params.get("rsi_close_cross_enable", False)
                close_conditions["rsi_close_cross_long_level"] = params.get("rsi_close_cross_long_level", 70)
                close_conditions["rsi_close_cross_short_level"] = params.get("rsi_close_cross_short_level", 30)
            elif block_type == "stoch_close":
                close_conditions["stoch_close_enable"] = True
                close_conditions["stoch_close_k_length"] = params.get("stoch_close_k_length", 14)
                close_conditions["stoch_close_k_smooth"] = params.get("stoch_close_k_smooth", 1)
                close_conditions["stoch_close_d_smooth"] = params.get("stoch_close_d_smooth", 3)
                close_conditions["stoch_close_only_profit"] = params.get("stoch_close_only_profit", True)
                close_conditions["stoch_close_min_profit"] = params.get("stoch_close_min_profit", 0.5)
                close_conditions["stoch_close_reach_enable"] = params.get("stoch_close_reach_enable", False)
                close_conditions["stoch_close_reach_long_more"] = params.get("stoch_close_reach_long_more", 80)
                close_conditions["stoch_close_reach_short_less"] = params.get("stoch_close_reach_short_less", 20)
            elif block_type == "channel_close":
                close_conditions["channel_close_enable"] = True
                close_conditions["channel_close_type"] = params.get("channel_close_type", "Keltner")
                close_conditions["channel_close_band"] = params.get("channel_close_band", "Breakout")
                close_conditions["channel_close_keltner_length"] = params.get("channel_close_keltner_length", 20)
                close_conditions["channel_close_keltner_mult"] = params.get("channel_close_keltner_mult", 2.0)
                close_conditions["channel_close_bb_length"] = params.get("channel_close_bb_length", 20)
                close_conditions["channel_close_bb_deviation"] = params.get("channel_close_bb_deviation", 2.0)
            elif block_type == "ma_close":
                close_conditions["ma_close_enable"] = True
                close_conditions["ma_close_only_profit"] = params.get("ma_close_only_profit", True)
                close_conditions["ma_close_min_profit"] = params.get("ma_close_min_profit", 0.5)
                close_conditions["ma_close_ma1_length"] = params.get("ma_close_ma1_length", 9)
                close_conditions["ma_close_ma1_type"] = params.get("ma_close_ma1_type", "EMA")
                close_conditions["ma_close_ma2_length"] = params.get("ma_close_ma2_length", 21)
                close_conditions["ma_close_ma2_type"] = params.get("ma_close_ma2_type", "EMA")
            elif block_type == "psar_close":
                close_conditions["psar_close_enable"] = True
                close_conditions["psar_close_only_profit"] = params.get("psar_close_only_profit", True)
                close_conditions["psar_close_min_profit"] = params.get("psar_close_min_profit", 0.5)
                close_conditions["psar_close_start"] = params.get("psar_close_start", 0.02)
                close_conditions["psar_close_increment"] = params.get("psar_close_increment", 0.02)
                close_conditions["psar_close_maximum"] = params.get("psar_close_maximum", 0.2)
            elif block_type == "time_bars_close":
                close_conditions["time_bars_close_enable"] = True
                close_conditions["close_after_bars"] = params.get("close_after_bars", 20)
                close_conditions["close_only_profit"] = params.get("close_only_profit", True)
                close_conditions["close_min_profit"] = params.get("close_min_profit", 0.5)
                close_conditions["close_max_bars"] = params.get("close_max_bars", 100)

        # Indent Order (Session 5.5): extract from action block
        indent_order: dict[str, Any] = {}
        for block_id, block in self.blocks.items():
            block_type = block.get("type", "")
            params = block.get("params", {})
            if block_type == "indent_order":
                indent_order["enabled"] = params.get("indent_enable", True)
                indent_order["indent_percent"] = params.get("indent_percent", 0.1)
                indent_order["cancel_after_bars"] = params.get("indent_cancel_bars", 10)
                break

        dca_config["close_conditions"] = close_conditions
        dca_config["indent_order"] = indent_order
        return dca_config

    def has_dca_blocks(self) -> bool:
        """
        Check if strategy contains any DCA grid blocks.

        Returns:
            True if any block has category="dca_grid" and is enabled
        """
        for block in self.blocks.values():
            if block.get("category") == "dca_grid":
                block_type = block.get("type", "")
                if block_type == "dca_grid_enable":
                    params = block.get("params", {})
                    if params.get("enabled", True):
                        return True
        return False

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """
        Generate trading signals from OHLCV data by executing the strategy graph.

        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume
                   Index should be datetime

        Returns:
            SignalResult with entry/exit signals
        """
        # Clear cache
        self._value_cache.clear()

        # Execute blocks in order
        for block_id in self.execution_order:
            block = self.blocks[block_id]
            block_type = block.get("type")

            # Skip main strategy node (it doesn't produce outputs)
            if block_type == "strategy" or block.get("isMain"):
                continue

            # Execute block and cache outputs
            outputs = self._execute_block(block_id, ohlcv)
            self._value_cache[block_id] = outputs

        # Find main strategy node and collect entry/exit signals
        main_node_id = None
        for block_id, block in self.blocks.items():
            if block.get("type") == "strategy" or block.get("isMain"):
                main_node_id = block_id
                break

        # Initialize signals
        n = len(ohlcv)
        entries = pd.Series([False] * n, index=ohlcv.index)
        exits = pd.Series([False] * n, index=ohlcv.index)
        short_entries = pd.Series([False] * n, index=ohlcv.index)
        short_exits = pd.Series([False] * n, index=ohlcv.index)

        if main_node_id:
            # Collect signals connected to main node
            for conn in self.connections:
                target_id = self._get_connection_target_id(conn)
                if target_id == main_node_id:
                    source_id = self._get_connection_source_id(conn)
                    source_port = self._get_connection_source_port(conn)
                    target_port = self._get_connection_target_port(conn)

                    if source_id in self._value_cache:
                        source_outputs = self._value_cache[source_id]
                        if source_port in source_outputs:
                            signal = source_outputs[source_port]

                            # Map to appropriate signal series
                            if target_port == "entry_long":
                                entries = entries | signal
                            elif target_port == "exit_long":
                                exits = exits | signal
                            elif target_port == "entry_short":
                                short_entries = short_entries | signal
                            elif target_port == "exit_short":
                                short_exits = short_exits | signal

        return SignalResult(
            entries=entries,
            exits=exits,
            short_entries=short_entries,
            short_exits=short_exits,
        )

    @classmethod
    def get_default_params(cls) -> dict[str, Any]:
        """Get default parameters (not used for builder strategies)"""
        return {}

    def __repr__(self) -> str:
        return f"StrategyBuilderAdapter(name='{self.name}', blocks={len(self.blocks)}, connections={len(self.connections)})"
