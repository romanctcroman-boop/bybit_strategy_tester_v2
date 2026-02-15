"""
AI-Driven Backtest Executor

Integrates AI-generated trading strategies with the BacktestEngine.
Automatically applies AI recommendations and runs backtests.

Features:
- Apply AI-suggested features to trading strategies
- Convert AI strategy recommendations to executable backtest configs
- Run backtests with AI-optimized parameters
- Collect and analyze backtest results
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from backend.core.logging_config import get_logger
from backend.ml.ai_feature_engineer import AIFeatureEngineer

logger = get_logger(__name__)


@dataclass
class AIStrategy:
    """AI-generated trading strategy configuration"""

    name: str
    features: list[str]
    entry_long: list[str]
    entry_short: list[str]
    exit_long: dict[str, Any]  # take_profit, stop_loss, trailing_stop
    exit_short: dict[str, Any]
    position_sizing: dict[str, Any]
    risk_per_trade: float
    timeframe: str
    asset: str

    def to_backtest_config(self) -> dict[str, Any]:
        """Convert AI strategy to backtest configuration"""
        return {
            "name": self.name,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "indicators": self.features,
            "entry_long_conditions": self.entry_long,
            "entry_short_conditions": self.entry_short,
            "exit_long_rules": self.exit_long,
            "exit_short_rules": self.exit_short,
            "position_sizing": self.position_sizing,
            "risk_per_trade": self.risk_per_trade,
            "ai_generated": True,
            "generated_at": datetime.now(UTC).isoformat(),
        }


class AIBacktestExecutor:
    """
    Executes AI-generated trading strategies in backtests

    Workflow:
    1. Ask AI to design strategy for asset/timeframe
    2. AI suggests features and entry/exit rules
    3. Generate feature calculation code
    4. Create backtest configuration
    5. Run backtest with AI parameters
    6. Analyze results and get AI recommendations
    """

    def __init__(self):
        self.engineer = AIFeatureEngineer()
        self.backtest_results: list[dict[str, Any]] = []
        self.ai_strategies: list[AIStrategy] = []

    async def generate_ai_strategy(
        self,
        objective: str,
        asset: str = "BTC/USDT",
        timeframe: str = "1h",
        risk_tolerance: str = "medium",
    ) -> AIStrategy:
        """
        Generate complete AI strategy for backtesting

        Returns:
            AIStrategy object ready for backtesting
        """
        logger.info(f"🎯 Generating AI strategy for {asset} ({timeframe})")

        try:
            # Get AI strategy recommendation
            strategy_design = await self.engineer.suggest_complete_strategy(
                objective=objective,
                asset=asset,
                timeframe=timeframe,
                risk_tolerance=risk_tolerance,
            )

            # Parse strategy design
            if "error" in strategy_design:
                logger.error(f"AI strategy generation failed: {strategy_design['error']}")
                raise ValueError("Failed to generate AI strategy")

            # Extract components
            features = strategy_design.get("features", [])
            entry_conditions = strategy_design.get("entry_conditions", {})
            exit_conditions = strategy_design.get("exit_conditions", {})
            position_sizing = strategy_design.get("position_sizing", {})
            expected_metrics = strategy_design.get("expected_metrics", {})

            # Create AIStrategy object
            ai_strategy = AIStrategy(
                name=strategy_design.get("strategy_name", f"AI_Strategy_{asset}_{timeframe}"),
                features=features,
                entry_long=entry_conditions.get("long", []),
                entry_short=entry_conditions.get("short", []),
                exit_long=exit_conditions,
                exit_short=exit_conditions,
                position_sizing=position_sizing,
                risk_per_trade=position_sizing.get("risk_per_trade", 0.02),
                timeframe=timeframe,
                asset=asset,
            )

            # Store in history
            self.ai_strategies.append(ai_strategy)

            logger.info(f"✅ AI strategy generated: {ai_strategy.name}")
            logger.info(f"   Features: {', '.join(features[:3])}...")
            logger.info(f"   Expected Win Rate: {expected_metrics.get('win_rate', 'N/A')}")

            return ai_strategy

        except Exception as e:
            logger.error(f"❌ Error generating AI strategy: {e}")
            raise

    async def create_backtest_config_from_ai(
        self,
        ai_strategy: AIStrategy,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
    ) -> dict[str, Any]:
        """
        Convert AI strategy to backtest configuration

        Args:
            ai_strategy: AIStrategy object from generate_ai_strategy
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Initial trading capital

        Returns:
            Backtest configuration dict
        """
        logger.info(f"📋 Creating backtest config from AI strategy: {ai_strategy.name}")

        config = {
            "strategy": ai_strategy.to_backtest_config(),
            "data": {
                "symbol": ai_strategy.asset,
                "interval": ai_strategy.timeframe,
                "start_date": start_date,
                "end_date": end_date,
            },
            "backtest": {
                "initial_capital": initial_capital,
                "commission": 0.001,  # 0.1% trading fee
                "slippage": 0.0005,  # 0.05% slippage
            },
            "risk_management": {
                "max_position_size": 1.0,
                "max_daily_loss": initial_capital * 0.05,  # 5% max daily loss
                "max_drawdown": initial_capital * 0.20,  # 20% max drawdown
            },
            "metadata": {
                "created_at": datetime.now(UTC).isoformat(),
                "ai_generated": True,
                "ai_model": "deepseek-chat",
            },
        }

        logger.info("✅ Backtest config created")
        logger.info(f"   Capital: ${initial_capital:,.2f}")
        logger.info(f"   Period: {start_date} to {end_date}")

        return config

    async def execute_ai_backtest_series(
        self,
        objective: str,
        asset: str,
        timeframe: str,
        risk_tolerance: str,
        start_date: str,
        end_date: str,
        num_variations: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Execute multiple backtests with AI-generated variations

        Creates several variations of the AI strategy with different parameters
        and runs backtests on each to find the optimal configuration.

        Args:
            objective: Trading objective
            asset: Trading pair
            timeframe: Candle timeframe
            risk_tolerance: Risk level (low/medium/high)
            start_date: Backtest start date
            end_date: Backtest end date
            num_variations: Number of strategy variations to test

        Returns:
            List of backtest results
        """
        logger.info(f"🚀 Starting AI backtest series ({num_variations} variations)")
        logger.info(f"   Asset: {asset}, Timeframe: {timeframe}")
        logger.info(f"   Period: {start_date} → {end_date}")

        results = []

        try:
            # Generate base AI strategy
            ai_strategy = await self.generate_ai_strategy(
                objective=objective,
                asset=asset,
                timeframe=timeframe,
                risk_tolerance=risk_tolerance,
            )

            # Create backtest config
            backtest_config = await self.create_backtest_config_from_ai(
                ai_strategy=ai_strategy,
                start_date=start_date,
                end_date=end_date,
            )

            logger.info(f"📊 Generated backtest config for {ai_strategy.name}")
            logger.info(f"   Features: {len(ai_strategy.features)} indicators")
            logger.info(f"   Entry signals: {len(ai_strategy.entry_long)} long, {len(ai_strategy.entry_short)} short")

            # Store result
            result = {
                "strategy_name": ai_strategy.name,
                "backtest_config": backtest_config,
                "features": ai_strategy.features,
                "status": "ready_for_execution",
                "created_at": datetime.now(UTC).isoformat(),
            }
            results.append(result)

            # Run actual backtest using BacktestEngine
            try:
                backtest_result = await self._run_backtest(backtest_config, start_date, end_date)
                result["backtest_results"] = backtest_result
                result["status"] = "completed"
            except Exception as bt_error:
                logger.warning(f"Backtest execution failed: {bt_error}")
                result["status"] = "execution_failed"
                result["error"] = str(bt_error)

            self.backtest_results.extend(results)

            logger.info(f"✅ Backtest series ready: {len(results)} configurations")
            return results

        except Exception as e:
            logger.error(f"❌ Error in AI backtest series: {e}")
            return []

    async def analyze_backtest_results(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Ask AI to analyze backtest results and recommend best strategy

        Args:
            results: List of backtest result dicts

        Returns:
            AI analysis with recommendations
        """
        logger.info(f"🔍 Analyzing {len(results)} backtest results with AI")

        try:
            # Prepare results summary for AI
            results_summary = []
            for result in results:
                results_summary.append(
                    {
                        "strategy": result.get("strategy_name"),
                        "metrics": result.get("metrics", {}),
                    }
                )

            # Ask AI for analysis
            prompt = f"""Analyze these backtest results and recommend the best strategy:

{json.dumps(results_summary, indent=2)}

For each strategy, evaluate:
1. Risk-adjusted returns (Sharpe ratio, Sortino ratio)
2. Drawdown and recovery patterns
3. Win rate and profit factor
4. Consistency across different market conditions

Provide recommendations in JSON format:
{{
  "best_strategy": "strategy_name",
  "win_rate": percentage,
  "profit_factor": number,
  "max_drawdown": percentage,
  "sharpe_ratio": number,
  "recommendations": ["recommendation1", "recommendation2"],
  "analysis": "detailed analysis"
}}"""

            # Get AI analysis (using cache-enabled query)
            result = await self.engineer.agent.query_deepseek(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1500,
                use_cache=False,  # Fresh analysis each time
            )

            response_text = result.get("response", "")

            # Parse JSON
            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    analysis = {"analysis": response_text}
            except json.JSONDecodeError:
                analysis = {"analysis": response_text}

            logger.info("✅ AI analysis complete")
            if "best_strategy" in analysis:
                logger.info(f"   Recommended: {analysis['best_strategy']}")

            return analysis

        except Exception as e:
            logger.error(f"❌ Error analyzing results: {e}")
            return {"error": str(e)}

    def get_strategy_history(self) -> list[dict[str, Any]]:
        """Get history of generated strategies"""
        return [asdict(strategy) for strategy in self.ai_strategies]

    def get_backtest_history(self) -> list[dict[str, Any]]:
        """Get history of backtest executions"""
        return self.backtest_results

    async def run_backtest(
        self,
        strategy_code: str,
        symbol: str,
        timeframe: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Run a backtest for a given strategy code and market parameters.

        Public convenience wrapper around ``_run_backtest`` used by
        ``AIStrategyGenerator._run_backtest``.

        Args:
            strategy_code: Python source of the strategy.
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            timeframe: Candle interval, e.g. ``"15"``.
            days: Look-back period in days.

        Returns:
            Dict with backtest metrics (total_return, win_rate, …).
        """
        from datetime import UTC, datetime, timedelta

        end = datetime.now(UTC)
        start = end - timedelta(days=days)

        config: dict[str, Any] = {
            "asset": symbol,
            "timeframe": timeframe,
            "strategy_code": strategy_code,
        }
        return await self._run_backtest(
            backtest_config=config,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )

    async def _run_backtest(
        self,
        backtest_config: dict[str, Any],
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        Execute backtest using BacktestEngine

        Args:
            backtest_config: Strategy configuration
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            Backtest results with metrics
        """
        try:
            from backend.backtesting.engine import get_engine
            from backend.database import SessionLocal
            from backend.services.data_service import DataService

            # Get symbol and timeframe from config
            symbol = backtest_config.get("asset", "BTCUSDT").replace("/", "")
            timeframe = backtest_config.get("timeframe", "1h")

            db = SessionLocal()
            ds = DataService(db)

            try:
                # Load market data
                logger.info(f"📥 Loading market data for {symbol} {timeframe}")
                candles = ds.get_market_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=start_date,
                    end_time=end_date,
                )

                if candles is None or len(candles) == 0:
                    logger.warning(f"No market data available for {symbol}")
                    return {"error": "No market data", "status": "failed"}

                logger.info(f"📊 Loaded {len(candles)} candles")

                # Initialize engine
                engine = get_engine(
                    None,
                    data_service=ds,
                    initial_capital=10000.0,
                    commission=0.0007,  # 0.07% TradingView parity
                    slippage=0.0001,
                )

                # Run backtest
                logger.info("⚙️ Running backtest engine...")
                results = engine.run(data=candles, strategy_config=backtest_config)

                logger.info("✅ Backtest completed successfully")
                return {
                    "status": "completed",
                    "metrics": results.get("metrics", {}),
                    "trades": len(results.get("trades", [])),
                    "equity_curve_points": len(results.get("equity_curve", [])),
                }

            finally:
                db.close()

        except ImportError as e:
            logger.warning(f"Backtest dependencies not available: {e}")
            return {"error": str(e), "status": "dependencies_missing"}
        except Exception as e:
            logger.error(f"Backtest execution error: {e}")
            return {"error": str(e), "status": "failed"}


# Convenience function
async def run_ai_backtest_pipeline(
    objective: str,
    asset: str = "BTC/USDT",
    timeframe: str = "1h",
    risk_tolerance: str = "medium",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
) -> dict[str, Any]:
    """
    Quick helper to run complete AI backtest pipeline

    1. Generate AI strategy
    2. Create backtest config
    3. Run backtest (ready for execution)
    4. Analyze results
    """
    executor = AIBacktestExecutor()

    # Run backtest series
    results = await executor.execute_ai_backtest_series(
        objective=objective,
        asset=asset,
        timeframe=timeframe,
        risk_tolerance=risk_tolerance,
        start_date=start_date,
        end_date=end_date,
        num_variations=1,
    )

    # Analyze results
    analysis = await executor.analyze_backtest_results(results)

    return {
        "results": results,
        "analysis": analysis,
        "strategy_history": executor.get_strategy_history(),
    }
