"""Tests for backend.optimization.post_grid."""

from __future__ import annotations

from typing import Any

from backend.optimization.post_grid import refine_top_k


def _spec(path: str, low: float, high: float, step: float, type_: str = "int") -> dict[str, Any]:
    return {"param_path": path, "type": type_, "low": low, "high": high, "step": step}


class TestRefineTopK:
    def test_empty_top_returns_empty(self) -> None:
        assert refine_top_k([], [_spec("x", 0, 10, 1)], lambda p: 0.0) == []

    def test_single_center_grid(self) -> None:
        # Quadratic objective with peak at x=5
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": 0.0}]

        def obj(p: dict[str, Any]) -> float:
            return -((p["x"] - 5) ** 2)

        result = refine_top_k(top, specs, obj, pct=0.5, steps_per_param=5)
        assert result, "expected at least the original entry"
        # Best should still be x=5 with score 0
        assert result[0]["params"]["x"] == 5
        assert result[0]["score"] == 0.0

    def test_finds_better_neighbour(self) -> None:
        # Objective peaks at x=7 but Optuna only sampled x=5
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": -4.0}]  # (5-7)^2 = 4

        def obj(p: dict[str, Any]) -> float:
            return -((p["x"] - 7) ** 2)

        # ±50% of [0..10] = ±5 → covers x=10, includes x=7
        result = refine_top_k(top, specs, obj, pct=0.5, steps_per_param=5)
        assert result[0]["score"] > -4.0
        # The best found should be marked as post_grid
        assert result[0]["_source"] == "post_grid"

    def test_max_evals_cap_respected(self) -> None:
        specs = [_spec("x", 0, 100, 1), _spec("y", 0, 100, 1)]
        top = [{"params": {"x": 50, "y": 50}, "score": 0.0}]

        call_count = {"n": 0}

        def obj(p: dict[str, Any]) -> float:
            call_count["n"] += 1
            return float(p["x"] + p["y"])

        refine_top_k(top, specs, obj, pct=0.5, steps_per_param=5, max_evals=10)
        assert call_count["n"] <= 10

    def test_objective_exception_is_swallowed(self) -> None:
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": 0.0}]

        def obj(p: dict[str, Any]) -> float:
            if p["x"] == 6:
                raise RuntimeError("boom")
            return float(p["x"])

        # Must not raise
        result = refine_top_k(top, specs, obj, pct=0.5, steps_per_param=3)
        # Result should still contain the original
        assert any(r["params"] == {"x": 5} for r in result)

    def test_int_type_preserved(self) -> None:
        specs = [_spec("period", 5, 50, 1, "int")]
        top = [{"params": {"period": 14}, "score": 0.5}]
        seen_types: list[type] = []

        def obj(p: dict[str, Any]) -> float:
            seen_types.append(type(p["period"]))
            return 1.0

        refine_top_k(top, specs, obj, pct=0.3, steps_per_param=4)
        # Every evaluated param should be int (from grid) or whatever the original was
        assert all(t is int for t in seen_types)

    def test_progress_callback_called(self) -> None:
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": 0.0}]
        progress_log: list[tuple[int, int, float]] = []

        def cb(done: int, total: int, best: float) -> None:
            progress_log.append((done, total, best))

        refine_top_k(top, specs, lambda p: 1.0, pct=0.4, steps_per_param=3, on_progress=cb)
        assert progress_log
        # done counter monotonically increases
        assert [p[0] for p in progress_log] == sorted(p[0] for p in progress_log)

    def test_progress_callback_failure_does_not_break(self) -> None:
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": 0.0}]

        def cb_bad(*_: object) -> None:
            raise ValueError("bad cb")

        # Must complete without raising
        result = refine_top_k(top, specs, lambda p: 1.0, on_progress=cb_bad)
        assert result

    def test_results_sorted_descending(self) -> None:
        specs = [_spec("x", 0, 10, 1)]
        top = [{"params": {"x": 5}, "score": 0.0}]
        result = refine_top_k(top, specs, lambda p: float(p["x"]))
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)
