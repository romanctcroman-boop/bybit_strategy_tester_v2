# TradingView Metrics Mapping

Соответствие метрик нашего бэктестера и TradingView Strategy Tester.

## Метрики Performance (Результаты)

| TradingView (RU) | TradingView (EN) | Наш движок | Поле |
|------------------|------------------|------------|------|
| Исходный капитал | Initial Capital | ✅ | `initial_capital` |
| Нереализованная ПР/УБ | Unrealized P&L | ✅ | `open_pnl` / `open_pnl_pct` |
| Чистая прибыль | Net Profit | ✅ | `net_profit` / `net_profit_pct` |
| Валовая прибыль | Gross Profit | ✅ | `gross_profit` / `gross_profit_pct` |
| Валовый убыток | Gross Loss | ✅ | `gross_loss` / `gross_loss_pct` |
| Ожидаемая прибыль | Expectancy | ✅ | `expectancy` |
| Выплаченная комиссия | Commission Paid | ✅ | `total_commission` |
| Прибыль от покупки и удержания | Buy & Hold Return | ✅ | `buy_hold_return` / `buy_hold_return_pct` |
| Опережающая динамика стратегии | Strategy Outperformance | ✅ | `strategy_outperformance` |
| Годовая доходность (CAGR) | CAGR | ✅ | `cagr` |
| Доходность на исходный капитал | Return on Initial Capital | ✅ | `total_return` |

## Метрики Runup (Рост капитала)

| TradingView (RU) | TradingView (EN) | Наш движок | Поле |
|------------------|------------------|------------|------|
| Сред. продолж. роста капитала | Avg Run-Up Duration | ✅ | `avg_runup_duration_bars` |
| Сред. рост капитала | Avg Run-Up | ✅ | `avg_runup` / `avg_runup_value` |
| Макс. рост капитала | Max Run-Up | ✅ | `max_runup` / `max_runup_value` |
| Макс. рост капитала (внутри бара) | Max Intrabar Run-Up | ✅ | `max_runup_intrabar` / `max_runup_intrabar_value` |

## Метрики Drawdown (Просадка)

| TradingView (RU) | TradingView (EN) | Наш движок | Поле |
|------------------|------------------|------------|------|
| Сред. продолж. просадки капитала | Avg Drawdown Duration | ✅ | `avg_drawdown_duration_bars` |
| Сред. просадка капитала | Avg Drawdown | ✅ | `avg_drawdown` / `avg_drawdown_value` |
| Макс. просадка капитала | Max Drawdown | ✅ | `max_drawdown` / `max_drawdown_value` |
| Макс. просадка (внутри бара) | Max Intrabar Drawdown | ✅ | `max_drawdown_intrabar` / `max_drawdown_intrabar_value` |
| Доходность на макс. просадку | Return on Max Drawdown | ✅ | `recovery_factor` |

## Метрики Risk Ratios (Коэффициенты риска)

| TradingView (RU) | TradingView (EN) | Наш движок | Поле |
|------------------|------------------|------------|------|
| Sharpe Ratio | Sharpe Ratio | ✅ | `sharpe_ratio` |
| Sortino Ratio | Sortino Ratio | ✅ | `sortino_ratio` |
| Calmar Ratio | Calmar Ratio | ✅ | `calmar_ratio` |
| Ulcer Index | Ulcer Index | ✅ | `ulcer_index` |
| Volatility | Volatility | ✅ | `volatility` |

## Метрики Trades (Сделки)

| TradingView (RU) | TradingView (EN) | Наш движок | Поле |
|------------------|------------------|------------|------|
| Всего закрытых сделок | Total Closed Trades | ✅ | `total_trades` |
| Прибыльных | Winning Trades | ✅ | `winning_trades` |
| Убыточных | Losing Trades | ✅ | `losing_trades` |
| Процент прибыльных | Win Rate | ✅ | `win_rate` |
| Profit Factor | Profit Factor | ✅ | `profit_factor` |
| Средняя прибыль | Avg Win | ✅ | `avg_win` / `avg_win_value` |
| Средний убыток | Avg Loss | ✅ | `avg_loss` / `avg_loss_value` |
| Наибольшая прибыль | Largest Win | ✅ | `largest_win` / `largest_win_value` |
| Наибольший убыток | Largest Loss | ✅ | `largest_loss` / `largest_loss_value` |
| Макс. серия прибыльных | Max Consecutive Wins | ✅ | `max_consecutive_wins` |
| Макс. серия убыточных | Max Consecutive Losses | ✅ | `max_consecutive_losses` |

## Long/Short Separate Statistics

| TradingView (RU) | Наш движок | Поле |
|------------------|------------|------|
| ДЛИННАЯ - Чистая прибыль | ✅ | `long_net_profit` / `long_pnl_pct` |
| ДЛИННАЯ - Валовая прибыль | ✅ | `long_gross_profit` |
| ДЛИННАЯ - Валовый убыток | ✅ | `long_gross_loss` |
| ДЛИННАЯ - Profit Factor | ✅ | `long_profit_factor` |
| ДЛИННАЯ - Win Rate | ✅ | `long_win_rate` |
| КОРОТКАЯ - Чистая прибыль | ✅ | `short_net_profit` / `short_pnl_pct` |
| КОРОТКАЯ - Валовая прибыль | ✅ | `short_gross_profit` |
| КОРОТКАЯ - Валовый убыток | ✅ | `short_gross_loss` |
| КОРОТКАЯ - Profit Factor | ✅ | `short_profit_factor` |
| КОРОТКАЯ - Win Rate | ✅ | `short_win_rate` |
| CAGR LONG | ✅ | `cagr_long` |
| CAGR SHORT | ✅ | `cagr_short` |

## Расчет метрик

### Nerealized P&L (Нереализованная ПР/УБ)
```python
# TradingView formula
Unrealized_PnL = (Current_Price - Avg_Entry_Price) × Position_Size

# Наш движок (engine.py line 695)
if is_long:
    unrealized_pnl = (price - entry_price) * position * leverage
else:
    unrealized_pnl = (entry_price - price) * position * leverage
```

### TP/SL Execution (TradingView-style)
```python
# TradingView: TP/SL проверяются по high/low внутри бара
# Наш движок (engine.py lines 565-600)

# Для LONG:
worst_price_in_bar = current_low   # SL проверяется по low
best_price_in_bar = current_high   # TP проверяется по high

# Для SHORT:
worst_price_in_bar = current_high  # SL проверяется по high
best_price_in_bar = current_low    # TP проверяется по low

# Цена выхода = точная цена TP/SL (не close!)
exit_price = entry_price * (1 - stop_loss / leverage)  # для SL
exit_price = entry_price * (1 + take_profit / leverage)  # для TP
```

### Average Run-Up (Сред. рост капитала)
```python
# Наш движок (engine.py line 723)
runup = (equity_series - initial_cap) / initial_cap
positive_runups = runup[runup > 0]
avg_runup = float(positive_runups.mean()) if len(positive_runups) > 0 else 0.0
```

### Recovery Factor (Доходность на макс. просадку)
```python
recovery_factor = net_profit / max_drawdown_value
```

## Дата обновления
2026-01-11

## Статус
✅ Полное соответствие TradingView Strategy Tester
