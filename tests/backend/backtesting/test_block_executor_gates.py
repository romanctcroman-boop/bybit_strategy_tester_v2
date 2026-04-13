"""
Tests for AND/OR/NOT/filter logic gates in block_executor.execute_logic().

Invariants (neutral-element correctness — bug fix B1, 2026-04-13):
    AND gate neutral element = True  (True & x = x)
        → missing input defaults to True, so a single connected input passes through
    OR  gate neutral element = False (False | x = x)
        → missing input defaults to False, already correct before fix
    NOT gate: no inputs → defaults to False → result = True (reasonable sentinel)
    filter block: missing filter defaults to True (pass-through) — same as AND

The original bug: AND gate used _default_bool(fill=False), meaning an unconnected
port blocked all signals. Fixed to fill=True.
"""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series(values: list[bool], index=None) -> pd.Series:
    if index is None:
        index = pd.RangeIndex(len(values))
    return pd.Series(values, index=index, dtype=bool)


def _call(logic_type: str, inputs: dict[str, pd.Series], params: dict | None = None):
    """Thin wrapper around execute_logic()."""
    from backend.backtesting.strategy_builder.block_executor import execute_logic

    return execute_logic(logic_type, params or {}, inputs)


# ---------------------------------------------------------------------------
# AND gate — neutral element = True
# ---------------------------------------------------------------------------


class TestAndGate:
    """execute_logic("and", ...) — unconnected port must default to True."""

    def test_both_inputs_connected(self):
        """Standard two-input AND."""
        a = _series([True, True, False, False])
        b = _series([True, False, True, False])
        result = _call("and", {"a": a, "b": b})["result"]
        expected = [True, False, False, False]
        assert list(result) == expected

    def test_missing_b_passes_a_through(self):
        """
        Only 'a' connected, 'b' missing.
        AND(a, True) == a  — signal passes through unchanged.

        Bug (before fix): AND(a, False) → blocked all signals.
        """
        signal = _series([True, False, True, True])
        result = _call("and", {"a": signal})["result"]
        # With neutral element True: result = signal & True = signal
        assert list(result) == [True, False, True, True], (
            "Missing 'b' must default to True (AND neutral). Before fix it was False, which blocked all signals."
        )

    def test_missing_a_passes_b_through(self):
        """Only 'b' connected; 'a' should default to True."""
        signal = _series([False, True, True, False])
        result = _call("and", {"b": signal})["result"]
        assert list(result) == [False, True, True, False]

    def test_no_inputs_returns_true_series(self):
        """No inputs at all → result = True & True = True."""
        result = _call("and", {})["result"]
        assert bool(result.iloc[0]) is True

    def test_three_inputs_all_connected(self):
        """Optional 'c' port: result = a & b & c."""
        a = _series([True, True, False])
        b = _series([True, False, True])
        c = _series([True, True, True])
        result = _call("and", {"a": a, "b": b, "c": c})["result"]
        assert list(result) == [True, False, False]

    def test_three_inputs_c_missing(self):
        """'c' not present — behaves like 2-input AND."""
        a = _series([True, False, True])
        b = _series([True, True, False])
        result = _call("and", {"a": a, "b": b})["result"]
        assert list(result) == [True, False, False]

    def test_missing_input_does_not_block_true_signal(self):
        """
        Critical regression: a single True signal at bar 2.
        Before fix: AND with missing 'b'=False → result[2] = False (blocked!).
        After fix: AND with missing 'b'=True  → result[2] = True  (passes).
        """
        n = 5
        signal = _series([False, False, True, False, False])
        result = _call("and", {"a": signal})["result"]
        assert result.iloc[2] is True or bool(result.iloc[2]) is True, (
            "AND gate with one missing input must pass the True signal through."
        )
        # All False bars still False
        assert result.iloc[0] is False or bool(result.iloc[0]) is False


# ---------------------------------------------------------------------------
# OR gate — neutral element = False (already correct, regression guard)
# ---------------------------------------------------------------------------


