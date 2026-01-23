<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Да, `backtester_spec.md` это то что надо, но не упусти все деталь иначе возникнут проблемы

Ниже цельный черновик `backtester_spec.md`, собранный из всего, что обсуждали. Он уже структурирован как технический документ и учитывает все нюансы TradingView‑подобной логики.[^1][^2][^3][^4][^5]

***

# Backtester Specification (`backtester_spec.md`)

## 1. Цель и обзор

Цель: реализовать модуль бэктестера стратегий с логикой и метриками, максимально близкими к Strategy Tester / Отчёту по стратегии TradingView, но в виде независимого Python‑бэкенда.[^2][^1]

Основной конвейер:

```text
DataLoader → StrategyRunner → Broker (Order Simulator)
          → BacktestResult (Trades + Equity)
          → Metrics Engine
          → UI / Reports
```

Требования:

- Бар‑по‑барная симуляция без заглядывания в будущее в «честном» режиме.[^6][^7]
- Модель исполнения ордеров по OHLC бара максимально приближена к TradingView.[^3][^8]
- Поддержка пирамидинга (несколько входов в одном направлении) на уровне Broker.[^3]
- Полный набор стандартных метрик: Performance, Trades analysis, Risk/performance ratios, Buy\&Hold, Max run‑up/drawdown, структура прибыли и распределение P\&L.[^4][^5][^2]
- Расширяемая архитектура: StrategyRunner и UI можно заменять/расширять без изменений в Broker и Metrics.

***

## 2. Компоненты и интерфейсы

### 2.1. DataLoader

**Назначение:** загрузка и подготовка исторических данных.

Вход:

- `symbol: str`
- `timeframe: str` (например `"15m"`, `"1h"`, `"1D"`)
- `start_time: datetime`, `end_time: datetime`
- источник: биржа / файл / кэш.

Выход:

```text
Bar {
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
}

bars_LTF: List[Bar]         # основной ТФ стратегии
bars_HTF: Optional[List[Bar]]  # старший ТФ для multi-TF, опционально
```

Требования:

- монотонный порядок по `time`;
- без пропусков внутри выбранного периода (либо явно документировать пропуски);
- возможность догрузки (forward‑тест, расширение периода).

***

### 2.2. StrategyRunner

**Назначение:** реализация логики стратегии (аналог Pine Script `strategy()`).[^6][^3]

#### 2.2.1. Режим исполнения

Параметр:

```text
execution_mode: "bar_close" | "intrabar"
```

- `bar_close` (MVP, default) — стратегия вызывается один раз на закрытии каждого бара (исторический стандарт TradingView‑бэктеста).[^7]
- `intrabar` (v2+) — стратегия может вызываться на нескольких под‑шагах внутри бара (open → экстремумы → close), имитируя `calc_on_every_tick` / `on_order_fills`.[^9][^7]


#### 2.2.2. Multi‑TF и контекст HTF

При использовании старшего ТФ (аналог `security()` / `request.security()` в Pine):

- DataLoader готовит `bars_HTF`.
- На баре LTF индекс `t` Runner получает `ContextHTF` только для **закрытых** HTF‑баров.[^10][^9]

Режимы:

```text
lookahead_mode: "none" | "allow"
```

- `"none"` (default) — честный режим, HTF‑данные сдвинуты так, чтобы исключить look‑ahead (каждый LTF‑бар видит только уже закрытый прошлый HTF‑бар).[^9]
- `"allow"` — разрешён look‑ahead (для исследований), но бэктест будет помечен предупреждением.


#### 2.2.3. Интерфейс StrategyRunner

Вход Runner’а на шаге:

```text
run_strategy(
    bar: Bar,
    context_htf: Optional[ContextHTF],
    state: StrategyState
) -> List[OrderSignal]
```

Где:

