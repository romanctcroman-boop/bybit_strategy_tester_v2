Run a backtest for the specified strategy and parameters.

Usage: /backtest [symbol] [timeframe] [strategy_type] [params...]

Example: /backtest BTCUSDT 15 rsi period=14 overbought=70 oversold=30

Steps:
1. Parse the arguments from the user's message (symbol, interval, strategy_type, strategy_params)
2. Use defaults if not specified: symbol=BTCUSDT, interval=15, initial_capital=10000, leverage=1, direction=both
3. Show the backtest configuration before running
4. Build the JSON request and show it to the user
5. Remind the user to POST to: http://localhost:8000/api/v1/backtests/
6. If the server is running and accessible, fetch the result and display it in the standard report format:
   - Net Profit ($, %), Total Trades (W/L), Win Rate, Profit Factor, Sharpe, Max Drawdown
   - Any warnings from the `warnings` field
   - TradingView parity status

Critical constraints:
- commission_rate is always 0.0007 (never ask the user to change this)
- Only timeframes: 1, 5, 15, 30, 60, 240, D, W, M
- Only data from 2025-01-01 onwards
