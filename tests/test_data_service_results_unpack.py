from backend.services.data_service import DataService


class FakeDataService(DataService):
    """A lightweight fake that captures update_backtest calls instead of hitting DB."""

    def __init__(self):
        # don't call super() to avoid creating a real DB session
        self.captured = None

    def update_backtest(self, backtest_id: int, **kwargs):
        # store the payload that would be used to update the DB
        self.captured = {"backtest_id": backtest_id, "payload": kwargs}
        return self.captured


def test_update_backtest_results_unpacks_nested_results():
    ds = FakeDataService()

    sample_results = {
        "metrics": {
            "net_profit": 123.45,
            "avg_win": 0.5,
            "avg_win_value": 55.0,
            "profit_factor": 2.3,
        },
        "trades": [
            {"pnl": 10.0, "pnl_pct": 0.01, "fees": 0.1, "bars_in_trade": 5},
            {"pnl": -5.0, "pnl_pct": -0.005, "fees": 0.05, "bars_in_trade": 3},
        ],
        "equity_curve": [10000, 10010, 10005],
    }

    ds.update_backtest_results(
        backtest_id=77,
        final_capital=10005.0,
        total_return=0.0005,
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        win_rate=0.5,
        sharpe_ratio=1.1,
        max_drawdown=0.02,
        results=sample_results,
    )

    assert ds.captured is not None
    payload = ds.captured["payload"]

    # trades and equity_curve must be present in the payload
    assert "trades" in payload
    assert isinstance(payload["trades"], list)
    assert len(payload["trades"]) == 2

    assert "equity_curve" in payload
    assert isinstance(payload["equity_curve"], list)

    # some metric keys should be copied
    assert payload.get("net_profit") == 123.45
    assert payload.get("avg_win") == 0.5
    assert payload.get("avg_win_value") == 55.0
