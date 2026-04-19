# Что ещё не выполнено и новые задачи

> **Дата:** 2026-01-31 (обновлено)  
> **Источники:** CURSOR_RULES_ANALYSIS, FULL_IMPLEMENTATION_PLAN, IMPLEMENTATION_STATUS, PROJECT_JOURNAL, ROADMAP_REMAINING_TASKS.

---

## 0. Roadmap — крупные задачи (2026-02)

| Задача | Статус |
|--------|--------|
| Event-driven движок | ✅ EventQueue, EventDrivenEngine, SimulationExecutionHandler, интеграция StrategyBuilderAdapter |
| Multi-asset portfolio | ✅ MIN_VARIANCE, MAX_SHARPE, CVXPORTFOLIO, diversification_ratio |
| §12 Визуализация | ✅ Parameter heatmap, Trade distribution, Regime overlay |
| Версионирование / Undo / Шаблоны | ✅ БД, API, Versions UI, Undo/Redo, Export/Import шаблонов |
| L2 / Generative LOB | ✅ WebSocket collector, CGAN (PyTorch), обучение на NDJSON |

**Зависимости для тестов:** `pip install numba vectorbt torch` (или `pip install .[dev-full]`).  

**Калибровка:** `scripts/calibrate_166_metrics.py` — 51/51 метрик ✅  
- Данные: TV_DATA_DIR (или d:/TV) с экспортом TradingView  
- Windows: `$env:PYTHONIOENCODING='utf-8'; py scripts/calibrate_166_metrics.py`

**Регрессия:** `scripts/compare_vectorbt_vs_fallback.py`, `compare_equity.py` — требуют БД (data.sqlite3). Скрипты добавляют project_root в sys.path автоматически.

---

## 1. Оставшееся по Cursor Rules (низкий приоритет)

| Задача | Описание | Статус |
|--------|----------|--------|
| **Дефолт комиссии 0.07%** | Во всех сценариях бэктеста по умолчанию 0.07% для TradingView parity. | ✅ Выполнено 2026-01-30: models.py (commission_value=0.0007), optimizations.py, backtest_tasks, data_service, portfolio (advanced), optimizer, gpu_optimizer, fast_optimizer, vectorbt_optimizer, gpu_batch_optimizer. |
| **Версия Python в правилах** | Одна рекомендуемая версия в project.mdc и README. | ✅ Выполнено 2026-01-30: project.mdc «3.11+ (рекомендуется 3.14)», AGENTS.MD и README обновлены. |
| **except Exception** | В backend используются `except Exception as e:` с логированием; голых `except Exception: pass` не найдено. При появлении — заменять на логирование. | Низкий приоритет |

---

## 2. Синхронизация документации ✅ (2026-01-30)

| Документ | Статус |
|----------|--------|
| **docs/tradingview_dca_import/IMPLEMENTATION_STATUS.md** | Обновлены Phase 3–4 (ATR, Indent, MTF, Close Conditions [x]), Next Steps (маппинг и комиссия отмечены выполненными). |
| **docs/SESSION_5_4_AUDIT_REPORT.md** | Раздел 3 обновлён: WebSocket UI — Done (Session 5.5); итоговая таблица: интеграция WS — Да. |
| **docs/FULL_IMPLEMENTATION_PLAN.md** | Phase 1.1 и 1.2 отмечены [x], strategy_builder_ws.js — «интегрирован в UI». |

---

## 3. Новые / уточнённые задачи

### 3.1 Интеграция конфига Strategy Builder → DCAEngine ✅ (2026-01-30)

- **Сделано:** В `StrategyBuilderAdapter.extract_dca_config()` добавлен сбор блоков `rsi_close`, `stoch_close`, `channel_close`, `ma_close`, `psar_close`, `time_bars_close` и `indent_order`; возвращаются словари `close_conditions` и `indent_order`. В `strategy_builder.py` при формировании BacktestConfig в `strategy_params` передаются `close_conditions` и `indent_order` из `final_dca_config`. В `DCAEngine._configure_from_config()` добавлено чтение `config.strategy_params["close_conditions"]` и `config.strategy_params["indent_order"]` и применение к `self.close_conditions` и `self.indent_order`.

### 3.2 Signal Memory ✅ (2026-01-30)

- **Назначение:** «Держать сигнал в памяти N баров» — если условие входа выполнилось на баре i, сигнал активен до бара i + N; противоположный сигнал отменяет память.
- **Реализация:** В `StrategyBuilderAdapter._execute_filter()` добавлен хелпер `apply_signal_memory(buy_events, sell_events, memory_bars)`. Применяется в фильтрах: **rsi_filter** (`use_signal_memory` / `signal_memory_bars`), **stochastic_filter** (`activate_stoch_cross_memory` / `stoch_cross_memory_bars` для mode cross; `activate_stoch_kd_memory` / `stoch_kd_memory_bars` для kd_cross), **two_ma_filter** (`ma_cross_memory_bars`), **macd_filter** (`macd_signal_memory_bars`, `disable_macd_signal_memory=False`). Тесты: `tests/test_signal_memory_adapter.py`.

### 3.3 E2E и регрессия ✅ (2026-02)

- **E2E DCA:** Добавлен `tests/test_e2e_dca_close_condition.py`: тесты `test_dca_engine_run_with_time_bars_close`, `test_dca_engine_run_with_indent_order_config`, `test_dca_engine_run_with_rsi_close_config` — проверка применения close_conditions и indent_order из strategy_params и прохождение run_from_config.
- **Регрессия:** `scripts/calibrate_166_metrics.py` — 51/51 метрик (100%). `scripts/compare_vectorbt_vs_fallback.py` — сравнение движков. Зависимости: numba, vectorbt (pip install .[dev-full]).

### 3.4 Хардкод путей (остатки)

- По анализу пути в перечисленных тестах и скриптах исправлены. При появлении новых скриптов в `scripts/` или тестов — сразу использовать `Path(__file__).resolve().parents[N]` и env (DATABASE_PATH и т.д.), без `d:\...`.

---

## 4. Сводка приоритетов

| Приоритет | Задачи |
|-----------|--------|
| **Сделано (2026-01-30)** | Маппинг Strategy Builder → DCAEngine. E2E тесты DCA + close_conditions. Синхронизация SESSION_5_4, REMAINING, IMPLEMENTATION_STATUS, FULL_PLAN. Замена except в bybit.py и sqlite_pool.py. **Дефолт комиссии 0.07%** во всех BacktestConfig/API/optimizers. **Версия Python** в project.mdc, AGENTS.MD, README (3.11+, рекомендуется 3.14). |
| **Далее** | По мере правок — заменять любые голые `except Exception: pass` на логирование (критичные файлы уже с логированием). |
| **По возможности** | — (Signal Memory в рантайме выполнено 2026-01-30.) |

---

_Документ можно обновлять по мере выполнения пунктов._
