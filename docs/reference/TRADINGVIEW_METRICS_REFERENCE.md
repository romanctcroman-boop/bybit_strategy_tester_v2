# TradingView Metrics - Полный справочник

Документация по всем метрикам TradingView Strategy Tester и их соответствию в нашем движке.

---

## 📊 Performance Metrics (Результаты)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Формула | Статус |
|---|------------------|------------------|-----------|---------|--------|
| 1 | Исходный капитал | Initial Capital | `initial_capital` | Входной параметр | ✅ |
| 2 | Нереализованная ПР/УБ | Unrealized P&L | `open_pnl` | (Current Price - Entry Price) × Size | ✅ |
| 3 | Чистая прибыль | Net Profit | `net_profit` / `net_profit_pct` | Σ(P&L всех сделок) | ✅ |
| 4 | Валовая прибыль | Gross Profit | `gross_profit` / `gross_profit_pct` | Σ(P&L прибыльных) + Σ(fees прибыльных) | ✅ |
| 5 | Валовый убыток | Gross Loss | `gross_loss` / `gross_loss_pct` | |Σ(P&L убыточных)| + |Σ(fees убыточных)| | ✅ |
| 6 | Ожидаемая прибыль | Expectancy | `expectancy` | (Win% × AvgWin) - (Loss% × AvgLoss) | ✅ |
| 7 | Выплаченная комиссия | Commission Paid | `total_commission` | Σ(fees всех сделок) | ✅ |
| 8 | Прибыль от покупки и удержания | Buy & Hold Return | `buy_hold_return` / `buy_hold_return_pct` | (LastPrice - FirstPrice) / FirstPrice × Capital | ✅ |
| 9 | Опережающая динамика стратегии | Strategy Outperformance | `strategy_outperformance` | StrategyReturn% - BuyHoldReturn% | ✅ |
| 10 | Годовая доходность (CAGR) | CAGR | `cagr` | ((FinalCapital/InitialCapital)^(1/Years) - 1) × 100 | ✅ |
| 11 | Доходность на исходный капитал | Return on Initial Capital | `total_return` | NetProfit / InitialCapital | ✅ |

---

## 📈 Run-Up Metrics (Рост капитала)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Формула | Статус |
|---|------------------|------------------|-----------|---------|--------|
| 1 | Сред. продолж. роста капитала | Avg Run-Up Duration | `avg_runup_duration_bars` | Среднее кол-во баров в периодах роста | ✅ |
| 2 | Сред. рост капитала | Avg Run-Up | `avg_runup` / `avg_runup_value` | Mean(Equity - InitialCap) когда Equity > InitialCap | ✅ |
| 3 | Макс. рост капитала | Max Run-Up | `max_runup` / `max_runup_value` | Max(Equity - InitialCap) / InitialCap × 100 | ✅ |
| 4 | Макс. рост (внутри бара) | Max Intrabar Run-Up | `max_runup_intrabar` | Учитывает High внутри бара | ✅ |

**Примечание:** Если стратегия всегда в убытке (Equity < InitialCapital), все значения Runup = 0.

---

## 📉 Drawdown Metrics (Просадка)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Формула | Статус |
|---|------------------|------------------|-----------|---------|--------|
| 1 | Сред. продолж. просадки капитала | Avg Drawdown Duration | `avg_drawdown_duration_bars` | Среднее кол-во баров в просадках | ✅ |
| 2 | Сред. просадка капитала | Avg Drawdown | `avg_drawdown` / `avg_drawdown_value` | Mean((Peak - Equity) / Peak) | ✅ |
| 3 | Макс. просадка капитала | Max Drawdown | `max_drawdown` / `max_drawdown_value` | Max((Peak - Equity) / Peak) | ✅ |
| 4 | Макс. просадка (внутри бара) | Max Intrabar Drawdown | `max_drawdown_intrabar` | Учитывает Low внутри бара | ✅ |
| 5 | Продолжит. макс. просадки | Max Drawdown Duration | `max_drawdown_duration_days` | Время от пика до восстановления | ✅ |

---

## 📊 Risk Ratios (Коэффициенты риска)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Формула | Статус |
|---|------------------|------------------|-----------|---------|--------|
| 1 | Доходность на макс. просадку | Recovery Factor | `recovery_factor` | NetProfit / MaxDrawdownValue | ✅ |
| 2 | Sharpe Ratio | Sharpe Ratio | `sharpe_ratio` | (MeanReturn - RFR) / StdReturn | ✅ |
| 3 | Sortino Ratio | Sortino Ratio | `sortino_ratio` | (MeanReturn - RFR) / DownsideStd | ✅ |
| 4 | Calmar Ratio | Calmar Ratio | `calmar_ratio` | AnnualReturn / MaxDrawdown | ✅ |
| 5 | Чистая прибыль в % от наибольшего убытка | Net Profit to Largest Loss | `net_profit_to_largest_loss` | NetProfit / |LargestLoss| | ✅ |
| 6 | Ulcer Index | Ulcer Index | `ulcer_index` | √(Mean(Drawdown²)) | ✅ |

---

