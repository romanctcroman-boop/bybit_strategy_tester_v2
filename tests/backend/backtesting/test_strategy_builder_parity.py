"""
Parity tests for Strategy Builder: Adapter vs Generated Code

Tests that StrategyBuilderAdapter and CodeGenerator produce identical
backtest results (100% parity, no tolerance).

For each test strategy:
1. Create strategy via Strategy Builder API
2. Run backtest via StrategyBuilderAdapter
3. Generate Python code via API endpoint
4. Execute generated code and run backtest
5. Compare ALL metrics with strict equality (==)
"""

import importlib.util
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, StrategyType
from backend.backtesting.strategies import BaseStrategy, SignalResult
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter
from backend.database import Base, get_db

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override get_db dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_app():
    """Create a test FastAPI app"""
    from backend.api.routers.strategy_builder import router as strategy_builder_router

    app = FastAPI()
    app.include_router(strategy_builder_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.create_all(bind=engine)
    yield app
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def clean_db():
    """Ensure clean database state for each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_app, clean_db):
    """Create test client"""
    with TestClient(test_app) as c:
        yield c


@pytest.fixture
def sample_ohlcv():
    """Generate synthetic OHLCV data for testing"""
    dates = pd.date_range("2024-01-01", periods=1000, freq="1h")
    np.random.seed(42)  # For reproducibility
    prices = 10000 + np.cumsum(np.random.randn(1000) * 50)
    ohlcv = pd.DataFrame(
        {
            "open": prices + np.random.randn(1000) * 10,
            "high": prices + np.abs(np.random.randn(1000) * 20),
            "low": prices - np.abs(np.random.randn(1000) * 20),
            "close": prices + np.random.randn(1000) * 10,
            "volume": np.random.uniform(100, 1000, 1000),
        },
        index=dates,
    )
    return ohlcv


class GeneratedCodeStrategy(BaseStrategy):
    """
    Wrapper for CodeGenerator-generated strategy code.

    Executes generated Python code and converts its output
    (List[Dict]) to SignalResult format.
    """

    def __init__(self, generated_code: str, strategy_name: str, params: dict[str, Any] | None = None):
        """
        Initialize from generated code string.

        Args:
            generated_code: Python code string from CodeGenerator
            strategy_name: Name of the generated strategy class
            params: Strategy parameters (not used for generated code)
        """
        super().__init__(params)
        self.generated_code = generated_code
        self.strategy_name = strategy_name
        self._strategy_instance = None
        self._load_strategy()

    def _load_strategy(self) -> None:
        """Load and instantiate the generated strategy class"""
        # Create a temporary module
        spec = importlib.util.spec_from_loader("generated_strategy", loader=None)
        module = importlib.util.module_from_spec(spec)

        # Execute generated code in module namespace
        exec(self.generated_code, module.__dict__)

        # Get strategy class
        strategy_class = getattr(module, self.strategy_name)
        self._strategy_instance = strategy_class()

    def _validate_params(self) -> None:
        """No validation needed for generated code"""
        pass

    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """
        Generate signals using generated code.

        Converts generated code's List[Dict] output to SignalResult.
        The generated code processes candles bar-by-bar and returns signals
        with bar indices.
        """
        # Convert OHLCV to format expected by generated code (numpy arrays)
        candles = {
            "open": ohlcv["open"].values,
            "high": ohlcv["high"].values,
            "low": ohlcv["low"].values,
            "close": ohlcv["close"].values,
            "volume": ohlcv["volume"].values,
        }

        # Call generated strategy's calculate method
        signals_list = self._strategy_instance.calculate(candles)

        # Convert List[Dict] to SignalResult
        n = len(ohlcv)
        entries = pd.Series([False] * n, index=ohlcv.index)
        exits = pd.Series([False] * n, index=ohlcv.index)
        short_entries = pd.Series([False] * n, index=ohlcv.index)
        short_exits = pd.Series([False] * n, index=ohlcv.index)

        # Process signals - generated code should include 'index' field
        for signal in signals_list:
            action = signal.get("action", "").lower()
            # Try to get index from signal dict
            idx = signal.get("index")
            if idx is None:
                # If no index, try to infer from position in list
                # This is a fallback - ideally CodeGenerator should add index
                continue

            if isinstance(idx, (int, np.integer)) and 0 <= idx < n:
                if action == "buy":
                    entries.iloc[idx] = True
                elif action == "sell":
                    exits.iloc[idx] = True
                elif action == "short":
                    short_entries.iloc[idx] = True
                elif action == "close":
                    short_exits.iloc[idx] = True

        return SignalResult(
            entries=entries,
            exits=exits,
            short_entries=short_entries if short_entries.any() else None,
            short_exits=short_exits if short_exits.any() else None,
        )


def build_rsi_strategy_graph() -> dict[str, Any]:
    """Build a simple RSI oversold strategy graph"""
    return {
        "name": "RSI Parity Test",
        "description": "RSI oversold strategy for parity testing",
        "blocks": [
            {
                "id": "block_price",
                "type": "price",
                "category": "input",
                "name": "Price",
                "x": 100,
                "y": 100,
                "params": {},
            },
            {
                "id": "block_rsi",
                "type": "rsi",
                "category": "indicator",
                "name": "RSI",
                "x": 300,
                "y": 100,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "block_const_30",
                "type": "constant",
                "category": "input",
                "name": "Constant 30",
                "x": 100,
                "y": 200,
                "params": {"value": 30},
            },
            {
                "id": "block_less_than",
                "type": "less_than",
                "category": "condition",
                "name": "Less Than",
                "x": 500,
                "y": 150,
                "params": {},
            },
            {
                "id": "main_strategy",
                "type": "strategy",
                "category": "main",
                "name": "Strategy",
                "isMain": True,
                "x": 700,
                "y": 150,
                "params": {},
            },
        ],
        "connections": [
            {
                "id": "conn_price_rsi",
                "source": {"blockId": "block_price", "portId": "value"},
                "target": {"blockId": "block_rsi", "portId": "source"},
                "type": "data",
            },
            {
                "id": "conn_rsi_lt",
                "source": {"blockId": "block_rsi", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "a"},
                "type": "data",
            },
            {
                "id": "conn_const_lt",
                "source": {"blockId": "block_const_30", "portId": "value"},
                "target": {"blockId": "block_less_than", "portId": "b"},
                "type": "data",
            },
            {
                "id": "conn_lt_entry",
                "source": {"blockId": "block_less_than", "portId": "result"},
                "target": {"blockId": "main_strategy", "portId": "entry_long"},
                "type": "data",
            },
        ],
    }


def run_backtest_with_strategy(strategy: BaseStrategy, ohlcv: pd.DataFrame, config: BacktestConfig) -> dict[str, Any]:
    """Run backtest with given strategy and return metrics"""
    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=strategy, silent=True)

    if not result.metrics:
        return {}

    # Extract all metrics for comparison
    metrics = result.metrics
    return {
        "total_return": metrics.total_return,
        "net_profit": metrics.net_profit,
        "max_drawdown": metrics.max_drawdown,
        "total_trades": metrics.total_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "win_rate": metrics.win_rate,
        "sharpe_ratio": metrics.sharpe_ratio,
        "sortino_ratio": metrics.sortino_ratio,
        "calmar_ratio": metrics.calmar_ratio,
        "profit_factor": metrics.profit_factor,
        "gross_profit": metrics.gross_profit,
        "gross_loss": metrics.gross_loss,
        "buy_hold_return": metrics.buy_hold_return,
        "cagr": metrics.cagr,
        "avg_trade_value": metrics.avg_trade_value,
        "best_trade": metrics.best_trade,
        "worst_trade": metrics.worst_trade,
    }


class TestStrategyBuilderParity:
    """Test parity between StrategyBuilderAdapter and CodeGenerator output"""

    def test_rsi_strategy_parity(self, client, sample_ohlcv):
        """Test RSI oversold strategy: Adapter vs Generated Code"""
        graph = build_rsi_strategy_graph()

        # 1. Create strategy via API
        create_response = client.post(
            "/api/v1/strategy-builder/strategies",
            json={
                "name": graph["name"],
                "description": graph["description"],
                "timeframe": "1h",
                "symbols": ["BTCUSDT"],
                "blocks": graph["blocks"],
                "connections": graph["connections"],
            },
        )
        assert create_response.status_code == 200, create_response.text
        strategy_id = create_response.json()["id"]

        # Build BacktestConfig
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="1h",
            start_date=sample_ohlcv.index[0],
            end_date=sample_ohlcv.index[-1],
            strategy_type=StrategyType.CUSTOM,
            strategy_params={},
            initial_capital=10000.0,
            position_size=1.0,
            leverage=1.0,
            direction="both",
            taker_fee=0.0007,
            maker_fee=0.0007,
            slippage=0.0005,
        )

        # 2. Run backtest via StrategyBuilderAdapter
        adapter = StrategyBuilderAdapter(graph)
        adapter_metrics = run_backtest_with_strategy(adapter, sample_ohlcv, config)

        # 3. Generate code via API endpoint
        generate_response = client.post(
            f"/api/v1/strategy-builder/strategies/{strategy_id}/generate-code",
            json={"template": "backtest", "include_comments": True},
        )
        assert generate_response.status_code == 200, generate_response.text
        generate_data = generate_response.json()
        assert generate_data["success"], f"Code generation failed: {generate_data.get('errors')}"

        generated_code = generate_data["code"]
        strategy_name = generate_data["strategy_name"]

        # 4. Run backtest via Generated Code
        generated_strategy = GeneratedCodeStrategy(generated_code, strategy_name, params={})
        generated_metrics = run_backtest_with_strategy(generated_strategy, sample_ohlcv, config)

        # 5. Compare ALL metrics with strict equality (100% parity required)
        metric_keys = [
            "total_return",
            "net_profit",
            "max_drawdown",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "profit_factor",
            "gross_profit",
            "gross_loss",
            "buy_hold_return",
            "cagr",
            "avg_trade_value",
            "best_trade",
            "worst_trade",
        ]

        mismatches = []
        for key in metric_keys:
            adapter_val = adapter_metrics.get(key)
            generated_val = generated_metrics.get(key)

            # Handle NaN comparisons
            if pd.isna(adapter_val) and pd.isna(generated_val):
                continue
            if adapter_val != generated_val:
                mismatches.append(f"{key}: adapter={adapter_val}, generated={generated_val}")

        if mismatches:
            pytest.fail("Metrics mismatch (100% parity required):\n" + "\n".join(mismatches))
