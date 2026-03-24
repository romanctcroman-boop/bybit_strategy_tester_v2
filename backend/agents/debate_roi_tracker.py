"""
Debate ROI Tracker.

Measures whether the multi-agent MAD debate (ConsensusNode: 3×DeepSeek + 1×Qwen critic)
produces better strategies than single-agent best-of selection.

DATA MODEL:
    Each pipeline run records one DebateRun:
      - with_debate: bool — was ConsensusNode active?
      - symbol / timeframe — market context
      - sharpe_ratio / max_drawdown / total_return / trade_count — backtest quality
      - llm_call_count / total_cost_usd — efficiency

STORAGE:
    SQLite at data/debate_roi.db (configurable via DEBATE_ROI_DB env var).
    Falls back to in-memory when DB path is unavailable (test mode).

USAGE:
    tracker = DebateROITracker()
    tracker.record(run)
    summary = tracker.summary()
    roi = tracker.debate_roi()   # positive = debate is better

ANALYSIS:
    debate_roi() returns the average difference in Sharpe ratio between
    with_debate=True runs and with_debate=False runs (higher = debate helps).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "debate_roi.db",
)
_DB_PATH = os.getenv("DEBATE_ROI_DB", _DEFAULT_DB)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DebateRun:
    """Single pipeline run result for ROI tracking."""

    run_id: str
    symbol: str
    timeframe: str
    with_debate: bool
    # Strategy quality — None when backtest was skipped
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    total_return: float | None = None
    trade_count: int | None = None
    # Pipeline efficiency
    llm_call_count: int = 0
    total_cost_usd: float = 0.0
    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    agents: list[str] = field(default_factory=list)
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["agents"] = json.dumps(self.agents)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> DebateRun:
        row = dict(row)
        row["agents"] = json.loads(row.get("agents") or "[]")
        row["with_debate"] = bool(row["with_debate"])
        return cls(**row)


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class DebateROITracker:
    """
    Tracks debate vs no-debate strategy quality over time.

    Thread-safe (uses a threading.Lock around every DB write).
    """

    def __init__(self, db_path: str = _DB_PATH, *, in_memory: bool = False) -> None:
        self._lock = threading.Lock()
        if in_memory:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_schema(self._conn)
            self._db_path = ":memory:"
        else:
            self._db_path = db_path
            self._conn = None  # opened per-call for file DBs
            try:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                with self._open() as conn:
                    self._init_schema(conn)
                logger.info(f"DebateROITracker: DB at {db_path}")
            except Exception as exc:
                logger.warning(f"DebateROITracker: falling back to in-memory ({exc})")
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._init_schema(self._conn)
                self._db_path = ":memory:"

    @contextmanager
    def _open(self):
        if self._conn is not None:  # in-memory
            yield self._conn
            return
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS debate_runs (
                run_id          TEXT PRIMARY KEY,
                symbol          TEXT NOT NULL,
                timeframe       TEXT NOT NULL,
                with_debate     INTEGER NOT NULL,
                sharpe_ratio    REAL,
                max_drawdown    REAL,
                total_return    REAL,
                trade_count     INTEGER,
                llm_call_count  INTEGER NOT NULL DEFAULT 0,
                total_cost_usd  REAL NOT NULL DEFAULT 0.0,
                timestamp       TEXT NOT NULL,
                agents          TEXT NOT NULL DEFAULT '[]',
                error_count     INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, run: DebateRun) -> None:
        """Persist a single DebateRun."""
        with self._lock, self._open() as conn:
            d = run.to_dict()
            conn.execute(
                """
                INSERT OR REPLACE INTO debate_runs
                  (run_id, symbol, timeframe, with_debate,
                   sharpe_ratio, max_drawdown, total_return, trade_count,
                   llm_call_count, total_cost_usd, timestamp, agents, error_count)
                VALUES
                  (:run_id, :symbol, :timeframe, :with_debate,
                   :sharpe_ratio, :max_drawdown, :total_return, :trade_count,
                   :llm_call_count, :total_cost_usd, :timestamp, :agents, :error_count)
                """,
                d,
            )

    def record_from_state(
        self,
        state,  # AgentState
        *,
        run_id: str,
        symbol: str,
        timeframe: str,
        with_debate: bool,
    ) -> DebateRun:
        """
        Convenience: build a DebateRun from an AgentState and record it.

        Args:
            state: AgentState returned by run_strategy_pipeline()
            run_id: Unique identifier for this run (e.g. UUID or timestamp)
            symbol: Trading symbol (e.g. "BTCUSDT")
            timeframe: Candle interval (e.g. "15")
            with_debate: Whether ConsensusNode was active

        Returns:
            The DebateRun that was recorded
        """
        backtest = state.results.get("backtest") or {}
        metrics = backtest.get("metrics") or {}

        run = DebateRun(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            with_debate=with_debate,
            sharpe_ratio=metrics.get("sharpe_ratio"),
            max_drawdown=metrics.get("max_drawdown"),
            total_return=metrics.get("total_return"),
            trade_count=metrics.get("total_trades"),
            llm_call_count=state.llm_call_count,
            total_cost_usd=state.total_cost_usd,
            agents=list(state.context.get("agents", [])),
            error_count=len(state.errors),
        )
        self.record(run)
        return run

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def all_runs(self) -> list[DebateRun]:
        """Return all recorded runs."""
        with self._open() as conn:
            rows = conn.execute("SELECT * FROM debate_runs ORDER BY timestamp").fetchall()
        return [DebateRun.from_row(dict(r)) for r in rows]

    def runs_for(self, *, with_debate: bool) -> list[DebateRun]:
        """Return runs filtered by debate flag."""
        with self._open() as conn:
            rows = conn.execute(
                "SELECT * FROM debate_runs WHERE with_debate = ? ORDER BY timestamp",
                (int(with_debate),),
            ).fetchall()
        return [DebateRun.from_row(dict(r)) for r in rows]

    def count(self) -> dict[str, int]:
        """Return total run counts."""
        with self._open() as conn:
            total = conn.execute("SELECT COUNT(*) FROM debate_runs").fetchone()[0]
            debate = conn.execute("SELECT COUNT(*) FROM debate_runs WHERE with_debate = 1").fetchone()[0]
        return {"total": total, "with_debate": debate, "without_debate": total - debate}

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def debate_roi(self) -> float | None:
        """
        Compute average Sharpe delta: avg(sharpe | with_debate=True) - avg(sharpe | without).

        Returns:
            Positive value = debate produces better strategies.
            None if insufficient data (< 1 run in either group with Sharpe data).
        """
        with_runs = [r.sharpe_ratio for r in self.runs_for(with_debate=True) if r.sharpe_ratio is not None]
        without_runs = [r.sharpe_ratio for r in self.runs_for(with_debate=False) if r.sharpe_ratio is not None]
        if not with_runs or not without_runs:
            return None
        return sum(with_runs) / len(with_runs) - sum(without_runs) / len(without_runs)

    def cost_overhead(self) -> float | None:
        """
        Average extra LLM calls when debate is enabled vs disabled.

        Returns:
            Positive = debate uses more calls (expected — 4 agents vs 1).
            None if insufficient data.
        """
        with_calls = [r.llm_call_count for r in self.runs_for(with_debate=True)]
        without_calls = [r.llm_call_count for r in self.runs_for(with_debate=False)]
        if not with_calls or not without_calls:
            return None
        return sum(with_calls) / len(with_calls) - sum(without_calls) / len(without_calls)

    def summary(self) -> dict[str, Any]:
        """
        Return a human-readable summary dict for reporting.

        Example::

            {
                "counts": {"total": 42, "with_debate": 21, "without_debate": 21},
                "debate_roi_sharpe": 0.12,
                "cost_overhead_calls": 3.4,
                "avg_cost_usd": {"with_debate": 0.006, "without_debate": 0.002},
                "sufficient_data": True,
            }
        """
        counts = self.count()
        roi = self.debate_roi()
        overhead = self.cost_overhead()

        def _avg_cost(with_debate: bool) -> float | None:
            runs = [r.total_cost_usd for r in self.runs_for(with_debate=with_debate)]
            return sum(runs) / len(runs) if runs else None

        return {
            "counts": counts,
            "debate_roi_sharpe": roi,
            "cost_overhead_calls": overhead,
            "avg_cost_usd": {
                "with_debate": _avg_cost(True),
                "without_debate": _avg_cost(False),
            },
            "sufficient_data": roi is not None,
        }


# ---------------------------------------------------------------------------
# Global singleton (lazy)
# ---------------------------------------------------------------------------

_tracker: DebateROITracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> DebateROITracker:
    """Get or create the global DebateROITracker singleton."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = DebateROITracker()
    return _tracker