```text
OrderSignal {
    type: "entry" | "exit" | "close" | "update_sl_tp"
    side: "long" | "short" | "flat"
    size: float                         # контрактов / лотов
    price_level: Optional[float]        # для limit/stop заявок
    sl: Optional[float]                 # уровень стоп-лосса
    tp: Optional[float]                 # уровень тейк-профита
    entry_id: Optional[str]             # идентификатор входа (для пирамидинга)
    from_entry_id: Optional[str]        # на какой вход нацелен exit
    tag: Optional[str]                  # произвольная метка
}
```

StrategyRunner **не** считает P\&L, комиссию и эквити — только генерирует решения.

***

### 2.3. Broker (Order Simulator)

**Назначение:** моделирование исполнения ордеров и состояния счёта, максимально похоже на TradingView.[^8][^3]

#### 2.3.1. Состояние Broker’а

```text
PositionEntry {
    id: str
    side: "long" | "short"
    size: float
    entry_price: float
    entry_time: datetime
}

BrokerState {
    entries_long:  List[PositionEntry]
    entries_short: List[PositionEntry]

    cash: float
    equity: float
    used_margin: float
    unrealized_pnl: float

    open_orders: List[PendingOrder]       # опционально, для сложных моделей
    pyramiding_limit: int                 # максимум активных входов per side
    close_rule: "FIFO" | "LIFO" | "ALL"   # правило закрытия слоёв
}
```


#### 2.3.2. Конфиг комиссий

```text
BrokerFeesConfig {
    maker_fee_rate: float        # например 0.0002 (0.02%)
    taker_fee_rate: float        # например 0.0006 (0.06%)
    fee_on_entry: bool           # брать ли комиссию при входе
    fee_on_exit: bool            # при выходе
    fee_currency: "quote" | "base" | "equity"
}
```

Расчёт комиссии:

- `notional = price * size * contract_value`.
- `fee_rate = taker_fee_rate` (MVP: все ордера как taker; v2: maker/taker по типу исполнения).[^11]
- `commission_side = notional * fee_rate` (если `fee_on_entry/exit == True`).
- `Trade.commission = сумма commission_side по всем fill‑ам сделки`.


#### 2.3.3. Приоритет SL/TP и модель исполнения внутри бара

Для каждого бара вызывается:

```text
simulate_bar(
    bar: Bar,
    signals: List[OrderSignal],
    state: BrokerState,
    fees: BrokerFeesConfig,
    sl_tp_cfg: SlTpPriorityConfig,
    exec_cfg: ExecutionConfig
) -> (BrokerState, List[Trade], EquityPoint)
```

`SlTpPriorityConfig`:

```text
SlTpPriorityConfig {
    sl_first: bool              # при одновременном достижении SL и TP
    trigger_on_entry_bar: bool  # разрешать ли срабатывание SL/TP на баре входа
}
```

`ExecutionConfig`:

```text
ExecutionConfig {
    market_fill_mode: "close" | "next_open"
    order_types_enabled: bool     # если false, все сигналы как market по close
}
```

**Последовательность исполнения на баре (MVP, default):**

1. Обработать входящие `signals` и при необходимости:
    - сформировать рыночные ордера;
    - обновить уровни SL/TP для текущих позиций.
2. Если позиция только что открыта на этом баре:
    - при `trigger_on_entry_bar = False` — не позволять SL/TP сработать на этой же свече;
    - иначе — разрешить их проверку как обычно.
3. Исполнение лимитов (если включены):
    - buy‑limit: `low <= price_level <= max(open, close)` → fill по `price_level`;
    - sell‑limit: `high >= price_level >= min(open, close)` → fill по `price_level`.[^8]
4. Исполнение стоп‑ордеров:
    - buy‑stop: если `high >= stop_price`;
    - sell‑stop: если `low <= stop_price`.
5. Исполнение SL/TP активной позиции:

Для long:
    - если `low <= sl` и `high >= tp` на одном баре:
        - если `sl_first == True` → закрыть по SL;
        - иначе → по TP;
    - если только `low <= sl` → SL;
    - если только `high >= tp` → TP.

Для short — зеркально.
6. Рыночные ордера:
    - при `market_fill_mode = "close"` — fill по `close` текущего бара;
    - при `market_fill_mode = "next_open"` — по `open` следующего бара.

