"""Run backtest for RSI_LS_11 strategy with slippage=0."""

import asyncio

import httpx


async def run_backtest():
    strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
    url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest"

    payload = {
        "symbol": "ETHUSDT",
        "interval": "30",  # <-- correct field name (not "timeframe")
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2026-02-25T00:00:00Z",
        "initial_capital": 10000.0,
        "leverage": 10,
        "position_size": 0.1,
        "commission": 0.0007,
        "slippage": 0.0,  # <-- ZERO slippage, matching TV
        "pyramiding": 1,
        "direction": "both",
        "stop_loss": 0.132,  # <-- correct field name (not "stop_loss_pct")
        "take_profit": 0.023,  # <-- correct field name (not "take_profit_pct")
        "market_type": "linear",
    }

    print("Running backtest with slippage=0...")
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text[:500]}")
            return

        result = resp.json()
        bt_id = result.get("backtest_id", result.get("id", "?"))
        print(f"Backtest ID: {bt_id}")
        status = result.get("status")
        print(f"Status: {status}")

        # Extract key metrics
        metrics = result.get("metrics", result.get("results", result))
        if "total_trades" in result:
            total = result["total_trades"]
            net_profit = result.get("net_profit", 0)
            win_rate = result.get("win_rate", 0)
        elif metrics:
            total = metrics.get("total_trades", 0)
            net_profit = metrics.get("net_profit", 0)
            win_rate = metrics.get("win_rate", 0)

        print("\nResults:")
        print(f"  Total trades:  {total}")
        print(f"  Net profit:    ${net_profit:.2f}")
        print(f"  Win rate:      {win_rate:.4f}%")
        if metrics:
            gp = metrics.get("gross_profit", 0)
            gl = metrics.get("gross_loss", 0)
            comm = metrics.get("total_commission", metrics.get("commission", 0))
            pf = metrics.get("profit_factor", 0)
            sharpe = metrics.get("sharpe_ratio", 0)
            dd = metrics.get("max_drawdown", 0)
            print(f"  Gross profit:  ${gp:.2f}")
            print(f"  Gross loss:    ${gl:.2f}")
            print(f"  Commission:    ${comm:.2f}")
            print(f"  Profit factor: {pf:.4f}")
            print(f"  Sharpe ratio:  {sharpe:.4f}")
            print(f"  Max drawdown:  {dd:.4f}%")

        print("\nTarget (TV):")
        print("  Total trades:  151")
        print("  Net profit:    $1091.53")
        print("  Win rate:      90.73%")
        print("  Gross profit:  $2960.36")
        print("  Gross loss:    $1868.84")
        print("  Commission:    $211.47")
        print("  Profit factor: 1.584")
        print("  Sharpe ratio:  0.357")
        print("  Max drawdown:  6.00%")


asyncio.run(run_backtest())
