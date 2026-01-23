from backend.services.advanced_backtesting.engine import (
    AdvancedBacktestEngine,
    BacktestConfig,
)


def make_candle(
    close: float, high: float = None, low: float = None, symbol: str = "BTCUSDT"
):
    return {
        "symbol": symbol,
        "open": close,
        "high": high if high is not None else close,
        "low": low if low is not None else close,
        "close": close,
        "volume": 1_000_000,
    }


def test_short_without_quantity_opens_and_closes():
    cfg = BacktestConfig(
        initial_capital=10_000,
        leverage=5.0,
        max_position_size=0.2,
        max_drawdown_limit=1.0,
        daily_loss_limit=1.0,
        maker_fee=0.0,
        taker_fee=0.0,
        apply_funding=False,
    )
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(99)]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "short"}
        if candle["close"] == 99:
            return {"action": "close"}
        return None

    result = engine.run(data, strat)

    assert result["trades"]["total"] == 1
    trade = result["all_trades"][0]
    assert trade["side"] == "short"
    assert trade["quantity"] > 0


def test_stop_loss_triggers_exit():
    cfg = BacktestConfig(initial_capital=10_000, leverage=1.0)
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(95, low=94)]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "buy", "stop_loss": 98}
        return None

    result = engine.run(data, strat)

    assert result["trades"]["total"] == 1
    trade = result["all_trades"][0]
    # Exit price should be at or below stop (with slippage it can differ slightly)
    assert trade["exit_price"] <= 98 + 1e-6


def test_position_limit_blocks_new_entries():
    cfg = BacktestConfig(initial_capital=10_000, leverage=1.0, position_limit=0)
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(101)]

    def strat(candle, _state):
        return {"action": "buy"}

    result = engine.run(data, strat)

    # No trades should be executed because position_limit=0 blocks openings
    assert result["trades"]["total"] == 0


def test_profit_factor_capped_when_no_losses():
    cfg = BacktestConfig(initial_capital=10_000, leverage=1.0)
    engine = AdvancedBacktestEngine(cfg)

    # Need at least 4 candles for entry/exit to fill with current engine pipeline
    data = [
        make_candle(100),
        make_candle(101),
        make_candle(110),
        make_candle(110),
    ]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "buy"}
        if candle["close"] == 110 and _state.get("position"):
            return {"action": "close"}
        return None

    result = engine.run(data, strat)

    assert result["performance"]["profit_factor"] == 100.0


def test_liquidation_triggers_when_equity_below_maintenance():
    cfg = BacktestConfig(
        initial_capital=1_000,
        leverage=5.0,
        maintenance_margin=0.02,
        liquidation_penalty_pct=0.0,
        apply_funding=False,
    )
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(50), make_candle(40)]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "buy"}
        return None

    result = engine.run(data, strat)

    assert result["events"]["liquidations"] == 1
    assert result["trades"]["total"] == 1
    trade = result["all_trades"][0]
    assert trade["reason"] == "liquidation"
    assert trade["pnl"] < 0


def test_funding_is_applied_for_longs():
    cfg = BacktestConfig(
        initial_capital=1_000,
        leverage=1.0,
        funding_rate=0.01,
        funding_interval_candles=1,
        apply_funding=True,
    )
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(100), make_candle(100)]

    def strat(candle, _state):
        if candle["close"] == 100 and not _state.get("position"):
            return {"action": "buy"}
        if candle["close"] == 100 and _state.get("position"):
            return {"action": "close"}
        return None

    result = engine.run(data, strat)

    assert result["costs"]["total_funding"] != 0
    assert result["performance"]["final_capital"] < cfg.initial_capital


def test_sharpe_is_finite_and_clipped():
    cfg = BacktestConfig(initial_capital=10_000, leverage=1.0)
    engine = AdvancedBacktestEngine(cfg)

    data = [make_candle(100), make_candle(100.1), make_candle(100.2)]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "buy"}
        if candle["close"] == 100.2:
            return {"action": "close"}
        return None

    result = engine.run(data, strat)

    sharpe = result["performance"]["sharpe_ratio"]
    assert isinstance(sharpe, float)
    assert -25 <= sharpe <= 25


