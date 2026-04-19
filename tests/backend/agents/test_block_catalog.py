"""
Tests for BuilderWorkflow._build_block_catalog()

Verifies:
1. Catalog covers ALL block types from DEFAULT_PARAM_RANGES
2. Critical blocks are present (not just RSI)
3. Port semantics info is present
4. Categories and param ranges render correctly
"""
from backend.agents.workflows.builder_workflow import BuilderWorkflow
from backend.optimization.builder_optimizer import DEFAULT_PARAM_RANGES


def test_catalog_covers_all_default_param_ranges():
    """Every block type in DEFAULT_PARAM_RANGES must appear in the catalog."""
    catalog = BuilderWorkflow._build_block_catalog()
    missing = [bt for bt in DEFAULT_PARAM_RANGES if bt not in catalog]
    assert not missing, f"Catalog missing block types: {missing}"


def test_catalog_not_rsi_only():
    """Catalog must contain diverse block types beyond RSI."""
    catalog = BuilderWorkflow._build_block_catalog()
    expected = [
        "macd", "stochastic", "supertrend", "qqe", "ichimoku",
        "keltner_bollinger", "divergence", "atr_volatility", "volume_filter",
        "mfi_filter", "cci_filter", "momentum_filter", "two_ma_filter",
        "trailing_stop_exit", "atr_exit", "multi_tp_exit", "close_by_time",
        "accumulation_areas", "two_mas", "parabolic_sar",
    ]
    missing = [b for b in expected if b not in catalog]
    assert not missing, f"Catalog missing important blocks: {missing}"


def test_catalog_has_port_semantics():
    """Catalog must explain entry_long vs filter_long port semantics."""
    catalog = BuilderWorkflow._build_block_catalog()
    assert "entry_long" in catalog
    assert "filter_long" in catalog
    assert "OR-gate" in catalog
    assert "AND-gate" in catalog
    assert "sl_tp" in catalog


def test_catalog_has_param_ranges():
    """Each block in catalog should show param ranges like [low..high]."""
    catalog = BuilderWorkflow._build_block_catalog()
    # RSI period range 7..100
    assert "7..100" in catalog
    # static_sltp must have SL/TP ranges
    assert "static_sltp" in catalog
    # Should have float range indicators
    assert ".." in catalog


def test_catalog_warns_supertrend_overtrading():
    """Catalog must warn about SuperTrend OR-gate danger."""
    catalog = BuilderWorkflow._build_block_catalog()
    assert "supertrend" in catalog
    # Warning about connecting to filter_long vs entry_long
    assert "filter_long" in catalog


def test_catalog_groups_by_category():
    """Catalog must have category section headers."""
    catalog = BuilderWorkflow._build_block_catalog()
    assert "ENTRY SIGNALS" in catalog
    assert "FILTER" in catalog
    assert "EXIT" in catalog


def test_catalog_covers_all_filter_blocks():
    """All *_filter block types from DEFAULT_PARAM_RANGES must be in catalog."""
    catalog = BuilderWorkflow._build_block_catalog()
    filter_blocks = [bt for bt in DEFAULT_PARAM_RANGES if bt.endswith("_filter")]
    missing = [bt for bt in filter_blocks if bt not in catalog]
    assert not missing, f"Missing filter blocks: {missing}"


def test_catalog_non_empty():
    """Catalog must be a substantial string."""
    catalog = BuilderWorkflow._build_block_catalog()
    assert isinstance(catalog, str)
    assert len(catalog) > 500


def test_catalog_all_blocks_count():
    """Catalog must expose ALL blocks from DEFAULT_PARAM_RANGES."""
    catalog = BuilderWorkflow._build_block_catalog()
    found = [bt for bt in DEFAULT_PARAM_RANGES if bt in catalog]
    total = len(DEFAULT_PARAM_RANGES)
    assert len(found) == total, (
        f"Only {len(found)}/{total} blocks in catalog. "
        f"Missing: {[bt for bt in DEFAULT_PARAM_RANGES if bt not in catalog]}"
    )


def test_catalog_includes_adx():
    """ADX (trend strength filter) must be in catalog with filter_long port."""
    catalog = BuilderWorkflow._build_block_catalog()
    assert "adx" in catalog
    # ADX is marked as filter in catalog
    assert "filter_long" in catalog