Каждый fill создаёт `Trade` и изменяет `BrokerState`.

#### 2.3.4. Пирамидинг

- При обработке `OrderSignal(type="entry")`:
    - считаем количество активных entries по направлению;
    - если `< pyramiding_limit` → создаём новый `PositionEntry` (`id = entry_id или авто`);
    - если `>= limit`:
        - базово — игнорируем сигнал;
        - v2 — конфигурируемое поведение (закрыть старые, открыть новые, частично закрыть и т.п.).[^3]
- При `type="exit"`:
    - если указан `from_entry_id` — закрываем конкретный слой;
    - иначе — закрываем по `close_rule`:
        - FIFO — закрываем самые старые;
        - LIFO — самые новые;
        - ALL — все слои целиком.


#### 2.3.5. Расчёт P\&L и эквити

При закрытии части позиции:

```text
direction = +1 для long, -1 для short
trade_pnl = (exit_price - entry_price) * size * direction
realized_pnl += trade_pnl - commission
```

Эквити:

```text
unrealized_pnl = (last_price - avg_entry_price) * net_position_size * direction
equity = initial_capital + realized_pnl + unrealized_pnl
```

`EquityPoint`:

```text
EquityPoint {
    time: datetime
    equity: float
    cash: float
    position_size: float
    unrealized_pnl: float
}
```


***

## 3. Формат BacktestResult

Broker по завершении прогонки по всем барам возвращает:

```text
Trade {
    id: int
    entry_id: Optional[str]
    side: "long" | "short"
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    realized_pnl: float
    commission: float
    bars_in_trade: int
    max_runup: float        # локальный максимум P&L или эквити внутри сделки
    max_drawdown: float     # локальный минимум внутри сделки
}

BacktestResult {
    trades_all:   List[Trade]
    trades_long:  List[Trade]   # фильтрация по side
    trades_short: List[Trade]

    equity_series:    List[EquityPoint]
    bh_equity_series: List[EquityPoint]   # линия Buy & Hold

    initial_capital: float

    flags: {
        has_lookahead_bias: bool
        is_repainting: bool
        warnings: List[str]
    }
}
```

Линия Buy\&Hold:

```text
bh_equity_t = initial_capital * close_t / close_start
```


***

## 4. Metrics Engine

**Назначение:** расчёт всех TV‑подобных метрик по `BacktestResult`.[^1][^2]

### 4.1. Performance (All / Long / Short)

Для каждого множества сделок (`trades_all`, `trades_long`, `trades_short`):

Обозначения:

- $P_i$ — `realized_pnl` сделки;
- $C_i$ — `commission` сделки;
- `OpenPnl` — текущий нереализованный P\&L;
- `Equity_t` — значение из `equity_series`;
- `E_0 = initial_capital`.

Метрики:

- `Open P&L = OpenPnl`.
- `Net profit = Σ P_i + OpenPnl - Σ C_i`.[^2]
- `Gross profit = Σ P_i, где P_i > 0`.
- `Gross loss = Σ P_i, где P_i < 0` (в UI — модуль).
- `Commission paid = Σ C_i`.
- `Buy & hold`:
    - абсолютный: `bh_equity_end - E_0`;
    - процент: `bh_equity_end / E_0 - 1`.[^12]
- `Max equity run-up`:
    - $RU_t = Equity_t - \min_{\tau \le t} Equity_\tau$;
    - `max_runup = max(RU_t)`.[^12]
- `Max equity drawdown`:
    - $DD_t = (Equity_t - \max_{\tau \le t} Equity_\tau) / \max_{\tau \le t} Equity_\tau$;
    - `max_drawdown = min(DD_t)` (в UI — модуль).[^13]
- `Max contracts held = max |position_size|` по `equity_series`. [^2]


### 4.2. Trades analysis

По каждому множеству сделок:

Обозначения:

- `T` — множество сделок;
- `T+` — сделки с `P_i > 0`;
- `T-` — `P_i < 0`;
- `b_i = bars_in_trade`.[^2]

Метрики:

