"""
Static Analysis Module for Strategy Code

Detects common backtesting pitfalls:
- Look-ahead bias (using future data)
- Repainting indicators
- Data leakage patterns

TradingView compatible warnings as per ТЗ specification.
"""

import ast
import re
from dataclasses import dataclass, field
from enum import Enum


class WarningLevel(str, Enum):
    """Warning severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AnalysisWarning:
    """Single analysis warning"""

    code: str  # e.g., "LOOKAHEAD_001"
    level: WarningLevel
    message: str
    line_number: int | None = None
    suggestion: str | None = None


@dataclass
class StrategyAnalysisResult:
    """Result of static strategy analysis"""

    has_lookahead_bias: bool = False
    is_repainting: bool = False
    has_data_leakage: bool = False
    warnings: list[AnalysisWarning] = field(default_factory=list)

    # Detailed flags
    uses_future_data: bool = False
    uses_high_low_of_current_bar: bool = False
    uses_close_for_entry_on_same_bar: bool = False
    has_forward_fill: bool = False
    uses_request_security: bool = False

    @property
    def is_safe(self) -> bool:
        """Check if strategy passed all checks"""
        return not (
            self.has_lookahead_bias or self.is_repainting or self.has_data_leakage
        )

    @property
    def critical_warnings(self) -> list[AnalysisWarning]:
        """Get only critical warnings"""
        return [
            w
            for w in self.warnings
            if w.level in (WarningLevel.ERROR, WarningLevel.CRITICAL)
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "has_lookahead_bias": self.has_lookahead_bias,
            "is_repainting": self.is_repainting,
            "has_data_leakage": self.has_data_leakage,
            "uses_future_data": self.uses_future_data,
            "uses_high_low_of_current_bar": self.uses_high_low_of_current_bar,
            "uses_close_for_entry_on_same_bar": self.uses_close_for_entry_on_same_bar,
            "has_forward_fill": self.has_forward_fill,
            "uses_request_security": self.uses_request_security,
            "is_safe": self.is_safe,
            "warnings": [
                {
                    "code": w.code,
                    "level": w.level.value,
                    "message": w.message,
                    "line_number": w.line_number,
                    "suggestion": w.suggestion,
                }
                for w in self.warnings
            ],
        }


class StrategyAnalyzer:
    """
    Static analyzer for trading strategy code.

    Detects:
    1. Look-ahead bias - using future data in calculations
    2. Repainting - indicator values that change on historical bars
    3. Data leakage - train/test contamination patterns

    TradingView-compatible analysis:
    - request.security() without barmerge.lookahead_on check
    - Using high/low of current bar for entry
    - Using close for entry on same bar (assumes bar completion)
    - Forward-fill without proper handling

    Usage:
        analyzer = StrategyAnalyzer()
        result = analyzer.analyze_code(strategy_code)
        if result.has_lookahead_bias:
            print("Warning: Strategy may have look-ahead bias!")
    """

    # Patterns that indicate look-ahead bias
    LOOKAHEAD_PATTERNS = [
        # Using future index in array access
        (
            r"\[\s*-?\d+\s*:\s*\]",
            "LOOKAHEAD_001",
            "Slice access may include future data",
        ),
        # shift(-N) with negative means looking forward
        (r"\.shift\s*\(\s*-\d+", "LOOKAHEAD_002", "Negative shift looks into future"),
        # Forward fill without awareness
        (
            r"\.ffill\(\)",
            "LOOKAHEAD_003",
            "Forward fill may leak future data if not handled",
        ),
        # Lead function
        (r"\.lead\s*\(", "LOOKAHEAD_004", "lead() function accesses future values"),
        # Expanding window that uses all data
        (
            r"\.expanding\s*\(",
            "LOOKAHEAD_005",
            "Expanding window may include future data in optimization",
        ),
    ]

    # Patterns that indicate repainting
    REPAINT_PATTERNS = [
        # High/Low on current bar in entry condition
        (
            r"(entry|signal).*high\s*\[0\]",
            "REPAINT_001",
            "Using current bar high for entry - repaints",
        ),
        (
            r"(entry|signal).*low\s*\[0\]",
            "REPAINT_002",
            "Using current bar low for entry - repaints",
        ),
        # Close on current bar for entry (bar not complete)
        (
            r"(entry|signal).*close\s*(?!\[\s*1)",
            "REPAINT_003",
            "Using current bar close for entry - may repaint",
        ),
        # HL2/OHLC4 on current bar
        (r"hl2\s*(?!\[)", "REPAINT_004", "hl2 on current bar may repaint"),
        (r"ohlc4\s*(?!\[)", "REPAINT_005", "ohlc4 on current bar may repaint"),
    ]

    # TradingView specific patterns
    TRADINGVIEW_PATTERNS = [
        # request.security without lookahead parameter
        (
            r"request\.security\s*\([^)]*\)",
            "TV_001",
            "request.security() - check for lookahead handling",
        ),
        # barmerge.lookahead_on (intentional lookahead - warning only)
        (
            r"barmerge\.lookahead_on",
            "TV_002",
            "Using lookahead_on - intentional future data access",
        ),
        # Plotting in strategy conditions
        (
            r"plotshape.*strategy\.entry",
            "TV_003",
            "Mixing plot with strategy may cause visual repainting",
        ),
    ]

    # Indicators known to repaint
    REPAINTING_INDICATORS = [
        "pivothigh",
        "pivotlow",  # Pivot points repaint by definition
        "highest",
        "lowest",  # Only if on current bar without offset
        "valuewhen",  # Can repaint if condition changes
        "barssince",  # Can repaint
        "ta.change",  # Safe but commonly misused
        "security",  # Depends on lookahead setting
    ]

    def __init__(self):
        self.result = StrategyAnalysisResult()

    def analyze_code(self, code: str) -> StrategyAnalysisResult:
        """
        Analyze strategy code for potential issues.

        Args:
            code: Strategy source code (Python or PineScript-like)

        Returns:
            StrategyAnalysisResult with detected issues
        """
        self.result = StrategyAnalysisResult()

        # Check for look-ahead patterns
        self._check_lookahead_patterns(code)

        # Check for repainting patterns
        self._check_repaint_patterns(code)

        # Check for TradingView specific issues
        self._check_tradingview_patterns(code)

        # Check for known repainting indicators
        self._check_repainting_indicators(code)

        # Analyze Python AST if valid Python
        self._analyze_python_ast(code)

        # Set summary flags
        self._set_summary_flags()

        return self.result

    def analyze_strategy_function(self, func) -> StrategyAnalysisResult:
        """
        Analyze a strategy function object.

        Args:
            func: Strategy function or callable

        Returns:
            StrategyAnalysisResult with detected issues
        """
        import inspect

        try:
            source = inspect.getsource(func)
            return self.analyze_code(source)
        except (TypeError, OSError):
            # Can't get source code
            self.result = StrategyAnalysisResult()
            self.result.warnings.append(
                AnalysisWarning(
                    code="SRC_001",
                    level=WarningLevel.INFO,
                    message="Could not retrieve source code for analysis",
                )
            )
            return self.result

    def analyze_signals(
        self,
        entry_signals,  # pd.Series
        exit_signals,  # pd.Series
        ohlcv,  # pd.DataFrame with OHLCV data
    ) -> StrategyAnalysisResult:
        """
        Analyze generated signals for look-ahead bias at runtime.

        This checks if signals could only have been generated with future knowledge.

        Args:
            entry_signals: Boolean series of entry signals
            exit_signals: Boolean series of exit signals
            ohlcv: OHLCV DataFrame with DatetimeIndex

        Returns:
            StrategyAnalysisResult with detected issues
        """
        import numpy as np
        import pandas as pd

        self.result = StrategyAnalysisResult()

        if not isinstance(entry_signals, pd.Series) or not isinstance(
            ohlcv, pd.DataFrame
        ):
            return self.result

        # Check 1: Signal generated on bar where exact high/low was touched
        # This is suspicious as it implies knowing the bar's range in advance
        try:
            entry_mask = entry_signals.fillna(False).astype(bool)
            if entry_mask.any():
                entry_bars = ohlcv.loc[entry_mask]

                # Check if many entries happened at exact high/low (statistically unlikely)
                # Allow some tolerance for common price levels
                at_high = np.isclose(
                    entry_bars["close"], entry_bars["high"], rtol=0.0001
                )
                at_low = np.isclose(entry_bars["close"], entry_bars["low"], rtol=0.0001)

                exact_edge_ratio = (at_high.sum() + at_low.sum()) / len(entry_bars)

                if (
                    exact_edge_ratio > 0.3
                ):  # More than 30% at exact high/low is suspicious
                    self.result.has_lookahead_bias = True
                    self.result.uses_high_low_of_current_bar = True
                    self.result.warnings.append(
                        AnalysisWarning(
                            code="RUNTIME_001",
                            level=WarningLevel.WARNING,
                            message=f"{exact_edge_ratio:.1%} of entries at exact bar high/low - possible look-ahead",
                            suggestion="Ensure entries use bar open or previous bar data",
                        )
                    )
        except Exception:
            pass

        # Check 2: Perfect win rate (> 90%) is suspicious
        # This often indicates overfitting or look-ahead
        try:
            wins = 0
            losses = 0
            in_trade = False
            entry_price = 0.0

            for i in range(len(ohlcv)):
                if not in_trade and entry_signals.iloc[i]:
                    in_trade = True
                    entry_price = ohlcv["close"].iloc[i]
                elif in_trade and (
                    exit_signals.iloc[i] if exit_signals is not None else False
                ):
                    exit_price = ohlcv["close"].iloc[i]
                    if exit_price > entry_price:
                        wins += 1
                    else:
                        losses += 1
                    in_trade = False

            total_trades = wins + losses
            if total_trades >= 20:
                win_rate = wins / total_trades
                if win_rate > 0.9:
                    self.result.has_lookahead_bias = True
                    self.result.warnings.append(
                        AnalysisWarning(
                            code="RUNTIME_002",
                            level=WarningLevel.WARNING,
                            message=f"Win rate {win_rate:.1%} is unusually high - possible look-ahead or overfitting",
                            suggestion="Validate on out-of-sample data",
                        )
                    )
        except Exception:
            pass

        self._set_summary_flags()
        return self.result

    def _check_lookahead_patterns(self, code: str) -> None:
        """Check code for look-ahead patterns"""
        lines = code.split("\n")

        for pattern, warning_code, message in self.LOOKAHEAD_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    self.result.warnings.append(
                        AnalysisWarning(
                            code=warning_code,
                            level=WarningLevel.WARNING,
                            message=message,
                            line_number=line_num,
                            suggestion="Use historical data only (e.g., shift(1) instead of shift(-1))",
                        )
                    )
                    self.result.has_lookahead_bias = True

    def _check_repaint_patterns(self, code: str) -> None:
        """Check code for repainting patterns"""
        lines = code.split("\n")

        for pattern, warning_code, message in self.REPAINT_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    self.result.warnings.append(
                        AnalysisWarning(
                            code=warning_code,
                            level=WarningLevel.WARNING,
                            message=message,
                            line_number=line_num,
                            suggestion="Use previous bar values for entry decisions",
                        )
                    )
                    self.result.is_repainting = True

    def _check_tradingview_patterns(self, code: str) -> None:
        """Check for TradingView-specific issues"""
        lines = code.split("\n")

        for pattern, warning_code, message in self.TRADINGVIEW_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    level = (
                        WarningLevel.INFO
                        if warning_code == "TV_002"
                        else WarningLevel.WARNING
                    )
                    self.result.warnings.append(
                        AnalysisWarning(
                            code=warning_code,
                            level=level,
                            message=message,
                            line_number=line_num,
                        )
                    )
                    if warning_code == "TV_001":
                        self.result.uses_request_security = True

    def _check_repainting_indicators(self, code: str) -> None:
        """Check for known repainting indicators"""
        code_lower = code.lower()

        for indicator in self.REPAINTING_INDICATORS:
            if indicator.lower() in code_lower:
                self.result.warnings.append(
                    AnalysisWarning(
                        code="INDICATOR_001",
                        level=WarningLevel.INFO,
                        message=f"'{indicator}' indicator found - may repaint depending on usage",
                        suggestion=f"Ensure {indicator} uses confirmed bars only",
                    )
                )

    def _analyze_python_ast(self, code: str) -> None:
        """Analyze Python code using AST for deeper analysis"""
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Check for iloc with negative index (future access)
                if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.UnaryOp):
                    if isinstance(node.slice.op, ast.USub):
                        if isinstance(node.slice.operand, ast.Constant):
                            val = node.slice.operand.value
                            if isinstance(val, int) and val > 0:
                                self.result.warnings.append(
                                    AnalysisWarning(
                                        code="AST_001",
                                        level=WarningLevel.WARNING,
                                        message=f"Negative index [-{val}] may indicate future data access",
                                        line_number=node.lineno,
                                    )
                                )

                # Check for DataFrame operations that might leak
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    if attr_name in ("pct_change", "diff", "rolling"):
                        # These are OK if used properly
                        pass
                    elif attr_name == "apply":
                        # Custom apply might have issues
                        self.result.warnings.append(
                            AnalysisWarning(
                                code="AST_002",
                                level=WarningLevel.INFO,
                                message="DataFrame.apply() - ensure function doesn't access future data",
                                line_number=node.lineno,
                            )
                        )

        except SyntaxError:
            # Not valid Python, skip AST analysis
            pass

    def _set_summary_flags(self) -> None:
        """Set summary flags based on detected warnings"""
        for warning in self.result.warnings:
            if warning.level in (WarningLevel.ERROR, WarningLevel.CRITICAL):
                self.result.has_data_leakage = True

            if "forward" in warning.message.lower():
                self.result.has_forward_fill = True

            if (
                "close" in warning.message.lower()
                and "current" in warning.message.lower()
            ):
                self.result.uses_close_for_entry_on_same_bar = True


def analyze_strategy(code_or_func) -> StrategyAnalysisResult:
    """
    Convenience function to analyze a strategy.

    Args:
        code_or_func: Either source code string or a function object

    Returns:
        StrategyAnalysisResult with detected issues
    """
    analyzer = StrategyAnalyzer()

    if callable(code_or_func):
        return analyzer.analyze_strategy_function(code_or_func)
    elif isinstance(code_or_func, str):
        return analyzer.analyze_code(code_or_func)
    else:
        result = StrategyAnalysisResult()
        result.warnings.append(
            AnalysisWarning(
                code="INPUT_001",
                level=WarningLevel.ERROR,
                message="Invalid input - expected code string or function",
            )
        )
        return result
