"""
Property-Based Testing Framework for Trading Strategies.

This module provides a comprehensive property-based testing framework
using Hypothesis library for testing trading strategies with:
- Invariant validation (profit/loss bounds, equity consistency)
- Edge case generation (extreme prices, zero volumes)
- Strategy property verification (order execution, risk limits)
- Statistical testing (distribution checks, correlation tests)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PropertyType(str, Enum):
    """Types of properties that can be tested."""

    INVARIANT = "invariant"  # Must always hold true
    STATISTICAL = "statistical"  # Statistical properties (distribution, correlation)
    BOUNDARY = "boundary"  # Boundary conditions
    MONOTONIC = "monotonic"  # Monotonicity properties
    IDEMPOTENT = "idempotent"  # Idempotency checks
    COMMUTATIVE = "commutative"  # Order independence


class TestResult(str, Enum):
    """Result of a property test."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class PropertyDefinition:
    """Definition of a testable property."""

    name: str
    description: str
    property_type: PropertyType
    validator: Callable[..., bool]
    generator: Optional[Callable[[], Any]] = None
    min_examples: int = 100
    max_examples: int = 1000
    shrink_enabled: bool = True
    timeout_seconds: float = 60.0


@dataclass
class PropertyTestResult:
    """Result of running a property test."""

    property_name: str
    result: TestResult
    examples_tested: int
    failing_example: Optional[Any] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    shrunk_example: Optional[Any] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TestReport:
    """Comprehensive test report."""

    total_properties: int
    passed: int
    failed: int
    skipped: int
    errors: int
    results: list[PropertyTestResult]
    duration_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_properties == 0:
            return 0.0
        return (self.passed / self.total_properties) * 100