- `total_trades = |T|`;
- `total_open_trades` (на конец периода, из текущего state);
- `winning_trades = |T+|`;
- `losing_trades = |T-|`;
- `percent_profitable = winning_trades / total_trades` (если `total_trades > 0`).
- `avg_pnl = Σ P_i / total_trades`;
- `avg_win = Σ P_i (i∈T+) / |T+|`;
- `avg_loss = Σ P_i (i∈T-) / |T-|`;
- `avg_win_loss_ratio = avg_win / |avg_loss|` (если `avg_loss != 0`).
- `largest_win = max P_i`;
- `largest_loss = min P_i`;
- `avg_bars_all = Σ b_i / |T|`;
- `avg_bars_win = Σ b_i (i∈T+) / |T+|`;
- `avg_bars_loss = Σ b_i (i∈T-) / |T-|`. [^2]


### 4.3. Risk / performance ratios

На основе `equity_series`:

1. Строим ряд **месячных доходностей** `R_m` (или дневных, но для TV‑совместимости — месячные):[^5][^4]
    - `R_m = Equity_end_of_month / Equity_start_of_month - 1`.
2. `MR = mean(R_m)`.
3. `RFR_month = risk_free_rate_annual / 12`.

Sharpe:

```text
Sharpe = (MR - RFR_month) / std(R_m)
```

Sortino:

- `DownsideDeviation = sqrt( Σ min(0, R_m - target)^2 / N )`, где `target = 0` или `RFR_month`.[^5]

```text
Sortino = (MR - RFR_month) / DownsideDeviation
```

Profit factor:

```text
ProfitFactor = GrossProfit / |GrossLoss|   # см. 4.1
```


### 4.4. Структура прибыли (PnL Structure)

На основе агрегатов:

- `total_profit = Σ P_i, P_i > 0`;
- `total_loss = Σ P_i, P_i < 0`;
- `unrealized_pnl` — текущий `OpenPnl`;
- `commissions = Σ C_i`;
- `total_pnl = total_profit + total_loss + unrealized_pnl - commissions`.

Используется для нижнего левого bar‑chart «Структура прибыли» (категории: Итоговая прибыль, Нереализованные П/УБ, Итоговый убыток, Комиссия, Общие П/УБ).[^14][^2]

### 4.5. Распределение прибыли и убытков (PnL Distribution)

Для каждого `Trade`:

- `pnl_pct = realized_pnl / (entry_price * size * leverage_factor)` (точная формула фиксируется в коде конфигурации; для спота `leverage_factor = 1`).

Далее:

- набор бинов по X, например: `(-∞,-1%]`, `(-1%,-0.5%]`, `(-0.5%,0]`, `(0,0.5%]`, `(0.5%,1%]`, `(1%,1.5%]`, `(1.5%,2.5%]`, `(2.5%,3.5%]`, `(3.5%,∞)`;
- считаем:
    - `counts_win[bin]` — количество сделок с `pnl_pct > 0` в бине;
    - `counts_loss[bin]` — `pnl_pct < 0`.
- `avg_win_pct` и `avg_loss_pct` — средние по всем выигрывающим/проигрывающим сделкам; используются как вертикальные пунктирные линии.[^11]

***

## 5. UI / Отчёты

UI работает только с `BacktestResult` и `Metrics`, не зная о барах/ордер‑симуляции.

### 5.1. Страница «График капитала»

Вход:

- `equity_series`, `bh_equity_series`, `PnLStructure`, `PnLDistribution`, summary‑метрики.[^15][^14][^2]

Элементы:

- Верхняя панель карточек:
    - Net profit, Max drawdown, Total trades, Win rate, Profit factor и др.
- Верхний график:
    - бирюзовая линия: `equity_series (equity vs time)`;
    - красная линия: B\&H или линия отклонения (equity_strategy − equity_bh);
    - маркеры сделок по оси времени (long/short).
- Переключатели:
    - «Покупка и удержание» (видимость B\&H);
    - «Отклонения сделок»;
    - «Абсолютные значения / Проценты».
