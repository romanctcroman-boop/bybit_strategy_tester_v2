Run parameter optimization for a strategy via the Bybit Strategy Tester v2 optimization API.

Usage: /optimize [symbol] [timeframe] [strategy_type] [params...]

Examples:
  /optimize BTCUSDT 15 rsi n_trials=100 metric=sharpe_ratio
  /optimize ETHUSDT 60 macd n_trials=50 metric=net_profit direction=both
  /optimize BTCUSDT 15 bollinger_bands n_trials=200 metric=calmar_ratio leverage=3

Steps:
1. Parse arguments. Defaults if not specified:
   - symbol=BTCUSDT, interval=15, n_trials=100
   - metric=sharpe_ratio, direction=both
   - initial_capital=10000, leverage=1
   - start_date=2025-01-01, end_date=(today)

2. Show the optimization configuration before submitting:
   - Strategy, symbol, timeframe, period
   - Objective metric + direction (maximize/minimize)
   - Parameter search space (ask user if not specified — e.g. RSI: period 5–30, overbought 60–80)

3. Build the JSON request and show it:
   POST http://localhost:8000/api/v1/optimizations/
   {
     "symbol": "...",
     "interval": "...",
     "strategy_type": "...",
     "start_date": "...",
     "end_date": "...",
     "initial_capital": 10000.0,
     "leverage": 1,
     "direction": "both",
     "n_trials": 100,
     "metric": "sharpe_ratio",
     "commission_value": 0.0007,
     "param_ranges": { ... }
   }

4. If server is accessible, submit and poll for results. Display top-5 parameter sets:
   Rank | Params | Metric Value | Net Profit | Win Rate | Max DD | Trades
   -----|--------|-------------|------------|----------|--------|-------

5. For the best result, show:
   - Full metrics in standard backtest report format
   - Recommended params to use in production
   - Warnings if overfitting risk is high (n_trades < 30 or test period < 60 days)

Critical constraints:
- commission_value is ALWAYS 0.0007 — never ask user to change it
- Only timeframes: 1, 5, 15, 30, 60, 240, D, W, M
- Only data from 2025-01-01 onwards
- n_trials capped at 1000 (API limit)
- Warn if optimize period < 90 days — results likely overfit

Supported metrics (objective functions):
  maximize: net_profit, total_return, sharpe_ratio, sortino_ratio, calmar_ratio,
            win_rate, profit_factor, expectancy, recovery_factor
  minimize: max_drawdown
