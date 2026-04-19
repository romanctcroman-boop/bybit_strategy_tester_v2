"""
Tests for DCA engine chart rendering fields:

  dca_levels      – per-order fill details [{level, time, price, size_usd}]
                    drives the G1..GN markers on the price chart
  dca_grid_prices – all planned G2..GN trigger prices (dashed grid lines)
  tp_price        – take-profit level (green horizontal line)
  sl_price        – stop-loss level   (red   horizontal line)
  order_fills     – raw fills on DCATradeRecord before model conversion

NOTE on units
  BacktestConfig.take_profit and .stop_loss are FRACTIONS  (0.015 = 1.5%)
  Engine stores them directly as _take_profit_pct / _stop_loss_pct
  Formula in _close_position:
      _tp_price = avg * (1 + _take_profit_pct)   [long]
      _sl_price = avg * (1 - _stop_loss_pct)     [long]

Engine invocation pattern used in all tests:
  engine.run_from_config(config, ohlcv)
  model_trades = engine._convert_trades_to_model(ohlcv)
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

_TP = 0.015  # 1.5 % (fraction) — default TP for most tests
_SL = 0.08  # 8.0 % (fraction) — large enough not to stop out on test OHLCV


def _make_ohlcv(start: float, end: float, n: int = 120) -> pd.DataFrame:
    """Deterministic OHLCV with linear price trend, UTC timestamps, 1-hour bars."""
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    prices = np.linspace(start, end, n)
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.3,
            "low": prices - 0.5,  # dip below grid prices → fills DCA orders
            "close": prices,
            "volume": np.ones(n) * 500.0,
        },
        index=dates,
    )


def _make_ohlcv_with_signals(entry_price: float = 100.0, trend: float = 1.0, n: int = 150) -> pd.DataFrame:
    """
    OHLCV with a deliberate price pattern for DCA grid testing.

    Layout:
      bars 0-9   : flat at entry_price (warm-up / pre-signal)
      bar  10    : signal bar (entry happens here or next)
      bars 10..n : linear drift by `trend` percent total

    The 'low' on each bar is set 0.5 below close so that DCA grid orders
    placed at entry_price * (1 - k*grid_size/100) will be filled as the
    price falls.  For a downtrend (trend < 0), bars after entry drift down
    and the grid orders fill naturally.
    """
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    prices = np.empty(n)
    prices[:10] = entry_price  # flat warm-up
    end_price = entry_price * (1.0 + trend / 100.0)
    prices[10:] = np.linspace(entry_price, end_price, n - 10)
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices + 0.3,
            "low": prices - 1.0,  # wide enough to fill grid orders
            "close": prices,
            "volume": np.ones(n) * 500.0,
        },
        index=dates,
    )


# ─── mock custom strategy ────────────────────────────────────────────────────


class _FixedSignalStrategy:
    """
    Minimal custom-strategy shim.

    Injects a single long (signal=1) or short (signal=-1) at `entry_bar`.
    The DCAEngine checks `_custom_strategy` before calling the registered
    strategy, so this bypasses RSI entirely and guarantees a trade.
    """

    def __init__(self, direction: str = "long", entry_bar: int = 10):
        self._direction = direction
        self._entry_bar = entry_bar

    def generate_signals(self, df: pd.DataFrame):
        """Return a pd.DataFrame with a 'signal' column — a format accepted by the engine."""
        signals = pd.DataFrame({"signal": np.zeros(len(df), dtype=float)}, index=df.index)
        if self._entry_bar < len(df):
            signals.loc[df.index[self._entry_bar], "signal"] = 1.0 if self._direction == "long" else -1.0
        return signals


# ─── config / run helpers ────────────────────────────────────────────────────


def _make_config(ohlcv, *, order_count=4, grid_size=2.0, tp=_TP, sl=_SL, direction="long", capital=1000.0):
    """Return a BacktestConfig for DCAEngine.run_from_config()."""
    from backend.backtesting.models import BacktestConfig, StrategyType

    return BacktestConfig(
        symbol="BTCUSDT",
        interval="1h",
        start_date=ohlcv.index[0],
        end_date=ohlcv.index[-1],
        strategy_type=StrategyType.RSI,
        strategy_params={"period": 5, "overbought": 70, "oversold": 30},
        initial_capital=capital,
        leverage=1,
        take_profit=tp,
        stop_loss=sl,
        dca_enabled=True,
        dca_direction=direction,
        dca_order_count=order_count,
        dca_grid_size_percent=grid_size,
        dca_martingale_coef=1.0,
        dca_martingale_mode="multiply_each",
        dca_safety_close_enabled=False,
        dca_drawdown_threshold=90.0,  # max allowed; safety_close=False so irrelevant
    )


def _run(ohlcv, config, *, direction: str = "long", entry_bar: int = 10):
    """Run engine with a forced signal and return (model_trades, engine)."""
    from backend.backtesting.engines.dca_engine import DCAEngine

    engine = DCAEngine()
    # Pass forced signal as custom_strategy so run_from_config stores it correctly
    forced = _FixedSignalStrategy(direction=direction, entry_bar=entry_bar)
    engine.run_from_config(config, ohlcv, custom_strategy=forced)
    return engine._convert_trades_to_model(ohlcv), engine


def _first_trade(ohlcv, config, *, direction: str = "long", entry_bar: int = 10):
    """Return the first model trade.  Fails (not skips) if none generated."""
    trades, engine = _run(ohlcv, config, direction=direction, entry_bar=entry_bar)
    if not trades:
        pytest.fail(
            "Engine produced no trades even with a forced signal. Check OHLCV length, config, or engine internals."
        )
    return trades[0], engine


# ─────────────────────────────────────────────────────────────────────────────
# 1.  DCATradeRecord dataclass (raw, before model conversion)
# ─────────────────────────────────────────────────────────────────────────────


class TestDCATradeRecordDataclass:
    """DCATradeRecord must expose the new chart-rendering fields with correct defaults."""

    def _new_rec(self):
        from backend.backtesting.engines.dca_engine import DCATradeRecord

        return DCATradeRecord()

    def test_order_fills_exists_and_defaults_to_empty_list(self):
        rec = self._new_rec()
        assert hasattr(rec, "order_fills"), "Missing field: order_fills"
        assert rec.order_fills == []

    def test_planned_grid_prices_exists_and_defaults_to_empty_list(self):
        rec = self._new_rec()
        assert hasattr(rec, "planned_grid_prices"), "Missing field: planned_grid_prices"
        assert rec.planned_grid_prices == []

    def test_tp_price_exists_and_defaults_to_none(self):
        rec = self._new_rec()
        assert hasattr(rec, "tp_price"), "Missing field: tp_price"
        assert rec.tp_price is None

    def test_sl_price_exists_and_defaults_to_none(self):
        rec = self._new_rec()
        assert hasattr(rec, "sl_price"), "Missing field: sl_price"
        assert rec.sl_price is None


# ─────────────────────────────────────────────────────────────────────────────
# 2.  models.TradeRecord (Pydantic) chart fields
# ─────────────────────────────────────────────────────────────────────────────


class TestModelTradeRecordSchema:
    """models.TradeRecord must declare tp_price / sl_price / dca_levels / dca_grid_prices."""

    @pytest.fixture
    def _rec(self):
        from backend.backtesting.models import TradeRecord

        return TradeRecord(
            entry_time=datetime(2025, 1, 1),
            exit_time=datetime(2025, 1, 2),
            entry_price=100.0,
            exit_price=101.5,
            pnl=1.5,
            side="long",
        )

    def test_tp_price_field_exists_defaults_none(self, _rec):
        assert hasattr(_rec, "tp_price")
        assert _rec.tp_price is None

    def test_sl_price_field_exists_defaults_none(self, _rec):
        assert hasattr(_rec, "sl_price")
        assert _rec.sl_price is None

    def test_dca_levels_field_exists_defaults_list(self, _rec):
        assert hasattr(_rec, "dca_levels")
        assert isinstance(_rec.dca_levels, list)

    def test_dca_grid_prices_field_exists_defaults_list(self, _rec):
        assert hasattr(_rec, "dca_grid_prices")
        assert isinstance(_rec.dca_grid_prices, list)

    def test_can_set_tp_sl_as_floats(self):
        from backend.backtesting.models import TradeRecord

        rec = TradeRecord(
            entry_time=datetime(2025, 1, 1),
            exit_time=datetime(2025, 1, 2),
            entry_price=100.0,
            exit_price=101.5,
            pnl=1.5,
            side="long",
            tp_price=101.5,
            sl_price=92.0,
        )
        assert rec.tp_price == pytest.approx(101.5)
        assert rec.sl_price == pytest.approx(92.0)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  dca_levels after run_from_config (G1..GN fill details)
# ─────────────────────────────────────────────────────────────────────────────


class TestDcaLevelsStructure:
    """
    Run engine on a downtrend OHLCV so G2/G3 fill, then verify dca_levels.
    SL is set very large (30 %) to prevent premature stop-out.
    """

    @pytest.fixture
    def _trade(self):
        # Forced entry at bar 10; price drifts down so G2/G3/G4 fill; large SL
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-8.0, n=150)
        cfg = _make_config(ohlcv, order_count=4, grid_size=2.5, tp=0.02, sl=0.30)
        t, _ = _first_trade(ohlcv, cfg)
        return t

    def test_dca_levels_is_list(self, _trade):
        assert isinstance(_trade.dca_levels, list)

    def test_has_at_least_g1(self, _trade):
        assert len(_trade.dca_levels) >= 1

    def test_each_fill_has_required_keys(self, _trade):
        for fill in _trade.dca_levels:
            for key in ("level", "time", "price", "size_usd"):
                assert key in fill, f"Missing key '{key}' in fill dict: {fill}"

    def test_g1_level_index_is_1(self, _trade):
        assert _trade.dca_levels[0]["level"] == 1

    def test_levels_are_sequential_starting_at_1(self, _trade):
        for expected, fill in enumerate(_trade.dca_levels, start=1):
            assert fill["level"] == expected

    def test_time_is_valid_iso_string(self, _trade):
        for fill in _trade.dca_levels:
            assert isinstance(fill["time"], str)
            datetime.fromisoformat(fill["time"])  # raises if malformed

    def test_price_is_positive(self, _trade):
        for fill in _trade.dca_levels:
            assert fill["price"] > 0

    def test_size_usd_is_positive(self, _trade):
        for fill in _trade.dca_levels:
            assert fill["size_usd"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# 4.  dca_levels count == dca_orders_filled
# ─────────────────────────────────────────────────────────────────────────────


class TestDcaLevelsCountConsistency:
    """len(dca_levels) must equal dca_orders_filled on every trade record."""

    def test_count_matches_orders_filled(self):
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-10.0, n=150)
        cfg = _make_config(ohlcv, order_count=5, grid_size=2.0, tp=0.02, sl=0.30)
        trades, _ = _run(ohlcv, cfg)
        assert trades, "No trades generated even with forced signal"
        for i, mt in enumerate(trades):
            assert len(mt.dca_levels) == mt.dca_orders_filled, (
                f"Trade {i}: dca_levels={len(mt.dca_levels)} != dca_orders_filled={mt.dca_orders_filled}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 5.  dca_grid_prices (all planned G2..GN trigger prices)
# ─────────────────────────────────────────────────────────────────────────────


class TestDcaGridPrices:
    """dca_grid_prices must have order_count-1 entries, descending, < G1 entry."""

    @pytest.fixture
    def _trade_5_orders(self):
        # Forced long entry at bar 10; price drifts down → G2..G4 fill; large SL
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-14.0, n=200)
        cfg = _make_config(ohlcv, order_count=5, grid_size=2.5, tp=0.03, sl=0.30)
        t, _ = _first_trade(ohlcv, cfg)
        return t

    def test_grid_prices_is_list(self, _trade_5_orders):
        assert isinstance(_trade_5_orders.dca_grid_prices, list)

    def test_count_equals_order_count_minus_one(self, _trade_5_orders):
        """5 orders → G2..G5 = 4 grid prices."""
        assert len(_trade_5_orders.dca_grid_prices) == 4, (
            f"Expected 4 planned grid prices, got {len(_trade_5_orders.dca_grid_prices)}"
        )

    def test_all_grid_prices_positive(self, _trade_5_orders):
        for i, gp in enumerate(_trade_5_orders.dca_grid_prices, start=2):
            assert gp > 0, f"G{i} price must be > 0, got {gp}"

    def test_grid_prices_descending_for_long(self, _trade_5_orders):
        """G2 > G3 > G4 > G5 for a long grid."""
        gps = _trade_5_orders.dca_grid_prices
        for i in range(len(gps) - 1):
            assert gps[i] > gps[i + 1], f"G{i + 2}={gps[i]:.4f} should be > G{i + 3}={gps[i + 1]:.4f}"

    def test_all_grid_prices_below_g1_entry(self, _trade_5_orders):
        """For a long grid every planned level must be below the G1 entry price."""
        g1 = _trade_5_orders.dca_levels[0]["price"]
        for i, gp in enumerate(_trade_5_orders.dca_grid_prices, start=2):
            assert gp < g1, f"G{i} planned {gp:.4f} must be < G1 entry {g1:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# 6.  tp_price (long trade)
# ─────────────────────────────────────────────────────────────────────────────


class TestTPPriceLong:
    """tp_price must be set, positive, above avg entry, and match the formula."""

    @pytest.fixture
    def _trade_and_engine(self):
        # Forced entry at bar 10; uptrend so TP fires; large SL so no premature stop
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=120)
        cfg = _make_config(ohlcv, order_count=4, grid_size=2.0, tp=_TP, sl=_SL)
        return _first_trade(ohlcv, cfg)

    def test_tp_price_not_none(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.tp_price is not None, "tp_price must not be None when TP is configured"

    def test_tp_price_is_positive(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.tp_price > 0

    def test_tp_price_above_avg_entry_for_long(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.tp_price > trade.dca_avg_entry_price, (
            f"Long TP {trade.tp_price:.4f} should be > avg entry {trade.dca_avg_entry_price:.4f}"
        )

    def test_tp_price_formula(self, _trade_and_engine):
        """tp = avg_entry * (1 + _take_profit_pct)  [stored as fraction]."""
        trade, engine = _trade_and_engine
        pct = engine._take_profit_pct  # e.g. 0.015
        expected = trade.dca_avg_entry_price * (1.0 + pct)
        assert trade.tp_price == pytest.approx(expected, rel=1e-5), (
            f"TP formula mismatch: expected {expected:.6f}, got {trade.tp_price:.6f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7.  sl_price (long trade)
# ─────────────────────────────────────────────────────────────────────────────


class TestSLPriceLong:
    """sl_price must be set, positive, below avg entry, and match the formula."""

    @pytest.fixture
    def _trade_and_engine(self):
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=120)
        cfg = _make_config(ohlcv, order_count=4, grid_size=2.0, tp=_TP, sl=_SL)
        return _first_trade(ohlcv, cfg)

    def test_sl_price_not_none(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.sl_price is not None, "sl_price must not be None when SL is configured"

    def test_sl_price_is_positive(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.sl_price > 0

    def test_sl_price_below_avg_entry_for_long(self, _trade_and_engine):
        trade, _ = _trade_and_engine
        assert trade.sl_price < trade.dca_avg_entry_price, (
            f"Long SL {trade.sl_price:.4f} should be < avg entry {trade.dca_avg_entry_price:.4f}"
        )

    def test_sl_price_formula(self, _trade_and_engine):
        """sl = avg_entry * (1 - _stop_loss_pct)  [stored as fraction]."""
        trade, engine = _trade_and_engine
        pct = engine._stop_loss_pct
        expected = trade.dca_avg_entry_price * (1.0 - pct)
        assert trade.sl_price == pytest.approx(expected, rel=1e-5), (
            f"SL formula mismatch: expected {expected:.6f}, got {trade.sl_price:.6f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 8.  TP/SL absent when config omits them
# ─────────────────────────────────────────────────────────────────────────────


class TestTPSLNoneWhenOmitted:
    """tp_price and sl_price must be None when take_profit/stop_loss are not set."""

    def test_both_none_when_config_omits_tp_and_sl(self):
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=120)
        cfg = _make_config(ohlcv, order_count=3, grid_size=2.0, tp=None, sl=None)
        trades, _ = _run(ohlcv, cfg)
        assert trades, "No trades generated even with forced signal"
        for mt in trades:
            assert mt.tp_price is None, f"tp_price should be None when TP not configured, got {mt.tp_price}"
            assert mt.sl_price is None, f"sl_price should be None when SL not configured, got {mt.sl_price}"


# ─────────────────────────────────────────────────────────────────────────────
# 9.  Short trade: TP below entry, SL above entry
# ─────────────────────────────────────────────────────────────────────────────


class TestShortTradeTPSL:
    """For short trades the TP/SL directions are reversed."""

    @pytest.fixture
    def _short_trade(self):
        # Forced short entry at bar 10; price falls → short TP fires
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-5.0, n=100)
        cfg = _make_config(ohlcv, order_count=3, grid_size=1.5, tp=_TP, sl=_SL, direction="short")
        return _first_trade(ohlcv, cfg, direction="short")

    def test_short_tp_below_avg_entry(self, _short_trade):
        trade, _ = _short_trade
        if trade.tp_price is None:
            pytest.skip("tp_price not set for this trade")
        assert trade.tp_price < trade.dca_avg_entry_price, (
            f"Short TP {trade.tp_price:.4f} must be < avg entry {trade.dca_avg_entry_price:.4f}"
        )

    def test_short_sl_above_avg_entry(self, _short_trade):
        trade, _ = _short_trade
        if trade.sl_price is None:
            pytest.skip("sl_price not set for this trade")
        assert trade.sl_price > trade.dca_avg_entry_price, (
            f"Short SL {trade.sl_price:.4f} must be > avg entry {trade.dca_avg_entry_price:.4f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 10.  Single-order trade (G1 only, no DCA fills)
# ─────────────────────────────────────────────────────────────────────────────


class TestSingleOrderTrade:
    """When price hits TP before any DCA order fills, dca_levels has exactly 1 entry."""

    def test_single_fill_has_exactly_one_dca_level(self):
        # TP at 0.5 % fires quickly after entry; G2 at -2.5 % never fills
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=120)
        cfg = _make_config(ohlcv, order_count=5, grid_size=2.5, tp=0.005, sl=0.10)
        trades, _ = _run(ohlcv, cfg)
        if not trades:
            pytest.skip("No trades generated")

        for mt in trades:
            if mt.dca_orders_filled == 1:
                assert len(mt.dca_levels) == 1, f"G1-only trade: expected 1 dca_level, got {len(mt.dca_levels)}"
                assert mt.dca_levels[0]["level"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 11.  sl_type="last_order": SL uses last filled DCA order price, not avg
# ─────────────────────────────────────────────────────────────────────────────


def _make_config_with_sl_type(ohlcv, *, sl_type: str, order_count=4, grid_size=2.0, tp=_TP, sl=_SL):
    """BacktestConfig that includes sl_type (simulating Static SL/TP node setting)."""
    from backend.backtesting.models import BacktestConfig, StrategyType

    return BacktestConfig(
        symbol="BTCUSDT",
        interval="1h",
        start_date=ohlcv.index[0],
        end_date=ohlcv.index[-1],
        strategy_type=StrategyType.RSI,
        strategy_params={"period": 5, "overbought": 70, "oversold": 30},
        initial_capital=1000.0,
        leverage=1,
        take_profit=tp,
        stop_loss=sl,
        sl_type=sl_type,
        dca_enabled=True,
        dca_direction="long",
        dca_order_count=order_count,
        dca_grid_size_percent=grid_size,
        dca_martingale_coef=1.0,
        dca_martingale_mode="multiply_each",
        dca_safety_close_enabled=False,
        dca_drawdown_threshold=90.0,
    )


class TestSlTypeConfiguration:
    """_sl_type is correctly read from BacktestConfig by _configure_from_config."""

    def test_sl_type_defaults_to_average_price(self):
        """When sl_type not provided, engine defaults to 'average_price'."""
        from backend.backtesting.engines.dca_engine import DCAEngine

        engine = DCAEngine()
        assert engine._sl_type == "average_price"

    def test_sl_type_average_price_read_from_config(self):
        """sl_type='average_price' is stored on the engine after configure."""
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=80)
        cfg = _make_config_with_sl_type(ohlcv, sl_type="average_price")
        _, engine = _run(ohlcv, cfg)
        assert engine._sl_type == "average_price"

    def test_sl_type_last_order_read_from_config(self):
        """sl_type='last_order' is stored on the engine after configure."""
        ohlcv = _make_ohlcv_with_signals(100.0, trend=5.0, n=80)
        cfg = _make_config_with_sl_type(ohlcv, sl_type="last_order")
        _, engine = _run(ohlcv, cfg)
        assert engine._sl_type == "last_order"

    def test_invalid_sl_type_falls_back_to_average_price(self):
        """An unrecognised sl_type value is normalised to 'average_price'."""
        from backend.backtesting.engines.dca_engine import DCAEngine

        engine = DCAEngine()

        # Inject a fake config object with bad sl_type
        class _FakeCfg:
            sl_type = "unknown_mode"
            take_profit = None
            stop_loss = None
            taker_fee = 0.0007
            maker_fee = None

        engine._configure_from_config(_FakeCfg())
        assert engine._sl_type == "average_price"


class TestSlTypeLastOrderPriceDifference:
    """
    When sl_type='last_order' and multiple DCA orders have filled, the SL chart
    line (trade.sl_price) must be computed from the last-filled order's price,
    not from the weighted average entry price.

    Setup: 4-order long grid with 3 % grid steps on a downtrend so G2–G4 fill.
    The last filled order (G4) fills at the lowest price; for a long position
    this produces a *lower* SL than if computed from average_entry_price.
    """

    @pytest.fixture
    def _avg_price_trade(self):
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-8.0, n=160)
        cfg = _make_config_with_sl_type(ohlcv, sl_type="average_price", order_count=4, grid_size=3.0, tp=None, sl=0.20)
        trades, engine = _run(ohlcv, cfg)
        assert trades, "No trades for average_price fixture"
        return trades[0], engine

    @pytest.fixture
    def _last_order_trade(self):
        ohlcv = _make_ohlcv_with_signals(100.0, trend=-8.0, n=160)
        cfg = _make_config_with_sl_type(ohlcv, sl_type="last_order", order_count=4, grid_size=3.0, tp=None, sl=0.20)
        trades, engine = _run(ohlcv, cfg)
        assert trades, "No trades for last_order fixture"
        return trades[0], engine

    def test_sl_price_set_for_average_price_mode(self, _avg_price_trade):
        trade, _ = _avg_price_trade
        assert trade.sl_price is not None and trade.sl_price > 0

    def test_sl_price_set_for_last_order_mode(self, _last_order_trade):
        trade, _ = _last_order_trade
        assert trade.sl_price is not None and trade.sl_price > 0

    def test_sl_price_differs_between_modes_when_multiple_orders_filled(self, _avg_price_trade, _last_order_trade):
        """
        If only G1 filled the two modes give the same result (both reference
        the single fill price which equals average).  When G2+ fill, the last
        order price diverges from the average, so the SL prices must differ.
        """
        avg_trade, _ = _avg_price_trade
        lo_trade, _ = _last_order_trade

        if avg_trade.dca_orders_filled < 2:
            pytest.skip("Only G1 filled — modes are indistinguishable for this OHLCV")

        assert avg_trade.sl_price != pytest.approx(lo_trade.sl_price, rel=1e-4), (
            f"With {avg_trade.dca_orders_filled} orders filled, SL from avg "
            f"({avg_trade.sl_price:.4f}) should differ from SL from last order "
            f"({lo_trade.sl_price:.4f})"
        )

    def test_last_order_sl_below_average_price_sl_for_long(self, _avg_price_trade, _last_order_trade):
        """
        For a long grid where later orders fill at lower prices:
        last_order_fill_price < average_entry_price
        ⟹ last_order SL < average_price SL
        """
        avg_trade, _ = _avg_price_trade
        lo_trade, _ = _last_order_trade

        if avg_trade.dca_orders_filled < 2:
            pytest.skip("Only G1 filled — cannot differentiate modes")

        assert lo_trade.sl_price < avg_trade.sl_price, (
            f"last_order SL ({lo_trade.sl_price:.4f}) should be < "
            f"average_price SL ({avg_trade.sl_price:.4f}) for a downtrend long grid"
        )

    def test_last_order_sl_matches_formula(self, _last_order_trade):
        """sl_price = last_filled_order_price * (1 - stop_loss_pct) for long."""
        trade, engine = _last_order_trade
        if trade.sl_price is None:
            pytest.skip("sl_price is None")

        sl_pct = engine._stop_loss_pct
        # The last filled order price comes from the dca_levels list (the last entry)
        assert trade.dca_levels, "Need at least one dca_level to verify last_order formula"
        last_fill_price = trade.dca_levels[-1]["price"]
        expected = last_fill_price * (1.0 - sl_pct)
        assert trade.sl_price == pytest.approx(expected, rel=1e-5), (
            f"last_order SL mismatch: expected {expected:.6f} "
            f"(last fill @ {last_fill_price:.4f} * (1 - {sl_pct})), "
            f"got {trade.sl_price:.6f}"
        )


class TestGetSlBasePriceHelper:
    """Unit tests for DCAEngine._get_sl_base_price()."""

    def _make_engine_with_position(self, sl_type: str, fill_prices: list[float]):
        """
        Create a DCAEngine with a synthetic position having multiple filled orders.
        """
        from unittest.mock import MagicMock

        from backend.backtesting.engines.dca_engine import DCAEngine

        engine = DCAEngine()
        engine._sl_type = sl_type

        # Build mock orders
        orders = []
        for i, fp in enumerate(fill_prices):
            order = MagicMock()
            order.filled = True
            order.fill_price = fp
            order.price = fp
            order.fill_time = i  # sequential
            order.level = i + 1
            orders.append(order)

        pos = MagicMock()
        pos.orders = orders
        pos.average_entry_price = sum(fill_prices) / len(fill_prices)
        engine.position = pos
        return engine

    def test_returns_average_entry_price_in_average_price_mode(self):
        engine = self._make_engine_with_position("average_price", [100.0, 97.0, 94.0])
        result = engine._get_sl_base_price()
        assert result == pytest.approx(97.0)  # simple average of mocked avg

    def test_returns_last_fill_price_in_last_order_mode(self):
        engine = self._make_engine_with_position("last_order", [100.0, 97.0, 94.0])
        result = engine._get_sl_base_price()
        assert result == pytest.approx(94.0)  # last filled price

    def test_returns_avg_when_no_filled_orders_in_last_order_mode(self):
        """Falls back to average_entry_price when no orders are filled."""
        from unittest.mock import MagicMock

        from backend.backtesting.engines.dca_engine import DCAEngine

        engine = DCAEngine()
        engine._sl_type = "last_order"

        pos = MagicMock()
        pos.orders = []  # no filled orders
        pos.average_entry_price = 100.0
        engine.position = pos

        result = engine._get_sl_base_price()
        assert result == pytest.approx(100.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