- Нижний левый бар‑чарт: `PnLStructure` по категориям.
- Нижний правый histogram: `PnLDistribution` (красные — убытки, зелёные — профит), пунктирные линии `avg_win_pct` и `avg_loss_pct`.


### 5.2. Страницы «Анализ сделок», «Доходность с учётом риска», «Список сделок»

- «Анализ сделок» — визуализация `TradesStats` All/Long/Short (таблица, графики win rate, средних, длительности сделок).[^2]
- «Доходность с учётом риска» — Sharpe, Sortino, Profit factor и графики run‑up/drawdown (на основе `equity_series`).[^4][^13]
- «Список сделок» — таблица по `trades_all` (Trade \#, Type, Date/Time entry/exit, Price, Size, Net P\&L, Run‑up, Drawdown, Cumulative P\&L).[^2]

***

## 6. Статический анализ стратегии (look‑ahead / repaint)

Перед запуском бэктеста стратегия прогоняется через анализатор:

```text
StrategyCheckResult {
    has_lookahead_bias: bool
    is_repainting: bool
    warnings: List[str]
}
```

Критерии (на уровне твоего DSL / AST):

- использование данных будущих баров (индексы > текущего, прямая работа с будущим `bar_index`);
- использование HTF без задержки (режим `"allow"`);[^10][^9]
- использование индикаторов, заведомо перерисовывающихся (фракталы без задержки, ZigZag, и др. — список формируется).[^16][^17]

Эти флаги попадают в `BacktestResult.flags` и отображаются в UI в виде предупреждений, аналогичных TradingView: «Strategy may use look-ahead bias» / «Strategy may repaint».[^18][^19]

***

Этот `backtester_spec.md` можно считать базовой спецификацией. При реализации для каждого блока можно явно помечать, что входит в «MVP» и что — в «TV‑совместимый v2+», но все необходимые поля и шаги уже перечислены, так что пробелов для будущих расширений не останется.
<span style="display:none">[^20]</span>

<div align="center">⁂</div>

[^1]: https://www.tradingview.com/support/solutions/43000562362-what-are-strategies-backtesting-and-forward-testing/

[^2]: https://ru.tradingview.com/support/solutions/43000764138/

[^3]: https://www.tradingview.com/pine-script-docs/v5/concepts/strategies/

[^4]: https://www.tradingview.com/support/solutions/43000681694-risk-performance-ratios-sharpe-ratio/

[^5]: https://www.tradingview.com/support/solutions/43000681697-risk-performance-ratios-sortino-ratio/

[^6]: https://www.tradingview.com/pine-script-docs/faq/strategies/

[^7]: https://www.tradingview.com/pine-script-docs/language/execution-model/

[^8]: https://optimusfutures.com/blog/how-to-backtest-on-tradingview/

[^9]: https://www.linkedin.com/pulse/how-avoid-look-ahead-bias-pinescript-sunil-guglani-voyac

[^10]: https://www.tradingview.com/script/P8NIR0uQ-Higher-TF-Repainting-Limiting-backtest-results/

[^11]: https://chartwisehub.com/tradingview-strategy-tester/

[^12]: https://www.tradingview.com/pine-script-docs/concepts/strategies/

[^13]: https://www.tradingview.com/support/solutions/43000681690-performance-max-equity-drawdown/

[^14]: https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/52611830/d0f31ed0-525a-4e4b-874c-7af13b29d837/F6670BE9-0E93-42F9-BF31-F689881580F2.jpg

[^15]: https://www.tradingview.com/support/solutions/43000681735-overview-equity/

[^16]: https://www.milvetti.com/post/understanding-the-repaint-issue-in-tradingview-indicators

[^17]: https://ru.tradingview.com/scripts/repainting/

[^18]: https://www.tradingview.com/support/solutions/43000614705-strategy-produces-unrealistically-good-results-by-peeking-into-the-future/

[^19]: https://www.tradingview.com/support/solutions/43000478429-script-or-strategy-gives-different-results-after-refreshing-the-page-repainting/

[^20]: https://ru.tradingview.com/scripts/performance/

