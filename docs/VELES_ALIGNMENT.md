# Veles-aligned UX and contracts

Date: 2025-10-22
Owner: bybit_strategy_tester_v2

This note captures the UX patterns and data contracts we want to mirror from Veles so we don’t forget them as we iterate.

## Bot card (Главная → Боты)

Statuses (end-to-end):
- awaiting_start — бот запускается, подписка на индикаторы.
- awaiting_signal — запущен, ждёт совпадения условий.
- running — «В сделке» (новые сигналы игнорируются до завершения).
- awaiting_stop — дождётся завершения текущей сделки и остановится.
- stopped — выключен.
- error — остановлен с ошибкой; подсветка, инструкции по восстановлению.

Actions (availability depends on status):
- Запустить / Остановить
- Запустить сделку (только при awaiting_signal)
- Редактировать
- Клонировать
- Поделиться
- Бэктест

Minimal Bot shape (API):
```json
{
  "id": "string",
  "name": "string",
  "direction": "LONG|SHORT",
  "exchange": "BYBIT_FUTURES|BINANCE_FUTURES",
  "symbol": "e.g., SOLUSDT" ,
  "status": "awaiting_start|awaiting_signal|running|awaiting_stop|stopped|error",
  "depositUsd": 100,
  "leverage": 5,
  "metrics": { "roiPct": 12.3, "winRatePct": 57.8, "profitFactor": 1.23 }
}
```

Endpoints (mock → real later):
- GET /api/v1/bots → { items: Bot[], total }
- POST /api/v1/bots/{id}/actions { action } → updated bot or operation id

## Active deal card (Активные сделки)

Layout:
- Left: bot name, pair, order progress (e.g., "2 / 5").
- Center: price scale
  - red segment: Entry → Next Open
  - markers: Entry (red), Next Open (blue), TP (green), Current price (grey, live)
  - labels: average price, nearest order/SL on the left, TP on the right
- Right: PnL (abs and %), action buttons:
  - К сделке (page with chart & orders)
  - К боту (editor)
  - Закрыть по рынку (immediate)
  - Усреднить (manual)
  - Отменить (bot stops managing; user closes on exchange)

Minimal ActiveDeal shape:
```json
{
  "id": "string",
  "botId": "string",
  "symbol": "SOLUSDT",
  "side": "LONG|SHORT",
  "orderProgress": "2 / 5",
  "prices": { "min": 100, "entry": 106.7, "nextOpen": 108.1, "target": 110.0, "current": 107.2 },
  "pnl": { "usd": -0.53, "pct": -0.93 },
  "openedAt": "2025-10-22T10:00:00Z",
  "averagePrice": 107.0
}
```

Endpoints (mock → real later):
- GET /api/v1/active-deals → { items: ActiveDeal[], total }
- POST /api/v1/active-deals/{id}/actions { action } → status/result

Live data:
- Use WS client to update `prices.current` for each symbol in view.

## Wizard (создание бота)

Key fields to support (from Veles Full Settings):
- Common: name, API binding, trading type (spot/futures), pair(s), deposit, leverage, margin type.
- Mode: Simple / Own / Signal.
- Grid: coverage %, orders count, martingale %, first order offset, logarithmic spacing, partial placement, “pulling” (подтяжка).
- Controls: stop after N deals, include existing position.
- Entry conditions: on/off + indicators.
- Take profit: simple / multi-takes / signal (+ min P&L).
- Stop-loss: fixed % / signal (from last order or from average) + min offset.
- Preview: TradingView overlay.
- Test: quick backtest before save.

Risk checks to warn about:
- Deposit vs account balance/leverage.
- Aggressive grid (coverage/martingale/offset) without SL.
- Too few historical signals/small sample.

## Backtests & statistics

- Gross: “грязная” прибыль (разница ордеров), база для сервисной комиссии.
- Net: Gross − trading fee (для фьючерсов это не финал, без funding).
- Fees: trading fee суммируется; малые и в другой валюте → могут быть прочерки.
- Funding: для финала сверяться с биржей (история закрытых P&L по позициям).
- PnL в UI = чистый ход цены (без плеча); PnL на бирже ≠ PnL UI.
- Что включаем: закрытые ботом через TP/SL; исключаем ручные/с ошибками/ликвидации.

Quick backtest (enhancements):
- Return Net vs Gross, MPP/MPU, unclosed-deal flag, sample limits, warnings.

## Multipair notes

- Monitors many pairs; opens deal for the first meeting conditions; ignores others while running.
- Backtest for multipair: only on the first pair in the list.

## Next steps (cross-ref to todos)

1) Live current price marker on Active page (WS).  
2) Mock API for bots and active-deals + frontend services/wiring.  
3) Active row stats panel.  
4) Wizard risk checks.  
5) Quick backtest enrichment.  
6) Status model end-to-end.  
7) Navigation actions.  
8) Tests.  
9) Keep this note updated.