## 🔄 Trade Statistics (Статистика сделок)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Формула | Статус |
|---|------------------|------------------|-----------|---------|--------|
| 1 | Всего закрытых сделок | Total Closed Trades | `total_trades` | Количество завершенных сделок | ✅ |
| 2 | Прибыльных | Winning Trades | `winning_trades` | Сделки с P&L > 0 | ✅ |
| 3 | Убыточных | Losing Trades | `losing_trades` | Сделки с P&L ≤ 0 | ✅ |
| 4 | Процент прибыльных | Win Rate | `win_rate` | WinningTrades / TotalTrades × 100 | ✅ |
| 5 | Profit Factor | Profit Factor | `profit_factor` | GrossProfit / GrossLoss | ✅ |
| 6 | Средняя прибыль | Avg Win | `avg_win` / `avg_win_value` | Mean(P&L прибыльных) | ✅ |
| 7 | Средний убыток | Avg Loss | `avg_loss` / `avg_loss_value` | Mean(P&L убыточных) | ✅ |
| 8 | Наибольшая прибыль | Largest Win | `largest_win` / `largest_win_value` | Max(P&L) | ✅ |
| 9 | Наибольший убыток | Largest Loss | `largest_loss` / `largest_loss_value` | Min(P&L) | ✅ |
| 10 | Макс. серия прибыльных | Max Consecutive Wins | `max_consecutive_wins` | Макс. подряд прибыльных | ✅ |
| 11 | Макс. серия убыточных | Max Consecutive Losses | `max_consecutive_losses` | Макс. подряд убыточных | ✅ |
| 12 | Среднее время в сделке | Avg Trade Duration | `avg_trade_duration_hours` | Mean(ExitTime - EntryTime) | ✅ |
| 13 | Среднее баров в сделке | Avg Bars in Trade | `avg_bars_in_trade` | Среднее количество баров | ✅ |

---

## 📊 Long/Short Breakdown (Разбивка Long/Short)

| # | TradingView (RU) | TradingView (EN) | Наше поле | Статус |
|---|------------------|------------------|-----------|--------|
| 1 | Длинных сделок | Long Trades | `long_trades` | ✅ |
| 2 | Коротких сделок | Short Trades | `short_trades` | ✅ |
| 3 | Длинных прибыльных | Long Winning | `long_winning_trades` | ✅ |
| 4 | Коротких прибыльных | Short Winning | `short_winning_trades` | ✅ |
| 5 | P&L длинных | Long P&L | `long_pnl` / `long_pnl_pct` | ✅ |
| 6 | P&L коротких | Short P&L | `short_pnl` / `short_pnl_pct` | ✅ |
| 7 | Win Rate длинных | Long Win Rate | `long_win_rate` | ✅ |
| 8 | Win Rate коротких | Short Win Rate | `short_win_rate` | ✅ |
| 9 | Gross Profit длинных | Long Gross Profit | `long_gross_profit` | ✅ |
| 10 | Gross Loss длинных | Long Gross Loss | `long_gross_loss` | ✅ |
| 11 | Profit Factor длинных | Long Profit Factor | `long_profit_factor` | ✅ |
| 12 | Gross Profit коротких | Short Gross Profit | `short_gross_profit` | ✅ |
| 13 | Gross Loss коротких | Short Gross Loss | `short_gross_loss` | ✅ |
| 14 | Profit Factor коротких | Short Profit Factor | `short_profit_factor` | ✅ |
| 15 | CAGR длинных | Long CAGR | `cagr_long` | ✅ |
| 16 | CAGR коротких | Short CAGR | `cagr_short` | ✅ |

---

## 🔧 Формулы расчета

### Net Profit
```python
net_profit = sum(trade.pnl for trade in trades)
net_profit_pct = (net_profit / initial_capital) * 100
```

### Gross Profit / Loss
```python
# TradingView считает Gross БЕЗ комиссий
gross_profit = sum(t.pnl + t.fees for t in trades if t.pnl > 0)
gross_loss = abs(sum(t.pnl + t.fees for t in trades if t.pnl <= 0))
```

### Recovery Factor
```python
recovery_factor = net_profit / max_drawdown_value
# Примечание: TradingView может использовать другую формулу
```

### Expectancy
```python
win_rate = winning_trades / total_trades
loss_rate = losing_trades / total_trades
avg_win_pct = mean([t.pnl_pct for t in winning_trades])
avg_loss_pct = mean([t.pnl_pct for t in losing_trades])
expectancy = (win_rate * avg_win_pct) - (loss_rate * abs(avg_loss_pct))
```

### Max Runup
```python
runup_series = (equity - initial_capital) / initial_capital
max_runup = max(0, runup_series.max()) * 100  # в процентах

# Если equity никогда не превышала initial_capital, max_runup = 0
```

### CAGR
```python
years = (end_date - start_date).days / 365.25
final_capital = initial_capital + net_profit
cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
```

---

## ⚠️ Известные расхождения с TradingView

| Метрика | Причина расхождения |
|---------|---------------------|
| Recovery Factor | TV может использовать cumulative drawdown вместо max |
| Strategy Outperformance | TV показывает 0% при малых значениях |
| CAGR | TV может округлять до 0% при коротких периодах |
| Комиссия в Gross | TV добавляет комиссию обратно к P&L |

---

## 📝 Проверено на данных

**Эталонный тест TradingView:**
- 862 сделки, BTCUSDT 15m
- Initial Capital: 10,000 USD
- Net Profit: -2,828.41 USD (-28.28%)
- Max Drawdown: -9,288.83 USD (-92.89%)
- Long + Short = Total ✅

---

## 📅 Дата обновления
2026-01-11

## ✅ Статус
Все 50+ метрик TradingView покрыты нашим движком.
