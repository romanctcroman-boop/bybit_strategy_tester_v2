"""Minimal Walk-Forward optimizer stub.

Provides a lightweight implementation to keep Celery tasks functional in dev/CI
without a heavy dependency on a full optimization engine.
"""
from __future__ import annotations
from typing import Any, Dict, List
import asyncio


class WalkForwardAnalyzer:
    def __init__(
        self,
        data: Any,
        initial_capital: float = 10_000.0,
        commission: float = 0.0006,
        is_window_days: int = 120,
        oos_window_days: int = 60,
        step_days: int = 30,
    ) -> None:
        # A very small placeholder that derives a couple of windows from data length
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.is_window_days = is_window_days
        self.oos_window_days = oos_window_days
        self.step_days = step_days
        # Pretend we built windows; at least one to keep tasks happy
        self.windows: List[Dict[str, Any]] = [
            {"idx": 0, "is_range": [0, 1], "oos_range": [2, 2]},
            {"idx": 1, "is_range": [3, 4], "oos_range": [5, 5]},
        ]

    async def run_async(
        self,
        strategy_config: Dict[str, Any],
        param_space: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
    ) -> Dict[str, Any]:
        # Simulate async work
        await asyncio.sleep(0)

        # Produce deterministic dummy results
        window_results = []
        for w in self.windows:
            window_results.append(
                {
                    "window": w,
                    "best_params": {k: (v[0] if v else None) for k, v in param_space.items()},
                    "metrics": {
                        "total_return": 0.05,
                        "sharpe_ratio": 1.0,
                        "max_drawdown": 0.02,
                        "win_rate": 0.55,
                        "total_trades": 10,
                    },
                    "score": 1.0 if metric == "sharpe_ratio" else 0.05,
                }
            )

        return {
            "windows": window_results,
            "summary": {
                "avg_total_return": sum(w["metrics"]["total_return"] for w in window_results) / len(window_results),
                "avg_sharpe": sum(w["metrics"]["sharpe_ratio"] for w in window_results) / len(window_results),
                "best_window_score": max(w["score"] for w in window_results),
            },
        }
from __future__ import annotations
from typing import Dict, Any, List
import asyncio


class WalkForwardAnalyzer:
    """Minimal stub implementation to satisfy optimize_tasks imports and basic flow.

    In a real implementation, this would slice data into IS/OOS windows,
    optimize params on IS, and evaluate on OOS.
    """

    def __init__(self, data: List[Dict[str, Any]], initial_capital: float, commission: float, is_window_days: int, oos_window_days: int, step_days: int) -> None:
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.is_window_days = is_window_days
        self.oos_window_days = oos_window_days
        self.step_days = step_days
        # naive: pretend we have N windows
        self.windows = list(range(max(1, min(5, len(data) // 100))))

    async def run_async(self, strategy_config: Dict[str, Any], param_space: Dict[str, List[Any]], metric: str) -> Dict[str, Any]:
        # Mock processing windows; return synthetic results
        await asyncio.sleep(0)
        windows: List[Dict[str, Any]] = []
        for i, _ in enumerate(self.windows):
            best_params = {k: (v[0] if isinstance(v, list) and v else v) for k, v in param_space.items()}
            windows.append({
                "index": i,
                "best_score": 1.0 - 0.1 * i,
                "best_params": best_params,
            })
        return {
            "metric": metric,
            "windows": windows,
            "summary": {"avg_score": 0.5},
        }
