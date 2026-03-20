# Progress — Статус проекта

## Последнее обновление: 2026-03-20

## ✅ Что работает (проверено)

- FallbackEngineV4 — gold standard, TradingView parity ✅
- NumbaEngine — 100% parity с V4, 20-40x быстрее ✅
- DCAEngine — DCA/Grid/Martingale стратегии ✅
- Strategy Builder — блочный конструктор (50+ типов блоков) ✅
- MetricsCalculator — 166 метрик ✅
- Optuna optimizer — TPE/CMA-ES оптимизация ✅
- AI агенты (DeepSeek/Qwen/Perplexity) в direct API режиме ✅
- 179+ тестов проходят (214 файлов) ✅
- Port aliases (long↔bullish, short↔bearish) ✅
- Direction mismatch detection + warnings[] ✅
- commission=0.0007 — проверено в core-файлах ✅
- `backend/config/constants.py` создан (Phase 1.1) ✅
- `backend/backtesting/models.py` обновлён: константы + direction="both" (Phase 1.2) ✅
- Phase 3: `strategy_builder_adapter.py` (3575→1399 строк) разбит на пакет `strategy_builder/` ✅
- Phase 4: `backtests.py` (3171→пакет router.py+formatters.py+schemas.py) ✅
- Phase 5: `SymbolSyncModule.js` извлечён из `strategy_builder.js` (13378→7154 строк) ✅
- Phase 5: `blockLibrary.js` извлечён (каталог блоков, ~158 строк) ✅

## ⚠️ Известные проблемы / Технический долг

- RSI Wilder smoothing: 4-trade divergence vs TradingView (warmup limit 500 баров) — ACCEPTABLE
- commission=0.001 остаётся в: `optimize_tasks.py`, `fast_optimizer.py` (deprecated), `ai_backtest_executor.py` (ML-experimental) — LOW PRIORITY
- position_size: fraction (0-1) в engine vs percent в live trading — ADR-006, задокументировано
- leverage default: 10 в optimizer/UI vs 1.0 в live trading — задокументировано
- 12 temp_analysis/ скриптов (одноразовые, не удалены) — CLEANUP NEEDED
- **Phase 1 незавершена**: `optimization/models.py`, `builder_optimizer.py`, `backtests.py:2771` — ещё 3 файла с хардкодом 0.0007

## 📁 Крупные файлы требующие внимания

| Файл | Строк | Статус |
|------|-------|--------|
| strategy_builder/adapter.py | 1399 | ✅ Phase 3 рефакторинг завершён |
| indicator_handlers.py | 2217 | Не разбит по категориям (trend/oscillators/etc) |
| strategy_builder.js | 7154 | ✅ Phase 5: SymbolSync + blockLibrary извлечены; canvas/block core остаётся |
| backtests/ (пакет) | router+formatters+schemas | ✅ Phase 4 завершён |

## 🚧 В процессе / Запланировано

- Phase 1: ~3 файла ещё с хардкодом 0.0007 (optimization/models.py, builder_optimizer.py, backtests/router.py:2771) — LOW
- indicator_handlers.py разбить по категориям (trend/oscillators/volatility/volume/other) — LOW
- Удалить deprecated файлы (fast_optimizer.py, fallback_engine_v2.py, v3.py) — MEDIUM
- Unified error handler для API роутеров (Phase 4.2) — LOW

## 📊 Метрики кодовой базы

- Backend: ~50+ роутеров, 40+ индикаторов
- Tests: 214 файлов / 10 директорий
- Frontend: Vanilla JS, no build step

## 🚫 Что НЕЛЬЗЯ делать

- Менять commission с 0.0007 без явного согласования
- Использовать FallbackEngineV2/V3 для нового кода
- Хардкодить даты (импортировать DATA_START_DATE)
- Реализовывать метрики вне MetricsCalculator
- Вызывать реальный Bybit API в тестах
