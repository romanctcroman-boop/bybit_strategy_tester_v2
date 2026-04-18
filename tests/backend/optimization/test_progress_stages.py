"""Tests for optimization pipeline stage tracking (2026-04-19).

Verifies that ``update_optimization_progress(stage=...)`` correctly
records, preserves and transitions through the hardening pipeline
stages consumed by the Strategy Builder UI progress bar.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_progress_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the shared JSON progress file and in-memory caches to a
    throwaway tmp_path so tests don't pollute ``.run/optimizer_progress.json``.
    """
    from backend.optimization import builder_optimizer as bo

    tmp_file = tmp_path / "optimizer_progress.json"
    monkeypatch.setattr(bo, "_PROGRESS_FILE", tmp_file, raising=True)
    monkeypatch.setattr(bo, "_PROGRESS_DIR", tmp_path, raising=True)
    monkeypatch.setattr(bo, "_progress_memory_cache", {}, raising=True)
    monkeypatch.setattr(bo, "_progress_trial_counter", {}, raising=True)
    yield


class TestStageField:
    """The progress entry must expose a ``stage`` key that tracks the
    currently-executing pipeline phase."""

    def test_stage_defaults_to_empty_string_when_not_supplied(self):
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("s1", tested=0, total=100)
        entry = get_optimization_progress("s1")
        assert "stage" in entry
        assert entry["stage"] == ""

    def test_stage_persists_across_incremental_updates(self):
        """Once a stage is set, subsequent updates without ``stage`` must
        preserve the value (so per-trial updates don't clobber the stage
        set by the surrounding pipeline driver)."""
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("s2", stage="searching", tested=0, total=100)
        update_optimization_progress("s2", tested=50, total=100)  # no stage kwarg
        update_optimization_progress("s2", tested=100, total=100)
        entry = get_optimization_progress("s2")
        assert entry["stage"] == "searching"
        assert entry["tested"] == 100

    def test_explicit_stage_transition_overwrites_previous(self):
        from backend.optimization.builder_optimizer import (
            get_optimization_progress,
            update_optimization_progress,
        )

        update_optimization_progress("s3", stage="searching", tested=100, total=100)
        update_optimization_progress("s3", stage="post_grid_refine", tested=0, total=30)
        entry = get_optimization_progress("s3")
        assert entry["stage"] == "post_grid_refine"
        assert entry["total"] == 30

    @pytest.mark.parametrize(
        "stage",
        [
            "loading_data",
            "preparing",
            "searching",
            "post_grid_refine",
            "overfit_guards",
            "finalizing",
            "done",
        ],
    )
    def test_all_documented_stages_round_trip(self, stage: str):
        from backend.optimization.builder_optimizer import (
            OPTIMIZATION_STAGES,
            get_optimization_progress,
            update_optimization_progress,
        )

        assert stage in OPTIMIZATION_STAGES
        update_optimization_progress("s-rt", stage=stage)
        entry = get_optimization_progress("s-rt")
        assert entry["stage"] == stage


class TestStageTransitionFlushesToDisk:
    """Stage transitions must force an immediate disk flush so multi-worker
    uvicorn setups don't show a stale phase."""

    def test_stage_transition_flushes_immediately(self):
        import json

        from backend.optimization import builder_optimizer as bo

        # First call — flush (is_first)
        bo.update_optimization_progress("s-flush", stage="preparing")
        disk1 = json.loads(bo._PROGRESS_FILE.read_text(encoding="utf-8"))
        assert disk1["s-flush"]["stage"] == "preparing"

        # Second call with NEW stage: must flush despite not hitting the
        # trial-counter interval (counter=2, interval=5).
        bo.update_optimization_progress("s-flush", stage="searching")
        disk2 = json.loads(bo._PROGRESS_FILE.read_text(encoding="utf-8"))
        assert disk2["s-flush"]["stage"] == "searching"

    def test_same_stage_repeated_respects_flush_interval(self):
        """When the stage stays the same, the flush-every-N-trials rule
        still applies (we don't want every per-trial call to hit disk)."""
        import json

        from backend.optimization import builder_optimizer as bo

        # Call 1: is_first → flush, stage=searching
        bo.update_optimization_progress("s-int", stage="searching", tested=0, total=100)
        # Calls 2..4: no stage transition, not first, not on interval → no flush
        for i in range(1, 4):
            bo.update_optimization_progress("s-int", tested=i, total=100)

        disk = json.loads(bo._PROGRESS_FILE.read_text(encoding="utf-8"))
        # Disk entry still has stage, but tested is the stale flushed value
        # (0) because no flush happened between calls 2-4.
        assert disk["s-int"]["stage"] == "searching"
        assert disk["s-int"]["tested"] == 0

        # In-memory cache has the latest value.
        mem = bo.get_optimization_progress("s-int")
        assert mem["tested"] == 3