class TestOrGate:
    """execute_logic("or", ...) — unconnected port must default to False."""

    def test_both_inputs_connected(self):
        a = _series([True, True, False, False])
        b = _series([True, False, True, False])
        result = _call("or", {"a": a, "b": b})["result"]
        assert list(result) == [True, True, True, False]

    def test_missing_b_passes_a_through(self):
        """OR(a, False) == a — missing input is neutral for OR."""
        signal = _series([True, False, True, False])
        result = _call("or", {"a": signal})["result"]
        assert list(result) == [True, False, True, False]

    def test_missing_a_passes_b_through(self):
        signal = _series([False, True, False, True])
        result = _call("or", {"b": signal})["result"]
        assert list(result) == [False, True, False, True]

    def test_no_inputs_returns_false(self):
        """No inputs → OR(False, False) = False."""
        result = _call("or", {})["result"]
        assert bool(result.iloc[0]) is False

    def test_three_inputs(self):
        a = _series([True, False, False])
        b = _series([False, True, False])
        c = _series([False, False, True])
        result = _call("or", {"a": a, "b": b, "c": c})["result"]
        assert list(result) == [True, True, True]


# ---------------------------------------------------------------------------
# NOT gate
# ---------------------------------------------------------------------------


class TestNotGate:
    def test_invert_series(self):
        signal = _series([True, False, True])
        result = _call("not", {"input": signal})["result"]
        assert list(result) == [False, True, False]

    def test_no_input_defaults_false_so_result_true(self):
        """NOT(False) = True — reasonable sentinel when input missing."""
        result = _call("not", {})["result"]
        assert bool(result.iloc[0]) is True


# ---------------------------------------------------------------------------
# filter block — missing filter defaults to True (pass-through)
# ---------------------------------------------------------------------------


class TestFilterBlock:
    """filter block: signal & filter — missing filter = True (pass-through)."""

    def test_both_connected(self):
        signal = _series([True, True, False, True])
        filt = _series([True, False, True, True])
        result = _call("filter", {"signal": signal, "filter": filt})["result"]
        assert list(result) == [True, False, False, True]

    def test_missing_filter_passes_signal_through(self):
        """filter defaults to True → result = signal."""
        signal = _series([True, False, True, False])
        result = _call("filter", {"signal": signal})["result"]
        assert list(result) == [True, False, True, False]

    def test_missing_signal_with_filter(self):
        """Signal missing → defaults to False → nothing passes."""
        filt = _series([True, True, True, True])
        result = _call("filter", {"filter": filt})["result"]
        assert list(result) == [False, False, False, False]

    def test_both_missing(self):
        """Both missing → False & True = False."""
        result = _call("filter", {})["result"]
        assert bool(result.iloc[0]) is False


# ---------------------------------------------------------------------------
# AND vs OR neutral-element correctness (side-by-side contract test)
# ---------------------------------------------------------------------------


class TestNeutralElements:
    """
    Parametrized contract: neutral element of each gate.

    AND neutral = True:  AND(signal, True) == signal
    OR  neutral = False: OR(signal, False) == signal
    """

    @pytest.mark.parametrize(
        "logic_type,connected_port,neutral_expected",
        [
            ("and", "a", True),  # AND neutral = True
            ("or", "a", False),  # OR  neutral = False
        ],
    )
    def test_neutral_element(self, logic_type, connected_port, neutral_expected):
        """Missing input must equal the neutral element for the gate type."""
        from backend.backtesting.strategy_builder.block_executor import execute_logic

        n = 6
        signal = _series([True, False, True, False, True, False])
        result = execute_logic(logic_type, {}, {connected_port: signal})["result"]

        # Verify: op(signal, neutral) == signal
        assert list(result) == list(signal), (
            f"{logic_type.upper()} gate: result with missing input (neutral={neutral_expected}) "
            f"must equal the connected signal. Got {list(result)}"
        )
