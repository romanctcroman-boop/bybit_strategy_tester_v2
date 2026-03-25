"""
GPUOptimizationResult dataclass.

Extracted from gpu_optimizer.py (lines 2529–2543).
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class GPUOptimizationResult:
    """Result of GPU-accelerated grid-search optimization."""

    status: str
    total_combinations: int
    tested_combinations: int
    execution_time_seconds: float
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, Any]
    top_results: list[dict[str, Any]]
    performance_stats: dict[str, Any]
    execution_mode: str
    fallback_reason: str | None = None