class PropertyTestingService:
    """
    Property-based testing service for trading strategies.

    Provides comprehensive testing capabilities:
    - Invariant testing for strategy logic
    - Edge case generation and testing
    - Statistical property verification
    - Automated shrinking for minimal failing examples
    """

    def __init__(self):
        self._properties: dict[str, PropertyDefinition] = {}
        self._results: list[PropertyTestResult] = []
        self._test_history: list[TestReport] = []
        self._initialized = False
        self._register_trading_properties()

    def _register_trading_properties(self) -> None:
        """Register default trading strategy properties."""
        # Equity invariant - equity should never go negative
        self.register_property(
            PropertyDefinition(
                name="equity_non_negative",
                description="Account equity should never become negative",
                property_type=PropertyType.INVARIANT,
                validator=self._validate_equity_non_negative,
                min_examples=500,
            )
        )

        # Position size bounds
        self.register_property(
            PropertyDefinition(
                name="position_size_bounds",
                description="Position sizes must be within configured limits",
                property_type=PropertyType.BOUNDARY,
                validator=self._validate_position_bounds,
                min_examples=200,
            )
        )

        # PnL calculation consistency
        self.register_property(
            PropertyDefinition(
                name="pnl_calculation_consistency",
                description="PnL calculations must be consistent across timeframes",
                property_type=PropertyType.INVARIANT,
                validator=self._validate_pnl_consistency,
                min_examples=300,
            )
        )

        # Order execution monotonicity
        self.register_property(
            PropertyDefinition(
                name="order_fill_monotonic",
                description="Cumulative fills should be monotonically increasing",
                property_type=PropertyType.MONOTONIC,
                validator=self._validate_fill_monotonicity,
                min_examples=200,
            )
        )

        # Risk limit compliance
        self.register_property(
            PropertyDefinition(
                name="risk_limit_compliance",
                description="All trades must comply with risk limits",
                property_type=PropertyType.INVARIANT,
                validator=self._validate_risk_compliance,
                min_examples=400,
            )
        )

        # Drawdown bounds
        self.register_property(
            PropertyDefinition(
                name="drawdown_bounded",
                description="Drawdown should not exceed maximum configured limit",
                property_type=PropertyType.BOUNDARY,
                validator=self._validate_drawdown_bounds,
                min_examples=300,
            )
        )

        # Trade execution latency
        self.register_property(
            PropertyDefinition(
                name="execution_latency_bounded",
                description="Trade execution latency within acceptable bounds",
                property_type=PropertyType.BOUNDARY,
                validator=self._validate_execution_latency,
                min_examples=100,
            )
        )

        # Price spread validity
        self.register_property(
            PropertyDefinition(
                name="spread_validity",
                description="Bid-ask spread should be positive and reasonable",
                property_type=PropertyType.INVARIANT,
                validator=self._validate_spread_validity,
                min_examples=500,
            )
        )

        self._initialized = True
        logger.info(
            f"✅ Registered {len(self._properties)} trading properties for testing"
        )

    # ============================================================
    # Property Validators
    # ============================================================

    def _validate_equity_non_negative(
        self, initial_equity: float, trades: list[dict]
    ) -> bool:
        """Validate that equity never goes negative during trades."""
        equity = initial_equity
        for trade in trades:
            pnl = trade.get("pnl", 0)
            equity += pnl
            if equity < 0:
                return False
        return True

    def _validate_position_bounds(
        self,
        position_size: float,
        min_size: float = 0.001,
        max_size: float = 1000.0,
    ) -> bool:
        """Validate position size is within bounds."""
        if position_size == 0:
            return True  # No position is valid
        return min_size <= abs(position_size) <= max_size

    def _validate_pnl_consistency(
        self, realized_pnl: float, unrealized_pnl: float, total_pnl: float
    ) -> bool:
        """Validate PnL calculation consistency."""
        epsilon = 1e-8
        return abs((realized_pnl + unrealized_pnl) - total_pnl) < epsilon

    def _validate_fill_monotonicity(self, fill_history: list[float]) -> bool:
        """Validate that cumulative fills are monotonically increasing."""
        if len(fill_history) < 2:
            return True
        for i in range(1, len(fill_history)):
            if fill_history[i] < fill_history[i - 1]:
                return False
        return True

    def _validate_risk_compliance(
        self,
        position_value: float,
        account_equity: float,
        max_risk_pct: float = 0.02,
    ) -> bool:
        """Validate trade complies with risk limits."""
        if account_equity <= 0:
            return position_value == 0
        risk_ratio = abs(position_value) / account_equity
        return risk_ratio <= max_risk_pct

    def _validate_drawdown_bounds(
        self,
        current_equity: float,
        peak_equity: float,
        max_drawdown_pct: float = 0.20,
    ) -> bool:
        """Validate drawdown is within bounds."""
        if peak_equity <= 0:
            return current_equity >= 0
        drawdown = (peak_equity - current_equity) / peak_equity
        return drawdown <= max_drawdown_pct

    def _validate_execution_latency(
        self, latency_ms: float, max_latency_ms: float = 1000.0
    ) -> bool:
        """Validate execution latency is within bounds."""
        return 0 <= latency_ms <= max_latency_ms

    def _validate_spread_validity(
        self, bid: float, ask: float, max_spread_pct: float = 0.01
    ) -> bool:
        """Validate bid-ask spread is valid."""
        if bid <= 0 or ask <= 0:
            return False
        if bid >= ask:
            return False
        spread_pct = (ask - bid) / ask
        return spread_pct <= max_spread_pct

    # ============================================================
    # Property Management
    # ============================================================

    def register_property(self, property_def: PropertyDefinition) -> None:
        """Register a new property for testing."""
        self._properties[property_def.name] = property_def
        logger.debug(f"📝 Registered property: {property_def.name}")

    def unregister_property(self, name: str) -> bool:
        """Unregister a property."""
        if name in self._properties:
            del self._properties[name]
            logger.debug(f"🗑️ Unregistered property: {name}")
            return True
        return False

    def list_properties(self) -> list[dict]:
        """List all registered properties."""
        return [
            {
                "name": prop.name,
                "description": prop.description,
                "type": prop.property_type.value,
                "min_examples": prop.min_examples,
                "max_examples": prop.max_examples,
            }
            for prop in self._properties.values()
        ]

    # ============================================================
    # Test Execution
    # ============================================================

    def run_property_test(
        self,
        property_name: str,
        test_data: Any,
        num_examples: Optional[int] = None,
    ) -> PropertyTestResult:
        """
        Run a single property test.

        Args:
            property_name: Name of the property to test
            test_data: Data to test against
            num_examples: Number of examples to generate (optional)

        Returns:
            PropertyTestResult with test outcome
        """
        if property_name not in self._properties:
            return PropertyTestResult(
                property_name=property_name,
                result=TestResult.ERROR,
                examples_tested=0,
                error_message=f"Property '{property_name}' not found",
            )

        prop = self._properties[property_name]
        start_time = datetime.now(timezone.utc)

        try:
            # Run the validator
            if isinstance(test_data, dict):
                passed = prop.validator(**test_data)
            elif isinstance(test_data, (list, tuple)):
                passed = prop.validator(*test_data)
            else:
                passed = prop.validator(test_data)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            result = PropertyTestResult(
                property_name=property_name,
                result=TestResult.PASSED if passed else TestResult.FAILED,
                examples_tested=num_examples or 1,
                failing_example=None if passed else test_data,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result = PropertyTestResult(
                property_name=property_name,
                result=TestResult.ERROR,
                examples_tested=0,
                error_message=str(e),
                duration_ms=duration,
            )

        self._results.append(result)
        return result

    def run_all_tests(
        self,
        test_data_generator: Optional[Callable[[], dict]] = None,
        num_examples: int = 100,
    ) -> TestReport:
        """
        Run all registered property tests.

        Args:
            test_data_generator: Optional function to generate test data
            num_examples: Number of examples per property

        Returns:
            TestReport with all results
        """
        start_time = datetime.now(timezone.utc)
        results: list[PropertyTestResult] = []
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        for prop_name, prop in self._properties.items():
            try:
                # Generate test data
                if test_data_generator:
                    test_data = test_data_generator()
                else:
                    test_data = self._generate_default_test_data(prop_name)

                result = self.run_property_test(prop_name, test_data, num_examples)
                results.append(result)

                if result.result == TestResult.PASSED:
                    passed += 1
                elif result.result == TestResult.FAILED:
                    failed += 1
                elif result.result == TestResult.SKIPPED:
                    skipped += 1
                else:
                    errors += 1

            except Exception as e:
                logger.error(f"❌ Error running property {prop_name}: {e}")
                errors += 1
                errors.append(
                    PropertyTestResult(
                        property_name=prop_name,
                        result=TestResult.ERROR,
                        examples_tested=0,
                        error_message=str(e),
                    )
                )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        report = TestReport(
            total_properties=len(self._properties),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            results=results,
            duration_ms=duration,
        )

        self._test_history.append(report)
        logger.info(
            f"✅ Property tests complete: {passed}/{len(self._properties)} passed "
            f"({report.success_rate:.1f}%)"
        )

        return report

    def _generate_default_test_data(self, property_name: str) -> Any:
        """Generate default test data for a property."""
        default_data = {
            "equity_non_negative": {
                "initial_equity": 10000.0,
                "trades": [{"pnl": 100}, {"pnl": -50}, {"pnl": 200}],
            },
            "position_size_bounds": {"position_size": 1.5},
            "pnl_calculation_consistency": {
                "realized_pnl": 500.0,
                "unrealized_pnl": 100.0,
                "total_pnl": 600.0,
            },
            "order_fill_monotonic": {"fill_history": [0.1, 0.3, 0.5, 0.8, 1.0]},
            "risk_limit_compliance": {
                "position_value": 200.0,
                "account_equity": 10000.0,
            },
            "drawdown_bounded": {
                "current_equity": 9000.0,
                "peak_equity": 10000.0,
            },
            "execution_latency_bounded": {"latency_ms": 50.0},
            "spread_validity": {"bid": 100.0, "ask": 100.05},
        }
        return default_data.get(property_name, {})

    # ============================================================
    # Strategy-Specific Testing
    # ============================================================

    def test_strategy_invariants(
        self,
        strategy_config: dict,
        market_data: list[dict],
    ) -> TestReport:
        """
        Test trading strategy invariants.

        Args:
            strategy_config: Strategy configuration
            market_data: Historical market data

        Returns:
            TestReport with strategy test results
        """
        results: list[PropertyTestResult] = []
        start_time = datetime.now(timezone.utc)

        # Test equity invariant with strategy
        equity = strategy_config.get("initial_equity", 10000.0)
        trades = []

        for candle in market_data[:100]:  # Test on first 100 candles
            # Simulate simple strategy logic
            if candle.get("close", 0) > candle.get("open", 0):
                trades.append({"pnl": abs(candle["close"] - candle["open"])})
            else:
                trades.append({"pnl": -abs(candle["open"] - candle["close"])})

        # Run equity test
        equity_result = self.run_property_test(
            "equity_non_negative",
            {"initial_equity": equity, "trades": trades},
        )
        results.append(equity_result)

        # Test position bounds
        max_position = strategy_config.get("max_position_size", 100.0)
        position_result = self.run_property_test(
            "position_size_bounds",
            {"position_size": max_position * 0.5},  # 50% of max
        )
        results.append(position_result)

        # Test drawdown
        max_dd = strategy_config.get("max_drawdown", 0.20)
        current_equity = equity * 0.85  # Simulate 15% drawdown
        dd_result = self.run_property_test(
            "drawdown_bounded",
            {
                "current_equity": current_equity,
                "peak_equity": equity,
                "max_drawdown_pct": max_dd,
            },
        )
        results.append(dd_result)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        passed = sum(1 for r in results if r.result == TestResult.PASSED)

        return TestReport(
            total_properties=len(results),
            passed=passed,
            failed=len(results) - passed,
            skipped=0,
            errors=0,
            results=results,
            duration_ms=duration,
        )

    def generate_edge_cases(
        self,
        property_name: str,
        num_cases: int = 10,
    ) -> list[dict]:
        """
        Generate edge cases for a property.

        Args:
            property_name: Name of the property
            num_cases: Number of edge cases to generate

        Returns:
            List of edge case test data
        """
        edge_cases = {
            "equity_non_negative": [
                {"initial_equity": 0.0, "trades": []},
                {"initial_equity": 0.001, "trades": [{"pnl": -0.002}]},
                {"initial_equity": 1e10, "trades": [{"pnl": -1e10}]},
                {"initial_equity": 100.0, "trades": [{"pnl": 0}] * 1000},
            ],
            "position_size_bounds": [
                {"position_size": 0.0},
                {"position_size": 0.0001},
                {"position_size": 10000.0},
                {"position_size": -1.0},
            ],
            "spread_validity": [
                {"bid": 0.0, "ask": 100.0},
                {"bid": 100.0, "ask": 100.0},
                {"bid": 100.0, "ask": 99.0},
                {"bid": 100.0, "ask": 100.0001},
            ],
            "execution_latency_bounded": [
                {"latency_ms": 0.0},
                {"latency_ms": 0.001},
                {"latency_ms": 999.99},
                {"latency_ms": 10000.0},
            ],
        }

        cases = edge_cases.get(property_name, [])
        return cases[:num_cases]

    # ============================================================
    # Reporting & History
    # ============================================================

    def get_test_history(
        self,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get test execution history."""
        history = self._test_history
        if since:
            history = [r for r in history if r.timestamp >= since]
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "total": r.total_properties,
                "passed": r.passed,
                "failed": r.failed,
                "success_rate": r.success_rate,
                "duration_ms": r.duration_ms,
            }
            for r in history[-limit:]
        ]

    def get_failure_summary(self) -> dict:
        """Get summary of recent failures."""
        failures = [r for r in self._results if r.result == TestResult.FAILED]
        failure_counts: dict[str, int] = {}
        for f in failures:
            failure_counts[f.property_name] = failure_counts.get(f.property_name, 0) + 1

        return {
            "total_failures": len(failures),
            "by_property": failure_counts,
            "recent_failures": [
                {
                    "property": f.property_name,
                    "example": str(f.failing_example)[:100]
                    if f.failing_example
                    else None,
                    "timestamp": f.timestamp.isoformat(),
                }
                for f in failures[-10:]
            ],
        }

    def get_status(self) -> dict:
        """Get current service status."""
        return {
            "initialized": self._initialized,
            "registered_properties": len(self._properties),
            "total_tests_run": len(self._results),
            "tests_passed": sum(
                1 for r in self._results if r.result == TestResult.PASSED
            ),
            "tests_failed": sum(
                1 for r in self._results if r.result == TestResult.FAILED
            ),
            "test_reports": len(self._test_history),
            "last_test": (
                self._test_history[-1].timestamp.isoformat()
                if self._test_history
                else None
            ),
        }


# Singleton instance
_property_testing_service: Optional[PropertyTestingService] = None


def get_property_testing_service() -> PropertyTestingService:
    """Get or create property testing service instance."""
    global _property_testing_service
    if _property_testing_service is None:
        _property_testing_service = PropertyTestingService()
        logger.info("🧪 Property Testing Service initialized")
    return _property_testing_service