def test_funding_long_pays_short_receives():
    cfg = BacktestConfig(
        initial_capital=1_000,
        leverage=1.0,
        funding_rate=0.01,
        funding_interval_candles=1,
        apply_funding=True,
    )
    # Сценарий 1: long платит
    engine = AdvancedBacktestEngine(cfg)
    data_long = [
        make_candle(100),
        make_candle(100),
        make_candle(100),
        make_candle(100),
        make_candle(100),
    ]

    state = {"close_sent": False}

    def strat_long(candle, _state):
        # buy на первой свече, закрытие через две свечи (учитываем задержку исполнения)
        if not _state.get("position") and len(engine.trades) == 0:
            return {"action": "buy"}
        if (
            _state.get("position")
            and len(engine.trades) == 0
            and not state["close_sent"]
        ):
            state["close_sent"] = True
            return {"action": "close"}
        return None

    result_long = engine.run(data_long, strat_long)
    long_trade = result_long["all_trades"][0]
    assert long_trade["funding_fees"] > 0  # long платит

    # Сценарий 2: short получает
    engine_short = AdvancedBacktestEngine(cfg)
    data_short = [
        make_candle(100),
        make_candle(100),
        make_candle(100),
        make_candle(100),
        make_candle(100),
        make_candle(100),
    ]

    state_short = {"close_sent": False}

    def strat_short(candle, _state):
        # short на первой свече, закрытие через две свечи
        if not _state.get("position") and len(engine_short.trades) == 0:
            return {"action": "short"}
        if (
            _state.get("position")
            and len(engine_short.trades) == 0
            and not state_short["close_sent"]
        ):
            state_short["close_sent"] = True
            return {"action": "close"}
        return None

    result_short = engine_short.run(data_short, strat_short)
    short_trade = result_short["all_trades"][0]
    assert short_trade["funding_fees"] < 0  # short получает


def test_liquidation_penalty_is_applied():
    cfg = BacktestConfig(
        initial_capital=1_000,
        leverage=5.0,
        maintenance_margin=0.02,
        liquidation_penalty_pct=0.01,
        apply_funding=False,
    )
    engine = AdvancedBacktestEngine(cfg)

    # Добавляем промежуточную свечу для исполнения ордера и резкого падения
    data = [make_candle(100), make_candle(100), make_candle(40)]

    def strat(candle, _state):
        if candle["close"] == 100:
            return {"action": "buy"}
        return None

    result = engine.run(data, strat)

    assert result["events"]["liquidations"] == 1
    trade = result["all_trades"][0]
    assert trade["reason"] == "liquidation"
    assert trade["liquidation_penalty"] > 0


def test_profit_factor_with_wins_and_losses():
    cfg = BacktestConfig(
        initial_capital=10_000,
        leverage=5.0,
        max_position_size=0.1,
        max_drawdown_limit=1.0,
        daily_loss_limit=1.0,
        position_limit=2,
        maker_fee=0.0,
        taker_fee=0.0,
        apply_funding=False,
    )
    engine = AdvancedBacktestEngine(cfg)

    data = [
        make_candle(100),
        make_candle(100),
        make_candle(120),
        make_candle(120),
        make_candle(101),
        make_candle(101),
        make_candle(99),
        make_candle(99),
    ]

    call = {"i": 0}

    def strat(candle, _state):
        i = call["i"]
        call["i"] += 1

        # Trade 1: win (signal buy at c0, close at c2)
        if i == 0:
            return {"action": "buy"}
        if i == 2:
            return {"action": "close"}

        # Trade 2: loss (signal buy at c4, close at c6)
        if i == 4:
            return {"action": "buy"}
        if i == 6:
            return {"action": "close"}
        return None

    result = engine.run(data, strat)

    pf = result["performance"]["profit_factor"]
    assert result["trades"]["total"] == 2
    pnls = [t["pnl"] for t in result["all_trades"]]
    assert pnls[0] > 0
    assert pnls[1] < 0

    pf_manual = sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))
    assert pf == round(pf_manual, 2)
    assert pf > 1.0
    assert pf < 100
