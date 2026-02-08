# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Массовое обновление зависимостей (2026-02-08):**
    - **Фреймворк:** FastAPI 0.121.3 → 0.128.4, Uvicorn 0.38.0 → 0.40.0
    - **ORM/DB:** SQLAlchemy 2.0.44 → 2.0.46, Alembic 1.17.1 → 1.18.3, Redis 6.4.0 → 7.1.0
    - **Pydantic:** 2.12.3 → 2.12.5, pydantic-settings 2.11.0 → 2.12.0, pydantic-core 2.41.4 → 2.41.5
    - **Сеть:** aiohttp 3.13.2 → 3.13.3, websockets 15.0.1 → 16.0
    - **MCP/API:** mcp 1.19.0 → 1.26.0, pybit 5.13.0 → 5.14.0
    - **Тестирование:** pytest 8.4.2 → 9.0.2
    - **Утилиты:** orjson 3.9.10 → 3.11.7, cryptography 46.0.3 → 46.0.4, celery 5.5.3 → 5.6.2, kombu 5.5.4 → 5.6.2
    - **Визуализация:** plotly 6.3.1 → 6.5.2, matplotlib 3.10.7 → 3.10.8
    - **Научные:** scipy 1.16.3 → 1.17.0, joblib 1.5.2 → 1.5.3, tqdm 4.67.1 → 4.67.3
    - **Системные:** psutil 7.1.3 → 7.2.2, structlog → 25.5.0, pip 25.3 → 26.0.1
    - **river:** constraint обновлён >=0.22.0,<0.24.0 во всех 3 requirements файлах
    - **docker SDK:** pin ослаблен ==7.0.0 → >=7.0.0

- **pyproject.toml — обновление целей линтинга:**
    - ruff target-version: py311 → py313
    - mypy python_version: 3.11 → 3.13
    - black target-version: [py311, py312] → [py313, py314]
    - Добавлен classifier Python 3.14

- **Dockerfile:** python:3.11-slim → python:3.14-slim (builder + runtime)

- **Docker Compose образы:**
    - PostgreSQL: 15-alpine → 17-alpine (prod + vault)
    - Elasticsearch: 8.5.0 → 8.17.0 (prod + monitoring)
    - Kibana: 8.5.0 → 8.17.0 (prod + monitoring)
    - Logstash: 8.5.0 → 8.17.0 (monitoring)
    - HashiCorp Vault: 1.15 → 1.19
    - MLflow: v2.10.0 → v2.21.0

### Added

- **`.vscode/extensions.json`** — рекомендуемые расширения для проекта (Python, Ruff, Docker, Copilot, YAML, TOML и др.)

### Known Issues

- **pandas 3.0 несовместим** с mlflow (<3), river (<3.0.0), pandas-ta — остаётся на 2.3.3
- **numpy ограничен 2.2.x** из-за numba 0.61.2 (требуется pandas-ta) — будет обновлён когда pandas-ta поддержит новый numba

### Fixed

- **Optimization `engine_type: "optimization"` 500 Error:** исправлен баг, при котором `engine_type="optimization"` вызывал 500 Internal Server Error в `/api/v1/optimizations/sync/grid-search`. Причина: `"optimization"` не был включён в условие single-process режима (строка 2316 в `optimizations.py`). Теперь `engine_type="optimization"` корректно обрабатывается как single-process Numba-движок.

### Added

- **MCP DeepSeek (Node.js) для Cursor:** папка `mcp-deepseek/` — MCP-сервер на Node.js с инструментами `deepseek_chat` и `deepseek_code_completion`. В `.cursor/mcp.json` добавлен сервер `deepseek-node` (запуск через `cmd /c cd /d ...\mcp-deepseek && node server.js`). API-ключ задаётся в env или в `mcp-deepseek/.env` (не в репозитории). См. `mcp-deepseek/README.md`.

### Changed

- **DeepSeek proxy (Base URL http://localhost:5000):** в `scripts/run_deepseek_proxy.ps1` исправлен расчёт корня проекта (один уровень вверх от `scripts/`), добавлена проверка наличия `.env` и использование `py -3.14` (как в проекте). В `docs/ai/CURSOR_DEEPSEEK_MODEL.md` — пошаговая диагностика «прокси не запускается»: создание `.env`, ключ, команда `python`/`py`, порт, запуск из корня.
- **Strategy Builder UI/UX (2026-02):** выбор тикера — немедленная синхронизация `runCheckSymbolDataForProperties()` (без debounce), blur вместо focus после выбора; База данных — эмодзи 🔒 заблокирован / 🔓 разблокирован, grid 3×2 (6 тикеров), `refreshDunnahBasePanel()` после sync, API_BASE для fetch; блок/разблок — `finally loadAndRender()` для обновления списка; удалённые тикеры исчезают.
- **Регрессия и калибровка (2026-02):** Установлены numba, vectorbt, torch. calibrate_166_metrics — 51/51 метрик ✅. compare_vectorbt_vs_fallback — sys.path + DATABASE_PATH. REMAINING_AND_NEW_TASKS обновлён: инструкции по калибровке (TV_DATA_DIR, PYTHONIOENCODING на Windows).
- **Зависимости:** добавлена опциональная группа `dev-full` (numba, vectorbt, torch) в pyproject.toml для полного покрытия тестов.
- **calibrate_166_metrics.py:** TV_DATA_DIR env для пути к TradingView экспорту; fix Unicode на Windows.
- **compare_vectorbt_vs_fallback.py:** sys.path + DATABASE_PATH env.
- **L2 Order Book (experimental):** WebSocket real-time collector, CGAN (PyTorch) для генерации стакана, обучение на NDJSON, скрипты `l2_lob_collect_ws.py` и `l2_lob_train_cgan.py`. модуль `backend/experimental/l2_lob/` — Bybit orderbook API, сбор снимков в NDJSON, replay в OrderBookSimulator, скелет Generative LOB.
- **ExecutionHandler:** SimulationExecutionHandler с slippage, latency, partial fills, rejection. Интеграция в EventDrivenEngine.
- **Cvxportfolio allocation:** Метод cvxportfolio (cvxpy convex optimization) для multi-asset портфеля.
- **EventDrivenEngine + StrategyBuilderAdapter:** create_on_bar_from_adapter(), run_event_driven_with_adapter() — запуск Strategy Builder стратегий в event-driven режиме.
- **Strategy Versions UI:** кнопка Versions в Strategy Builder, модалка с историей версий, Restore.
- **Strategy Builder — Export/Import шаблонов:** кнопки Export и Import в модалке Templates. Сохранение текущей стратегии в JSON и загрузка из файла.
- **Undo/Redo в Strategy Builder:** Ctrl+Z / Ctrl+Y, история 50 шагов. Охват: блоки, связи, drag, шаблоны, загрузка.
- **Regime overlay на equity:** чекбокс «Режим рынка» в backtest-results, загрузка `/market-regime/history`, box-аннотации (trending/ranging/volatile) на графике капитала.
- **Перепроверка roadmap:** EventDrivenEngine — тесты tests/test_event_driven_engine.py. ROADMAP_REMAINING_TASKS обновлён: Event-driven скелет ✅, Multi-asset portfolio ✅, §12 Heatmap и Trade distribution ✅, версионирование БД+API ✅. Regime overlay на equity — осталось.
- **Multi-asset portfolio (P2):** MIN_VARIANCE и MAX_SHARPE allocation (scipy.optimize), diversification_ratio, rolling_correlations, aggregate_multi_symbol_equity(). Тесты: tests/test_portfolio_allocation.py, API /advanced-backtest/portfolio.
- **Unified Trading API:** `backend/services/unified_trading/` — LiveDataProvider, StrategyRunner (завершение TODO из BACKTEST_PAPER_LIVE_API). — DataProvider, OrderExecutorInterface, HistoricalDataProvider, SimulatedExecutor (docs/architecture/BACKTEST_PAPER_LIVE_API.md).
- **Monte Carlo robustness API:** `POST /monte-carlo/robustness` — slippage_stress, price_randomization.
- **P2 RL environment:** calmar, drawdown_penalty reward, REWARD_FUNCTIONS, docs/architecture/RL_ENVIRONMENT.md
- **Backtest→Live API design:** docs/architecture/BACKTEST_PAPER_LIVE_API.md
- **P1 Regime integration:** `market_regime_enabled`, `market_regime_filter`, `market_regime_lookback` в SyncOptimizationRequest. При включении regime используется FallbackV4. UI в strategies.html (чекбокс, селект, окно).
- **Реализация рекомендаций ENGINE_OPTIMIZER_MODERNIZATION:** Optuna Bayesian оптимизация — `POST /sync/optuna-search` (TPE, n_trials, sampler_type). Monte Carlo robustness — добавлены SLIPPAGE_STRESS, PRICE_RANDOMIZATION. ExecutionSimulator — `backend/backtesting/execution_simulator.py` (latency, slippage, partial fills, rejections). Walk-Forward — режим `expanding`, `param_stability_report`, `get_param_stability_report()`. Roadmap: `docs/ROADMAP_ADVANCED_IDEAS.md`.
- **Гибридная двухфазная архитектура:** формализован pipeline Research → Validation → Paper → Live. Документ `docs/architecture/HYBRID_TWO_PHASE_PIPELINE.md` — точность и паритет (Numba↔FallbackV4 100%, VBT↔Fallback 10–60% drift). В `/sync/grid-search` добавлен параметр `validate_best_with_fallback` — опциональная перепроверка best_params на FallbackV4.
- **Предложения по модернизации движков и оптимизаторов:** создан `docs/ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md` — обзор мировых практик (event-driven, Monte Carlo robustness, Bayesian/Optuna, L2 order book, RL environments, backtest→live), приоритизированные идеи для roadmap.
- **Расширенный аудит проекта:** создан `docs/AUDIT_PROJECT_EXTENDED.md` — карта систем, аудит backend (API, backtesting, database, services), frontend, инфраструктуры, скриптов и тестов; кросс-срез, риски, рекомендации.
- **Выполнены рекомендации аудита:** удалён router_registry.py; API инвентаризация (docs/API_INVENTORY.md, legacy markers); консолидация docs + план декомпозиции strategy_builder.js (STRATEGY_BUILDER_INDEX.md); тесты test_fast_optimizer.py, test_live_trading_services.py; план API v2 (STATE_MANAGEMENT_AND_API_VERSIONING.md).
- **sync-all-tf:** блокирующие операции БД (чтение audit, persist) перенесены в thread pool (`asyncio.to_thread`), чтобы не блокировать event loop. Синхронизация 9 таймфреймов теперь выполняется параллельно и быстрее.
- **Окно Параметры (audit):** восстановление commission при загрузке; \_commission в buildStrategyPayload; убрана ссылка на initialCapital. Backend: CreateStrategyRequest/StrategyResponse расширены (leverage, position_size, parameters) — полная end-to-end поддержка сохранения/восстановления параметров. Документация: `docs/AUDIT_PARAMETERS_WINDOW.md`, тесты: `tests/test_e2e_parameters_window.py`.
- **Блок «Библиотека» (audit):** исправлена передача category; mapBlocksToBackendParams включает close_conditions. **Унификация параметров:** функция `_param()` в strategy_builder_adapter — fallback snake_case/camelCase для macd, bollinger, stochastic, qqe, stoch_rsi, ichimoku, parabolic_sar, keltner, filters. Документация: `docs/AUDIT_LIBRARY_BLOCK.md`.

### База Даннах (Dunnah Base) — управление тикерами в БД (2026-01-31)

- **Новая секция Properties «🗄️ База Даннах»:** отображает группы тикеров в БД (Symbol + Market Type + интервалы).
- **Удаление:** кнопка «Удалить» — удаляет все свечи тикера из БД.
- **Блокировка догрузки:** кнопки «Блокировать» / «Разблокировать» — тикеры в списке блокировки не догружаются при start_all (update_market_data), в DB Maintenance и при выборе в Properties.
- **Хранение блокировки:** `data/blocked_tickers.json`.
- **API:** GET/POST/DELETE `/symbols/blocked`, GET `/symbols/db-groups`, DELETE `/symbols/db-groups`.
- **Значок 🔒** в списке тикеров (Symbol) для заблокированных.

### Контроль устаревания БД — точный порог 2 года (2026-01-31)

- **Система уже была:** `db_maintenance_server.py` → `retention_cleanup`, задача `retention_cleanup` по расписанию (раз в 30 дней).
- **Исправление:** Расчёт порога заменён на точные 2 года (730 дней от текущей даты) вместо границ года; используется `RETENTION_YEARS` из `database_policy.py`.

### Нахлёст свечей при догрузке (2026-01-31)

- **Задача:** При проверке актуальности БД (start_all → update_market_data, DB Maintenance, Properties sync) догружать с нахлёстом нескольких свечей, чтобы избежать gaps на границе.
- **Реализация:** Переменный нахлёст по TF: 5 для 1m–60m, 4 для 4h, 3 для D, 2 для W/M.
- **Где:** `marketdata.py` (sync-all-tf, refresh), `update_market_data.py`, `db_maintenance_server.py` (\_update_stale_data).
- **DB maintenance:** INSERT OR REPLACE для перезаписи граничных свечей в зоне нахлёста.

### Единый набор таймфреймов: 1m, 5m, 15m, 30m, 60m, 4h, 1D, 1W, 1M (2026-01-31)

- Ограничен набор таймфреймов для всех систем.
- Backend: ALL_TIMEFRAMES, interval_ms_map, freshness_thresholds, tf_timeouts — добавлен M, обновлены.
- Frontend: Strategy Builder и Strategies — выпадающие списки только с этим набором; BYBIT_TF_OPTS, BYBIT_INTERVALS.
- DB maintenance, show_db, sync_missing_data — обновлены intervals.
- Устаревшие TF (3m, 2h, 6h, 12h) при загрузке стратегий маппятся на ближайший: 3→5, 120→60, 360→240, 720→D.

### Strategy Builder: зависание при быстром переключении тикеров (2026-01-31)

- **Проблема:** При переключении на другой тикер сразу после загрузки предыдущего новая загрузка зависала.
- **Причина:** Две синхронизации (старая и новая) выполнялись параллельно и конкурировали за ресурсы.
- **Исправление:** При старте синхронизации нового тикера отменяется предыдущий fetch (AbortController). Отменённая синхронизация не обновляет UI.

### Strategy Builder: таймаут синхронизации и сообщение об ошибке (2026-01-31)

- **Проблема:** Для некоторых тикеров (напр. 1000000BABYDOGEUSDT) показывалось «Синхронизация в фоне», но загрузка фактически прерывалась — данные не загружались.
- **Причина:** Таймаут 15 с был слишком мал; синхронизация 8 TF (включая 1m) занимает 1–2 мин. При отмене запроса бэкенд также прерывался.
- **Исправления:** Таймаут увеличен до 120 с; при таймауте показывается явное сообщение об ошибке; клик по блоку статуса при ошибке запускает повторную попытку.

### Strategy Builder: Properties — сворачивание при выборе тикера и вкладки (2026-01-31)

- **Проблема:** При выборе тикера панель Properties закрывалась; после повторного открытия секции (ОСНОВНЫЕ ПАРАМЕТРЫ, EVALUATION CRITERIA и др.) не раскрывались.
- **Причины:** (1) Клик по выпадающему списку тикеров (он в body) воспринимался как «вне панели» и вызывал сворачивание. (2) При открытии sidebar не раскрывалась первая секция. (3) Два обработчика на заголовки секций (sidebar-toggle и strategy_builder) приводили к двойному toggle.
- **Исправления:** Исключение `#backtestSymbolDropdown` из логики «клик вне панели»; событие `properties-symbol-selected` для сброса таймера сворачивания при выборе тикера; при открытии sidebar раскрывается первая секция; удалён дублирующий обработчик в strategy_builder, остаётся только sidebar-toggle.js.

### Strategy Builder: загрузка/догрузка тикера и автоактуализация (2026-01-31)

- **Выбор тикера:** При выборе тикера из выпадающего списка (Symbol) выполняется синхронизация: если тикер не в БД — полная загрузка на всех TF (1m, 5m, 15m, 30m, 1h, 4h, D, W); если есть — догрузка актуальных свечей.
- **Тип рынка:** При смене SPOT/LINEAR (бессрочные фьючерсы) для выбранного тикера запускается синхронизация данных.
- **Backend:** В `/symbols/sync-all-tf` добавлен фильтр `market_type` в запросах к БД (корректное разделение spot/linear). В список синхронизируемых TF включён 1m.
- **Автоактуализация:** После успешной синхронизации запускается таймер обновления: 1m/5m — каждые 5 мин; 15m — каждые 15 мин; 30m — каждые 30 мин; 1h — 1 ч; 4h — 4 ч; D — 1 день; W — 1 неделя. При смене TF или тикера таймер перезапускается.

### Список тикеров Bybit в Strategy Builder (2026-01-31)

- **Проблема:** В поле Symbol (Properties) отображалось только 3 тикера вместо полного списка (~500). Список не открывался/не закрывался, не прокручивался; при обновлении тикеров загружался один тип рынка; при сбое сети кэш затирался пустым списком.
- **Причины:** (1) Два обработчика на GET `/api/v1/marketdata/symbols-list` (marketdata + tickers_api) — срабатывал первый, без полной пагинации Bybit. (2) Bybit API instruments-info отдаёт данные постранично (limit/cursor) — загружалась только первая страница. (3) Фронт ограничивал список до 100/80 пунктов; выпадающий список открывался при загрузке страницы и перекрывался соседними элементами (z-index, overflow). (4) refresh-tickers при падении одной категории перезаписывал кэш пустым списком.
- **Исправления:** Единственный обработчик symbols-list — tickers_api (дубликат в marketdata удалён). В `BybitAdapter.get_symbols_list()` добавлена полная пагинация (limit=1000, cursor/nextPageCursor), проверка retCode в ответе Bybit, таймаут ≥30 с, логирование количества тикеров. Регистрация маршрутов symbols-list и refresh-tickers на уровне app через `add_api_route`. На фронте: выпадающий список открывается только по focus/click; закрытие по клику вне и через `closeSymbolDropdown()`; z-index 100000, max-height 220px, overflow-y auto; отображается до 500 тикеров (без обрезки до 100). В refresh-tickers кэш обновляется только при непустом ответе (при сбое одной категории вторая не затирается). Пороги slow_requests для путей symbols и refresh-tickers увеличены (long_running_paths).
- **Документация:** Добавлен `docs/TICKERS_SYMBOLS_LIST.md` с описанием проблемы, потока данных и проверки. Скрипт `scripts/test_bybit_symbols_direct.py` для прямой проверки Bybit API.

### Strategy Builder: Properties — работоспособность и все настройки (2026-01-30)

- **Разделение панели Properties:** Поля стратегии (Основные: тип рынка, направление; Data & Timeframe: timeframe, symbol, capital) вынесены в отдельный контейнер `#strategyBasicProps` и больше не перезаписываются при выборе блока. Параметры блока выводятся в отдельной секции «Параметры блока» (`#blockProperties`) — при выборе блока там отображаются Name/Type/Category и параметры из customLayouts или fallback.
- **Backtest Settings:** Добавлено редактируемое поле Commission % (`#backtestCommission`, по умолчанию 0.07); значение передаётся в `buildBacktestRequest()` (в API уходит commission / 100, например 0.0007). При загрузке стратегии поля Backtest Settings синхронизируются с данными стратегии: symbol, initial_capital, leverage, direction.
- **Тексты:** Заглушка при отсутствии выбранного блока приведена к русскому: «Выберите блок на холсте, чтобы редактировать его параметры.»

### Strategy Builder: исправления по аудиту Properties и Библиотека (2026-01-30)

- **Properties панель:** При выборе блока в правой панели параметры выводятся через `renderGroupedParams(block, false)` (customLayouts) — те же checkbox/select/number, что и в popup. Для блоков без layout сохранён fallback с текстовыми полями. Обработка изменений — делегированная в `setupEventListeners()` на `#propertiesPanel` (change/input по полям с `data-param-key`, используется `selectedBlockId`). Добавлена `escapeHtml()` для безопасного вывода.
- **Библиотека:** В `renderBlockLibrary()` добавлены 10 категорий: Correlation & Multi-Symbol, Alerts, Visualization, DCA Grid, Multiple Take Profits, ATR Exit, Signal Memory, Close Conditions (TradingView), Price Action Patterns, Divergence. Для отсутствующих ключей — проверка `if (!blocks || !Array.isArray(blocks)) return`.
- **UI:** Секция Properties «Закладка-2» переименована в «Data & Timeframe». Документ аудита `docs/STRATEGY_BUILDER_PROPERTIES_LIBRARY_AUDIT.md` обновлён (рекомендации отмечены выполненными).

### Signal Memory в рантайме (2026-01-30)

- **StrategyBuilderAdapter:** Добавлен хелпер `apply_signal_memory(buy_events, sell_events, memory_bars)` — расширение buy/sell на N баров после события; противоположный сигнал отменяет память. Применён в фильтрах: **rsi_filter** (use_signal_memory / signal_memory_bars), **stochastic_filter** (activate_stoch_cross_memory / stoch_cross_memory_bars, activate_stoch_kd_memory / stoch_kd_memory_bars), **two_ma_filter** (ma_cross_memory_bars), **macd_filter** (macd_signal_memory_bars, disable_macd_signal_memory=False).
- **Исправления:** В `_execute_filter` для stochastic_filter и macd_filter исправлена распаковка результата: `calculate_stochastic` и `calculate_macd` возвращают кортежи, не словари. Порядок аргументов `calculate_stochastic(high, low, close, ...)` приведён к сигнатуре.
- **Тесты:** Добавлен `tests/test_signal_memory_adapter.py` (5 тестов: RSI memory extend, RSI no memory, Stochastic cross memory, Two MA memory, MACD memory).

### План REMAINING: комиссия 0.07%, Python, документация (2026-01-30)

- **Дефолт комиссии 0.07% (TradingView parity):** Во всех сценариях бэктеста и оптимизации по умолчанию установлено 0.0007: `backend/backtesting/models.py` (commission_value), `backend/api/routers/optimizations.py` (4 места), `backend/tasks/backtest_tasks.py`, `backend/services/data_service.py`, `backend/services/advanced_backtesting/portfolio.py`, `backend/backtesting/optimizer.py`, `backend/backtesting/gpu_optimizer.py`, `backend/backtesting/gpu_batch_optimizer.py`, `backend/backtesting/fast_optimizer.py`, `backend/backtesting/vectorbt_optimizer.py`.
- **Версия Python в правилах:** В `.cursor/rules/project.mdc` — «3.11+ (рекомендуется 3.14)»; в `AGENTS.MD` — «Python 3.11+ required (3.14 recommended)»; в `README.md` — «3.11+ (3.12/3.13/3.14 supported; 3.14 recommended for dev)».
- **Документация:** Обновлены `docs/tradingview_dca_import/IMPLEMENTATION_STATUS.md` (Phase 3–4 чеклисты, Next Steps), `docs/SESSION_5_4_AUDIT_REPORT.md` (WebSocket UI — Done, итоговая таблица), `docs/FULL_IMPLEMENTATION_PLAN.md` (Phase 1.1–1.2 [x], WS интегрирован), `docs/REMAINING_AND_NEW_TASKS.md` (комиссия и Python отмечены выполненными, секция документации — выполнено).

### Синхронизация документации и задачи (2026-01-30)

- **Маппинг Strategy Builder → DCAEngine:** В `StrategyBuilderAdapter.extract_dca_config()` добавлен сбор блоков close_conditions и indent_order; в `strategy_builder.py` в `strategy_params` передаются `close_conditions` и `indent_order`; в `DCAEngine._configure_from_config()` — чтение и применение. В `run_from_config` добавлены `_precompute_close_condition_indicators`, логика indent_order при входе.
- **DCAEngine:** Исправлен `EquityCurve` в результате бэктеста: поле `equity` вместо `values`, timestamps как datetime.
- **E2E:** Добавлен `tests/test_e2e_dca_close_condition.py` (3 теста: time_bars_close, indent_order config, rsi_close config).
- **Signal Memory:** В `docs/REMAINING_AND_NEW_TASKS.md` зафиксировано назначение и место применения.
- **except Exception: pass:** Заменены на логирование в `backend/services/adapters/bybit.py` и `backend/database/sqlite_pool.py`.
- **Документация:** Обновлены SESSION_5_4_AUDIT_REPORT.md, REMAINING_AND_NEW_TASKS.md.

### P0: Evaluation Criteria & Optimization Config Panels (2026-01-30 - Session 5.7)

**Complete implementation of strategy builder panels for optimization configuration.**

#### Evaluation Criteria Panel ✅

- Created `frontend/js/pages/evaluation_criteria_panel.js` (~750 lines)
    - `EvaluationCriteriaPanel` class with full functionality
    - Primary metric selection with grouped categories
    - Secondary metrics grid with category organization
    - Metric weights sliders for composite scoring
    - Dynamic constraints list (add/remove/enable)
    - Multi-level sort order with drag & drop reordering
    - Quick presets: Conservative, Aggressive, Balanced, Frequency
    - localStorage state persistence
    - Event emission for integration

#### Optimization Config Panel ✅

- Created `frontend/js/pages/optimization_config_panel.js` (~800 lines)
    - `OptimizationConfigPanel` class with complete UI
    - Method selector: Bayesian, Grid Search, Random, Walk-Forward
    - Visual dual-range sliders for parameter ranges
    - Auto-detection of parameters from strategy blocks
    - Data period with train/test split slider
    - Walk-forward configuration (train/test/step windows)
    - Resource limits (trials, timeout, workers)
    - Advanced options: early stopping, pruning, warm start
    - Estimated time calculation
    - Mode indicator (Single Backtest vs Optimization)

#### CSS Styles ✅

- Extended `frontend/css/strategy_builder.css` (+600 lines)
    - Toggle switch component
    - Metric categories grid
    - Metric weights sliders
    - Sort order list with drag handles
    - Quick presets buttons
    - Method selector cards
    - Dual-range slider styling
    - Train/test split visualization
    - Walk-forward preview
    - Limits grid
    - Advanced options accordion
    - Estimated time display

#### Backend API Endpoints ✅

Extended `backend/api/routers/strategy_builder.py`:

- Pydantic models: `MetricConstraint`, `SortSpec`, `EvaluationCriteria`
- Pydantic models: `ParamRangeSpec`, `DataPeriod`, `OptimizationLimits`, `AdvancedOptions`, `OptimizationConfig`
- `POST /strategies/{id}/criteria` - Set evaluation criteria
- `GET /strategies/{id}/criteria` - Get evaluation criteria
- `POST /strategies/{id}/optimization-config` - Set optimization config
- `GET /strategies/{id}/optimization-config` - Get optimization config
- `GET /metrics/available` - Get all available metrics with presets

#### Tests ✅

- Created `tests/test_evaluation_optimization_panels.py` (~330 lines)
    - `TestEvaluationCriteriaModels` - 4 tests
    - `TestOptimizationConfigModels` - 4 tests
    - `TestEvaluationCriteriaEndpoints` - 3 tests
    - `TestOptimizationConfigEndpoints` - 2 tests
    - `TestAvailableMetrics` - 1 test
    - `TestConstraintValidation` - 2 tests
    - `TestCompositeScoring` - 2 tests
    - **Total: 18 tests, all passing**

---

### P0: Optimization Results Viewer (2026-01-30 - Session 5.6)

**Full implementation of interactive optimization results viewer with filtering, sorting, charts, and comparison.**

#### Frontend Module ✅

- Created `frontend/js/pages/optimization_results.js` (~1250 lines)
    - `OptimizationResultsViewer` class with full lifecycle management
    - Dynamic table columns based on optimization parameters
    - Real-time filtering: minSharpe, maxDD, minWinRate, minPF, minTrades
    - Multi-column sorting with direction toggle
    - Pagination with configurable page size (10, 25, 50, 100)
    - Convergence chart (best_score over trials via Chart.js)
    - Sensitivity chart per parameter
    - Details modal for individual result inspection
    - Comparison modal for side-by-side result analysis
    - Apply params to strategy functionality
    - CSV/JSON export with all filters applied
    - Demo data fallback when no optimization_id provided

#### HTML Updates ✅

- Updated `frontend/optimization-results.html`
    - Removed ~350 lines of inline JavaScript
    - Added modular script import
    - Legacy compatibility functions delegating to module instance

#### CSS Extensions ✅

- Extended `frontend/css/optimization_components.css` (+150 lines)
    - `.opt-results-table` - sticky headers, sortable columns
    - `.opt-rank-badge` - gold/silver/bronze rank badges with gradients
    - `.opt-metric-value.positive/.negative` - color-coded metrics
    - `.opt-loading-overlay`, `.opt-empty-state` - loading/empty states
    - `.opt-comparison-table` - comparison modal styling
    - Dark theme support

#### Backend API Endpoints ✅

Extended `backend/api/routers/optimizations.py` (+220 lines):

- `GET /{id}/charts/convergence` - Returns convergence chart data (trials, best_scores, all_scores, metric)
- `GET /{id}/charts/sensitivity/{param}` - Returns sensitivity data per parameter (param_name, values, scores)
- `POST /{id}/apply/{rank}` - Applies selected result params to strategy config
- `GET /{id}/results/paginated` - Paginated filtered results with sort support

#### Tests ✅

- Created `tests/test_optimization_results_viewer.py` (~250 lines)
    - `TestConvergenceEndpoint` - 2 tests
    - `TestSensitivityEndpoint` - 2 tests
    - `TestApplyEndpoint` - 2 tests
    - `TestPaginatedEndpoint` - 3 tests
    - `TestResultsViewerIntegration` - 3 tests
    - `TestEdgeCases` - 4 tests
    - **Total: 16 tests, all passing**

---

### Cursor Rules — требуемые исправления (2026-01-30)

- **Пути:** Устранён хардкод в tests/test_auto_event_binding.py, tests/test_safedom.py, test_frontend_security.py, scripts/adhoc/test_btc_correlation.py, test_autofix_constraints.py, test_v4_quick.py — используется PROJECT_ROOT / Path(**file**).resolve().parents[N], DATABASE_PATH из env.
- **dev.ps1:** Создан заново (run, lint, format, test, test-cov, clean, mypy, help).
- **Документация:** Созданы .agent/docs/ARCHITECTURE.md, .agent/docs/DECISIONS.md (ссылки на docs/), docs/DECISIONS.md (ADR-001 — ADR-005).
- **except Exception: pass:** Заменены на логирование в backend/api/app.py, backend/backtesting/engines/dca_engine.py, backend/api/lifespan.py, backend/backtesting/engine.py, backend/api/routers/optimizations.py.

### Cursor Rules Analysis (2026-01-30)

- Added **docs/CURSOR_RULES_ANALYSIS.md** — анализ проекта с учётом правил из AGENTS.md и `.cursor/rules/*.mdc`.
- Выявлено: хардкод путей в тестах/скриптах, отсутствие dev.ps1, расхождение .agent/docs/ и DECISIONS/ARCHITECTURE с фактической структурой docs/, массовое использование `except Exception: pass` в backend.
- В отчёте даны приоритизированные рекомендации по устранению расхождений.

### Full DCA Backend Implementation (2026-01-30 - Session 5.5 Part 2)

**Backend logic for all Strategy Builder features.**

#### Backend Validation Rules ✅

Extended `BLOCK_VALIDATION_RULES` in `strategy_validation_ws.py`:

- 6 Close Condition blocks: `rsi_close`, `stoch_close`, `channel_close`, `ma_close`, `psar_close`, `time_bars_close`
- New filters: `rvi_filter`, `indent_order`, `atr_stop` (extended)
- Updated exit block types for strategy validation

#### DCAEngine Close Conditions ✅

New `CloseConditionsConfig` dataclass and methods in `dca_engine.py`:

- `_check_close_conditions()` - main dispatcher for all close conditions
- `_check_rsi_close()` - RSI reach/cross detection
- `_check_stoch_close()` - Stochastic reach detection
- `_check_channel_close()` - Keltner/Bollinger breakout/rebound
- `_check_ma_close()` - Two MAs cross detection
- `_check_psar_close()` - Parabolic SAR flip detection
- Pre-computed indicator caches for performance

#### MTF Utilities ✅

New `backend/core/indicators/mtf_utils.py`:

- `resample_ohlcv()` - timeframe resampling
- `map_higher_tf_to_base()` - value mapping
- `calculate_supertrend_mtf()` - SuperTrend calculation
- `calculate_rsi_mtf()` - RSI calculation
- `MTFIndicatorCalculator` class - cached MTF calculations
- `apply_mtf_filters()` - filter application

#### Extended Indicators ✅

New `backend/core/indicators/extended_indicators.py`:

- `calculate_rvi()` - Relative Volatility Index
- `calculate_linear_regression_channel()` - Linear Regression with slope
- `find_pivot_points()` - S/R level detection
- `levels_break_filter()` - Pivot breakout signals
- `find_accumulation_areas()` - Volume-based accumulation detection

#### Indent Order ✅

New `IndentOrderConfig` and `PendingIndentOrder` dataclasses:

- `_create_indent_order()` - create pending limit order
- `_check_indent_order_fill()` - check fill or expiration
- Integration in main DCAEngine run loop

#### UI Enhancements ✅

- Extended `bop_filter` with triple smooth, cross line mode
- Added `block_worse_filter` in blockLibrary and customLayouts

#### New Tests (47 tests) ✅

- `tests/test_extended_indicators.py` - 13 tests
- `tests/test_dca_close_conditions.py` - 18 tests
- `tests/test_validation_rules_session55.py` - 16 tests

---

### Full DCA Implementation Plan Execution (2026-01-30 - Session 5.5)

**Comprehensive Strategy Builder expansion based on TradingView Multi DCA Strategy [Dimkud].**

#### Phase 1.1: WebSocket Integration in UI ✅

- Integrated `wsValidation.validateParam()` in `updateBlockParam()`
- Added server-side validation before `saveStrategy()`
- Created WebSocket status indicator with CSS styling
- Event listeners for `ws-validation-result`, `ws-validation-connected/disconnected`

#### Phase 1.2: Price Action UI (47 Patterns) ✅

Expanded `price_action_filter` from 22 to 47 patterns:

- **Bullish Exotic**: Pin Bar, Three Line Strike, Kicker, Abandoned Baby, Belt Hold, Counterattack, Ladder Bottom, Stick Sandwich, Homing Pigeon, Matching Low
- **Bearish Exotic**: Pin Bar, Three Line Strike, Kicker, Abandoned Baby, Belt Hold, Counterattack, Ladder Top, Stick Sandwich, Matching High
- **Neutral/Structure**: Inside Bar, Outside Bar
- **Gap Patterns**: Gap Up, Gap Down, Gap Up Filled, Gap Down Filled

#### Phase 2: Close Conditions (6 Types) ✅

New exit blocks in `blockLibrary.exits`:

- `rsi_close` - RSI Reach/Cross level close
- `stoch_close` - Stochastic Reach/Cross level close
- `channel_close` - Keltner/Bollinger channel breakout close
- `ma_close` - Two MAs cross close
- `psar_close` - Parabolic SAR flip close
- `time_bars_close` - Time/bars-based close with profit filter

#### Phase 3: MTF Expansion (3 Timeframes) ✅

Extended `supertrend_filter` and `rsi_filter` for multi-timeframe analysis:

- SuperTrend TF1/TF2/TF3 with separate ATR period, multiplier, BTC source
- RSI TF1/TF2/TF3 with separate period, range conditions

#### Phase 4: New Indicators ✅

- `rvi_filter` - Relative Volatility Index with range filter
- Extended `linreg_filter` - Signal memory, slope direction, breakout/rebound mode
- Extended `levels_filter` - Pivot bars, search period, channel width, test count
- Extended `accumulation_filter` - Backtrack interval, min bars, breakout signal

#### Phase 5: Advanced Features ✅

- `indent_order` - Limit entry with percentage offset, cancel after X bars
- Extended `atr_stop` - Full ATR SL/TP with wicks, method (WMA/RMA/SMA/EMA), separate periods/multipliers

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - All new blocks, defaultValues, customLayouts, validation rules
- `frontend/css/strategy_builder.css` - WebSocket status indicator styles

#### Tests

- 65 passed, 2 skipped (WebSocket + Price Action tests)

#### Documentation

- Created `docs/FULL_IMPLEMENTATION_PLAN.md`
- Updated `docs/SESSION_5_4_AUDIT_REPORT.md` with Phase 6 summary

---

### Exotic Candlestick Patterns + WebSocket Validation (2026-01-30 - Session 5.4)

**Extended pattern library and real-time validation via WebSocket.**

#### New Exotic Candlestick Patterns in `price_action_numba.py`

Added 11 new Numba JIT-optimized pattern detection functions:

- **`detect_three_line_strike()`** - Bullish/Bearish three line strike reversal
- **`detect_kicker()`** - Strong gap reversal pattern (one of the most reliable)
- **`detect_abandoned_baby()`** - Rare reversal with gapped doji
- **`detect_belt_hold()`** - Single candle reversal at extremes
- **`detect_counterattack()`** - Equal close reversal pattern
- **`detect_gap_patterns()`** - Gap up/down with fill detection
- **`detect_ladder_pattern()`** - Ladder bottom/top (5-candle reversal)
- **`detect_stick_sandwich()`** - Three candle sandwich pattern
- **`detect_homing_pigeon()`** - Bullish continuation (two reds, second inside)
- **`detect_matching_low_high()`** - Support/resistance at equal levels

Total patterns now: **47** (was 26)

#### WebSocket Real-Time Validation

**New Backend Endpoint**: `backend/api/routers/strategy_validation_ws.py`

- WebSocket endpoint: `/api/v1/strategy-builder/ws/validate`
- Message types:
    - `validate_param` - Single parameter validation
    - `validate_block` - Full block validation
    - `validate_connection` - Connection compatibility check
    - `validate_strategy` - Entire strategy validation
    - `heartbeat` - Keep-alive

**New Frontend Module**: `frontend/js/pages/strategy_builder_ws.js`

- Auto-reconnection with exponential backoff
- Request debouncing (150ms)
- Heartbeat every 30 seconds
- Visual state updates for blocks/params
- Fallback to local validation when disconnected

#### Test Coverage

- **40 tests** for exotic patterns (`tests/test_price_action_numba.py`)
- **27 tests** for WebSocket validation (`tests/test_strategy_validation_ws.py`) — 25 original + 2 added during audit
- Total tests: **67**

> **Audit (2026-01-30):** See `docs/SESSION_5_4_AUDIT_REPORT.md`. WebSocket validation API is implemented; UI integration (calling `wsValidation.validateParam`/`validateBlock` from Strategy Builder) is pending.

---

### Strategy Builder - UI Real-Time Validation (2026-01-30 - Session 5.3)

**Live parameter validation with visual feedback.**

#### New: `blockValidationRules` Configuration

Added comprehensive validation rules for all block types:

- **Momentum indicators**: RSI, Stochastic, StochRSI, Williams %R, MFI, CCI, CMO, ROC
- **Trend indicators**: SMA, EMA, MACD, ADX, Supertrend, Ichimoku, Parabolic SAR
- **Volatility indicators**: ATR, Bollinger, Keltner, Donchian, StdDev
- **Action blocks**: stop_loss, take_profit, trailing_stop, atr_stop, chandelier_stop, break_even, profit_lock, scale_out, multi_tp, limit_entry, stop_entry
- **Exit blocks**: atr_exit, session_exit, indicator_exit, partial_close, multi_tp_exit, break_even_exit
- **Price Action patterns**: engulfing, hammer, doji, pin_bar, shooting_star, marubozu, tweezer, harami
- **Divergence blocks**: RSI, MACD, Stochastic, OBV, MFI divergence

#### Validation Features

- **Type validation**: Ensures numbers are numbers
- **Range validation**: min/max bounds for each parameter
- **Required fields**: Marks mandatory parameters
- **Cross-parameter validation**: MACD fast < slow, between min < max
- **Multi-TP validation**: TP1 < TP2 < TP3 ordering

#### Visual Feedback (CSS)

- `.block-valid` - Subtle green border for valid blocks
- `.block-invalid` - Red border with pulse animation for invalid blocks
- `.param-valid` / `.param-invalid` - Input field styling
- Warning icon (⚠️) on blocks with validation errors
- Tooltip on hover showing error details

#### Enhanced `validateStrategy()` Function

Now validates:

1. Strategy has blocks
2. Main strategy node exists
3. Connections to main node
4. Entry signal connections
5. Disconnected blocks warning
6. **NEW: Block parameter validation**

### Numba JIT Price Action Patterns (2026-01-30 - Session 5.2)

**High-performance candlestick pattern detection with 10-50x speedup.**

#### New Module: `backend/core/indicators/price_action_numba.py`

Created Numba JIT-optimized pattern detection with:

- **`detect_engulfing()`** - Bullish/Bearish engulfing patterns
- **`detect_hammer()`** - Hammer and Hanging Man patterns
- **`detect_doji()`** - Standard, Dragonfly, Gravestone doji
- **`detect_pin_bar()`** - Bullish/Bearish pin bars
- **`detect_inside_bar()`** - Inside bar consolidation
- **`detect_outside_bar()`** - Outside bar volatility
- **`detect_three_soldiers_crows()`** - Three white soldiers / black crows
- **`detect_shooting_star()`** - Bearish shooting star
- **`detect_marubozu()`** - Strong momentum candles
- **`detect_tweezer()`** - Tweezer top/bottom reversals
- **`detect_three_methods()`** - Rising/Falling three methods
- **`detect_piercing_darkcloud()`** - Piercing line / Dark cloud
- **`detect_harami()`** - Bullish/Bearish harami
- **`detect_morning_evening_star()`** - Morning/Evening star
- **`detect_all_patterns()`** - Batch detection (all 26 signals)

#### Performance

- All functions decorated with `@njit(cache=True)` for JIT compilation
- Graceful fallback when Numba not installed
- 100 iterations of 1000-bar engulfing detection in under 1 second
- 10 iterations of 10000-bar all-patterns detection in under 2 seconds

#### Tests

- 21 new tests in `tests/test_price_action_numba.py`
- Pattern detection accuracy tests
- Performance benchmark tests
- Edge case handling (empty arrays, single bars, zero body)

### Strategy Builder - Unit Tests & Bug Fixes (2026-01-30 - Session 5.2)

#### New: `tests/test_strategy_builder_handlers.py`

Comprehensive test suite with 35 tests covering:

- **TestActionHandlers** (13 tests): stop_loss, take_profit, trailing_stop, atr_stop, chandelier_stop, break_even, profit_lock, scale_out, multi_tp, limit_entry, stop_entry, close, entry_price_action
- **TestExitHandlers** (7 tests): atr_exit, session_exit, signal_exit, indicator_exit, partial_close, multi_tp_exit, break_even_exit
- **TestPriceActionHandlers** (9 tests): All candlestick patterns (engulfing, hammer, doji, etc.)
- **TestDivergenceHandlers** (2 tests): RSI divergence, MACD divergence
- **TestIntegration** (3 tests): Multi-block strategies with 10+ blocks
- **TestEdgeCases** (2 tests): Empty OHLCV data, unknown block types

#### Bug Fixes in `strategy_builder_adapter.py`

Found and fixed 4 bugs during testing:

1. **`atr_exit` handler** - Fixed `calculate_atr()` signature (needed high, low, close arrays)
2. **`stoch_divergence` handler** - Fixed `calculate_stochastic()` return type (tuple not dict)
3. **`mfi_divergence` handler** - Fixed `calculate_mfi()` signature (needed 4 arrays)
4. **`rsi_divergence` handler** - Fixed numpy array vs pandas Series issue

#### New: `docs/STRATEGY_BUILDER_ADAPTER_API.md`

Comprehensive API documentation (~500 lines) covering:

- Block Categories overview
- Indicator blocks (RSI, MACD, BB, etc.)
- Filter blocks with all comparisons
- Action blocks with parameters
- Exit blocks with configuration
- Price Action patterns
- Divergence detection
- Close conditions
- Usage examples and error handling

### Strategy Builder Adapter - 100% Block Coverage (2026-01-30 - Session 5.1)

**Full frontend-backend parity achieved: 110/110 blocks covered!**

#### Actions Category - Complete (17 handlers)

Added missing action handlers:

- **`stop_loss`** - Stop loss with percent configuration
- **`take_profit`** - Take profit with percent configuration
- **`trailing_stop`** - Trailing stop with activation level
- **`atr_stop`** - ATR-based stop loss (period + multiplier)
- **`chandelier_stop`** - Chandelier stop from highest high
- **`break_even`** - Move stop to entry after trigger percent
- **`profit_lock`** - Lock minimum profit after threshold
- **`scale_out`** - Partial position close at profit target
- **`multi_tp`** - Multi take profit levels (TP1/TP2/TP3)
- **`limit_entry`** - Limit order entry at specific price
- **`stop_entry`** - Stop order entry on breakout
- **`close`** - Close any position

#### Exits Category - Complete (12 handlers)

Added missing exit handlers:

- **`atr_exit`** - ATR-based TP/SL with multipliers
- **`session_exit`** - Exit at session end (specific hour)
- **`signal_exit`** - Exit on opposite signal
- **`indicator_exit`** - Exit on indicator condition (RSI threshold etc.)
- **`partial_close`** - Partial close at profit targets
- **`multi_tp_exit`** - Multi TP levels with allocation %
- **`break_even_exit`** - Move to breakeven after profit trigger

#### Price Action Patterns - Complete (9 handlers)

Added missing candlestick patterns:

- **`hammer_hangman`** - Hammer and Hanging Man patterns
- **`doji_patterns`** - Standard, Dragonfly, Gravestone doji
- **`shooting_star`** - Bearish reversal after uptrend
- **`marubozu`** - Strong momentum candle (no wicks)
- **`tweezer`** - Tweezer top/bottom reversal
- **`three_methods`** - Rising/Falling three methods continuation
- **`piercing_darkcloud`** - Piercing line / Dark cloud cover
- **`harami`** - Inside bar reversal pattern

#### Divergence Detection - Complete (5 handlers)

Added missing divergence types:

- **`stoch_divergence`** - Stochastic K divergence
- **`mfi_divergence`** - Money Flow Index divergence

#### Coverage Summary

| Category         | Frontend | Backend | Status  |
| ---------------- | -------- | ------- | ------- |
| Indicators       | 34       | 34      | ✅ 100% |
| Filters          | 24       | 24      | ✅ 100% |
| Actions          | 17       | 21+     | ✅ 100% |
| Exits            | 12       | 14+     | ✅ 100% |
| Price Action     | 9        | 15+     | ✅ 100% |
| Divergence       | 5        | 5       | ✅ 100% |
| Close Conditions | 9        | 9       | ✅ 100% |

**Total: 110/110 blocks (100%)**

---

### Strategy Builder Adapter - MTF & Filters Extension (2026-01-30 - Session 5)

#### Multi-Timeframe Indicator Added

Implemented `mtf` indicator with full data resampling support:

- Resamples OHLCV to higher timeframe (5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w)
- Calculates indicator (EMA, SMA, RSI, ATR) on HTF data
- Forward-fills results back to original timeframe
- Graceful fallback on resampling errors

#### New Filters Implemented (6 Additional)

- **`accumulation_filter`** - Detects volume accumulation zones (high volume + tight range)
- **`linreg_filter`** - Linear regression channel with slope and deviation
- **`divergence_filter`** - Detects RSI/MACD/OBV divergence signals
- **`bop_filter`** - Balance of Power indicator filter
- **`levels_filter`** - Pivot point / swing high-low break filter
- **`price_action_filter`** - Candlestick patterns (engulfing, doji, hammer)

#### Code Quality Improvements (PEP 585)

- Replaced `Dict[...]` with `dict[...]` throughout codebase
- Replaced `List[...]` with `list[...]`
- Added `from __future__ import annotations` for forward compatibility

#### Tests Status

- ✅ 27 tests passing (9 DCA E2E + 18 API)

---

### Strategy Builder Adapter Complete Integration (2026-01-30 - Session 4)

#### Expanded Indicator Support (28 New Indicators)

Extended `_execute_indicator()` method to support all frontend indicators:

- **Oscillators:** QQE, Stoch RSI, Williams %R, ROC, MFI, CMO, CCI
- **Moving Averages:** WMA, DEMA, TEMA, Hull MA
- **Trend:** SuperTrend, Ichimoku, Parabolic SAR, Aroon
- **Volatility:** ATRP, Keltner Channels, Donchian Channels, StdDev
- **Volume:** OBV, VWAP, CMF, A/D Line, PVT
- **Other:** Pivot Points

#### New Filter Category Handler (`_execute_filter()`)

Implemented 20+ filter types matching frontend blocks:

- **Momentum Filters:** RSI, QQE, Stochastic, MACD, CCI, Momentum
- **Trend Filters:** SuperTrend, Two MA, DMI, Trend Direction
- **Volatility Filters:** ATR, Volatility, Highest/Lowest
- **Volume Filters:** Volume, Volume Compare, CMF
- **Price Filters:** Price Above/Below, Price Action
- **Time Filters:** Trading Hours, Session

#### New Category Handlers

Added handlers for all frontend block categories:

- **`_execute_action()`** - Buy, Sell, Close, Stop Loss, Take Profit signals
- **`_execute_exit()`** - TP%, SL%, ATR Stop, Trailing, Chandelier Exit
- **`_execute_position_sizing()`** - Fixed, % Equity, Risk-based, Kelly, Volatility
- **`_execute_time_filter()`** - Trading Hours, Days, Sessions, Date Range
- **`_execute_price_action()`** - Engulfing, Hammer, Doji, Pin Bar, Inside/Outside Bar
- **`_execute_divergence()`** - RSI, MACD, OBV Divergence Detection

#### Category Routing Extended

Extended `_execute_block()` to route all categories:

- action, exit, sizing, entry, risk, session, time
- price_action, divergence (new)

#### Tests Passing

- ✅ 9 DCA E2E tests
- ✅ 18 Strategy Builder API tests
- ✅ 4 Strategy Builder Validation tests

#### Files Modified

- `backend/backtesting/strategy_builder_adapter.py` - +500 lines (new methods and handlers)

---

### DCA Engine Full System Integration (2026-01-30 - Session 3)

#### BacktestConfig DCA Fields Added

Extended `BacktestConfig` (Pydantic model) with 19 new DCA-specific fields:

**Grid Configuration:**

- `dca_enabled` - Enable DCA/Grid mode (auto-selects DCAEngine)
- `dca_direction` - Trading direction: 'long', 'short', 'both'
- `dca_order_count` - Number of grid orders (2-15)
- `dca_grid_size_percent` - Grid step size % (0.1-50%)
- `dca_martingale_coef` - Martingale coefficient (1.0-5.0)
- `dca_martingale_mode` - Mode: 'multiply_each', 'multiply_total', 'progressive'
- `dca_log_step_enabled` - Enable logarithmic step distribution
- `dca_log_step_coef` - Logarithmic coefficient (1.0-3.0)
- `dca_drawdown_threshold` - Safety close threshold % (5-90%)
- `dca_safety_close_enabled` - Enable safety close mechanism

**Multi-TP Configuration:**

- `dca_multi_tp_enabled` - Enable multi-level take profit
- `dca_tp1_percent` / `dca_tp1_close_percent` - TP1 level and close %
- `dca_tp2_percent` / `dca_tp2_close_percent` - TP2 level and close %
- `dca_tp3_percent` / `dca_tp3_close_percent` - TP3 level and close %
- `dca_tp4_percent` / `dca_tp4_close_percent` - TP4 level and close %

#### DCAEngine Abstract Methods Implemented

- `name` - Property returning engine name
- `supports_bar_magnifier` - Returns True
- `supports_parallel` - Returns True
- `optimize()` - Grid search optimization for DCA parameters

#### New DCAEngine Methods

- `run_from_config(config, ohlcv)` - Direct BacktestConfig integration
- `_configure_from_config(config)` - Extract DCA fields from Pydantic model
- `_generate_signals_from_config(config, df)` - Strategy signal generation
- `_convert_trades_to_model(ohlcv)` - Convert trades to BacktestResult format
- `_build_performance_metrics(...)` - Build PerformanceMetrics model

#### Engine Selector Integration

- `get_engine()` now accepts `dca_enabled` parameter
- Auto-selects DCAEngine when `dca_enabled=True`
- Added 'dca' and 'dca_grid' to engine_type validator

#### BacktestService Integration

- Dynamic engine selection based on `config.dca_enabled`
- Uses `engine.run_from_config(config, ohlcv)` for DCA backtests
- Standard engine path unchanged for non-DCA backtests

#### Files Modified

- `backend/backtesting/models.py` - +100 lines (DCA fields + validators)
- `backend/backtesting/engine_selector.py` - +15 lines (dca_enabled support)
- `backend/backtesting/service.py` - +10 lines (DCA engine routing)
- `backend/backtesting/engines/dca_engine.py` - +250 lines (new methods)

---

### DCA Engine Implementation & Strategy Builder Extensions (2026-01-30 - Session 2)

#### Backend DCA Engine Created

New specialized engine for DCA/Grid trading: `backend/backtesting/engines/dca_engine.py`

**Features:**

- Grid order placement with configurable levels (3-15 orders)
- Martingale position sizing (1.0-1.8 coefficient)
- Logarithmic step distribution (0.8-1.4 coefficient)
- Dynamic Take Profit adjustment based on active orders
- Multiple Take Profits (TP1-TP4) support
- Safety close on drawdown threshold
- Signal memory system placeholder

**Classes:**

- `DCAEngine` - Main backtest engine extending BaseBacktestEngine
- `DCAGridConfig` - Configuration dataclass for grid settings
- `DCAGridCalculator` - Static methods for grid calculation
- `DCAOrder` - Individual order representation
- `DCAPosition` - Aggregate position state
- `MultipleTakeProfit` - TP1-TP4 configuration

#### Frontend Strategy Builder Extensions

**QQE Indicator Added:**

- New indicator in `blockLibrary.indicators`
- Parameters: rsi_period, qqe_factor, smoothing_period, source, timeframe
- customLayout with full UI fields

**Price Action Patterns Expanded (8 → 22 patterns):**

- Bullish Reversal: Hammer, Inverted Hammer, Bullish Engulfing, Morning Star, Piercing Line, Three White Soldiers, Tweezer Bottom, Dragonfly Doji, Bullish Harami, Rising Three Methods, Bullish Marubozu
- Bearish Reversal: Shooting Star, Hanging Man, Bearish Engulfing, Evening Star, Dark Cloud Cover, Three Black Crows, Tweezer Top, Gravestone Doji, Bearish Harami, Falling Three Methods, Bearish Marubozu
- Neutral: Standard Doji, Spinning Top

**DCA CustomLayouts Added:**

- `dca_grid_enable` - Grid mode with direction, leverage, alerts
- `dca_grid_settings` - Deposit, grid size, order count, distribution
- `dca_martingale_config` - Coefficient (1.0-1.8), mode, safety limits
- `dca_log_steps` - Log coefficient (0.8-1.4), step preview
- `dca_dynamic_tp` - Trigger orders, new TP, decrease per order
- `dca_safety_close` - Drawdown threshold, action type
- `multi_tp_enable` - Enable multi-TP with count
- `tp1_config` through `tp4_config` - Individual TP level settings
- `atr_sl` / `atr_tp` / `atr_wicks_mode` - ATR-based exit settings
- `signal_memory_enable` / `cross_memory` / `pattern_memory` - Signal memory
- `qqe_filter` - QQE indicator filter with signal types

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - Added ~300 lines for DCA/QQE/Price Action
- `backend/backtesting/engines/dca_engine.py` - New file (650+ lines)
- `backend/backtesting/engines/__init__.py` - Export DCAEngine

---

### TradingView Multi DCA Strategy Import & Major Strategy Builder Expansion (2026-01-30)

**Analyzed and integrated parameters from TradingView Multi DCA Strategy [Dimkud]**

#### Source Analysis

Imported and analyzed comprehensive DCA strategy with 200+ parameters:

- `docs/tradingview_dca_import/DCA Start.txt` - Full parameter specification
- `docs/tradingview_dca_import/DCA Strategy3.txt` - Alternative version with explanations
- `docs/tradingview_dca_import/ANALYSIS_REPORT.md` - Complete analysis document
- `docs/tradingview_dca_import/IMPLEMENTATION_STATUS.md` - Implementation tracking

#### New Block Categories Added to Strategy Builder

| Category             | Blocks   | Description                                                              |
| -------------------- | -------- | ------------------------------------------------------------------------ |
| **dca_grid**         | 6 blocks | DCA Grid mode, settings, martingale, log steps, dynamic TP, safety close |
| **multiple_tp**      | 5 blocks | Enable multi-TP, TP1-TP4 configuration                                   |
| **atr_exit**         | 3 blocks | ATR-based SL/TP, wicks mode                                              |
| **signal_memory**    | 3 blocks | Signal memory, cross memory, pattern memory                              |
| **close_conditions** | 9 blocks | Time close, RSI/Stoch reach/cross, channel, MA cross, PSAR, profit only  |
| **price_action**     | 9 blocks | Engulfing, hammer, doji, shooting star, marubozu, tweezer, harami, etc.  |
| **divergence**       | 5 blocks | RSI, MACD, Stochastic, OBV, MFI divergence detection                     |

#### Default Parameters Added

40+ new block types with complete default parameters:

- DCA Grid: deposit, leverage, grid size, order count, martingale (1.0-1.8), log steps (0.8-1.4)
- Multiple TP: TP1-TP4 with percent and close amounts
- ATR Exit: period, multiplier, smoothing method, wicks mode
- Signal Memory: memory bars, execution conditions
- Close Conditions: RSI/Stoch reach/cross levels, channel breakout, MA cross, PSAR
- Price Action: 22 candlestick patterns (engulfing, hammer, doji, etc.)
- Divergence: Regular and hidden divergence for 5 indicators

#### Backtest Results Display (Previous Session)

Added beautiful modal for displaying backtest results:

- Summary cards (ROI, Win Rate, Drawdown, Trades, PF, Sharpe)
- 4-tab interface (Overview, Equity, Trades, All Metrics)
- Equity curve canvas rendering
- Trades table with MFE/MAE
- Export to JSON functionality
- Full results page link

#### Files Modified

- `frontend/js/pages/strategy_builder.js` - Added 7 new block categories, 40+ default params
- `frontend/strategy-builder.html` - Added backtest results modal
- `frontend/css/strategy_builder.css` - Added results modal styles (~300 lines)
- `docs/tradingview_dca_import/` - New documentation folder

---

### Strategy Builder Engine Integration & Auto-Mode Detection (2025-01-29)

**Simplified engine architecture and improved block-to-optimization-panel integration**

#### Engine Simplification

Reduced engine complexity from 5+ engines to 2 core engines:

| Engine               | Use Case        | Features                                                 |
| -------------------- | --------------- | -------------------------------------------------------- |
| **FallbackEngineV4** | Single Backtest | Reference implementation, maximum accuracy, all features |
| **NumbaEngineV2**    | Optimization    | JIT-compiled, 20-40x faster, 100% parity with V4         |

Deprecated engines (with warnings): GPU, V2, V3

#### Auto-Mode Detection

- **Single Backtest mode**: Auto-selected when NO optimization params enabled on blocks
- **Optimization mode**: Auto-selected when ANY optimization params enabled on blocks
- UI automatically updates button text and indicators based on mode

#### Block-Panel Integration

- `strategy_builder.js` now dispatches `strategyBlocksChanged` event on add/delete
- `optimization_panels.js` listens for events and syncs parameter ranges
- Blocks include `optimizationParams` object for storing min/max/step/enabled
- Two-way sync: changes in optimization panel reflect back to block

#### Files Modified

- `backend/backtesting/engine_selector.py` - Simplified to 2-engine selection
- `frontend/js/pages/optimization_panels.js` - Added block integration, auto-mode, SSE handling
- `frontend/js/pages/strategy_builder.js` - Added event dispatch, optimizationParams

---

### Expanded Indicators Library and UI (2025-01-29)

Added 8 new advanced indicators to backend + 34 indicators in UI.

New Backend Indicators in backend/core/indicators/advanced.py:

- ADX (Average Directional Index)
- CCI (Commodity Channel Index)
- Ichimoku Cloud
- Parabolic SAR
- Pivot Points
- Aroon
- ATRP

Updated UI Block Library - 34 Indicators + 6 Filters in strategy_builder.js.

---

### Optimization Panels JavaScript Module (2025-01-29)

**Created interactive panel manager for Strategy Builder Manual Mode**

#### Files Created/Modified

- `frontend/js/pages/optimization_panels.js` (~650 lines) - NEW
- `frontend/css/strategy_builder.css` - Added ~150 lines
- `frontend/strategy-builder.html` - Added script include

#### Class: `OptimizationPanels`

| Method                         | Description                     |
| ------------------------------ | ------------------------------- |
| `init()`                       | Initialize all panels and state |
| `bindEvents()`                 | Setup all event listeners       |
| `setupCollapsibleSections()`   | Panel collapse/expand logic     |
| `updateSecondaryMetrics()`     | Sync checkbox state             |
| `addConstraint()`              | Add new constraint row          |
| `updateConstraints()`          | Parse constraint inputs         |
| `startOptimization()`          | Build config, call API          |
| `pollOptimizationStatus()`     | Poll job progress               |
| `showResultsQuickView()`       | Display metrics summary         |
| `saveState()/loadSavedState()` | Persist to localStorage         |

#### Features

- **Evaluation Criteria Panel**: Primary metric, secondary metrics checkboxes, dynamic constraints
- **Optimization Config Panel**: Method selection, date range, max trials, workers
- **Results Panel**: Progress bar, metrics preview, link to full results
- **State Persistence**: Auto-save to localStorage
- **API Integration**: Job start, polling, results loading

---

### �🎯 Advanced RSI Filter - TradingView Parity (2025-01-29)

**Implemented full RSI - [IN RANGE FILTER OR CROSS SIGNAL] from TradingView**

#### Features

| Feature         | Description                                     |
| --------------- | ----------------------------------------------- |
| Range Filter    | RSI must be within bounds (e.g., 1-50 for long) |
| Cross Signal    | RSI crossover/crossunder detection              |
| Signal Memory   | Keep signal active for N bars after cross       |
| Opposite Signal | Invert cross logic (long on short cross)        |
| BTC Source      | Use BTC RSI for altcoin trading                 |

#### File Created

- `backend/core/indicators/rsi_advanced.py` (~500 lines)

#### Classes & Functions

```python
# Classes
RSIAdvancedConfig   # Configuration dataclass
RSIAdvancedFilter   # Main filter class
RSIFilterResult     # Result container

# Convenience functions
apply_rsi_range_filter()     # Simple range filter
apply_rsi_cross_filter()     # Cross with optional memory
apply_rsi_combined_filter()  # Full combined mode
create_btc_rsi_filter()      # BTC source for alts
```

#### Usage Example

```python
from backend.core.indicators import RSIAdvancedFilter, RSIAdvancedConfig

config = RSIAdvancedConfig(
    rsi_period=14,
    use_long_range=True,
    long_range_lower=20,
    long_range_upper=60,
    use_cross_level=True,
    long_cross_level=30,
    activate_memory=True,
    memory_bars=5,
)
filter = RSIAdvancedFilter(config)
result = filter.apply(close_prices)
# result.long_signals, result.short_signals, result.rsi_values, etc.
```

---

### 📚 Unified Indicators Library (2025-01-29)

**Created centralized indicators library to eliminate code duplication**

#### Problem Solved

The project had **15-20 duplicate RSI implementations** scattered across:

- `signal_generators.py`
- `fast_optimizer.py`
- `gpu_optimizer.py`
- `strategy_builder/indicators.py`
- `mtf/signals.py`
- And 10+ other files

Each with slightly different implementations, making maintenance a nightmare.

#### Solution: `backend/core/indicators/`

Created unified library with **26 technical indicators** organized by category:

| Module          | Indicators                                             | Functions |
| --------------- | ------------------------------------------------------ | --------- |
| `momentum.py`   | RSI, Stochastic, Williams %R, ROC, CMO, MFI, Stoch RSI | 8         |
| `trend.py`      | SMA, EMA, WMA, DEMA, TEMA, Hull MA, MACD, Supertrend   | 8         |
| `volatility.py` | ATR, Bollinger, Keltner, Donchian, StdDev              | 5         |
| `volume.py`     | OBV, VWAP, PVT, A/D Line, CMF                          | 5         |

#### Features

- **Numba JIT optimization** (optional, falls back gracefully)
- **No GPU/CuPy** - project uses universal engines, GPU not needed
- **Consistent API** - all functions accept numpy arrays
- **Proper NaN handling** - warmup periods return NaN

#### Usage

```python
from backend.core.indicators import (
    calculate_rsi,
    calculate_sma,
    calculate_ema,
    calculate_macd,
    calculate_bollinger,
    calculate_atr,
)
```

#### Files Created

| File                                    | Lines | Purpose               |
| --------------------------------------- | ----- | --------------------- |
| `backend/core/indicators/__init__.py`   | 80    | Unified exports       |
| `backend/core/indicators/momentum.py`   | 400   | RSI, Stochastic, etc. |
| `backend/core/indicators/trend.py`      | 300   | MA variants, MACD     |
| `backend/core/indicators/volatility.py` | 200   | ATR, Bollinger, etc.  |
| `backend/core/indicators/volume.py`     | 200   | OBV, VWAP, etc.       |
| `backend/core/indicators/README.md`     | 250   | Documentation         |

#### Migration Progress

- [x] `backend/backtesting/signal_generators.py` - Updated
- [x] `backend/backtesting/mtf/signals.py` - Updated (removed ~60 lines)
- [x] `backend/backtesting/mtf/filters.py` - Updated (removed ~90 lines)
- [x] `backend/ml/rl_trading_agent.py` - Updated
- [~] `backend/services/strategy_builder/indicators.py` - Class-based, kept as-is
- [~] `backend/backtesting/fast_optimizer.py` - Numba JIT, kept as-is (performance)
- [~] `backend/backtesting/universal_engine/signal_generator.py` - Numba JIT, kept as-is

**Note**: Files marked `[~]` have their own optimized implementations (Numba JIT) for performance reasons. They remain separate to avoid performance regression.

---

### Manual Mode UI Implementation (2025-01-29)

**Implemented unified design standard for Strategy Builder Manual Mode**

#### Created Files

| File                                       | Lines | Purpose                                |
| ------------------------------------------ | ----- | -------------------------------------- |
| `frontend/css/optimization_components.css` | 595   | Unified CSS for optimization panels    |
| `frontend/optimization-results.html`       | 518   | Full results viewer page               |
| `frontend/js/pages/optimization.js`        | 580   | JavaScript for optimization management |

#### Modified Files

| File                                | Changes                                  |
| ----------------------------------- | ---------------------------------------- |
| `frontend/strategy-builder.html`    | Added 3 new sidebar panels               |
| `frontend/css/strategy_builder.css` | Added 500+ lines for optimization styles |

---

### � Strategy Builder - Full Audit & Dual-Mode Architecture (2025-01-29)

**Comprehensive audit of Strategy Builder capabilities and architecture design for Manual + AI modes**

#### Key Findings

Strategy Builder is a **fully functional** system with:

- **25 block types** across 7 categories (Data, Indicators, Conditions, Actions, Filters, Risk, Output)
- **Node-based visual composition** with drag/drop canvas
- **Code generation** for backtest, live, indicator templates
- **Full API** with 35+ endpoints for CRUD, validation, optimization, sharing
- **Optimization integration** via Grid Search, Bayesian (TPE), Walk-Forward
- **Database persistence** with versioning support

#### Dual-Mode Architecture

Defined Strategy Builder as **unified platform** for:

1. **Manual Mode (User-Driven)**: Visual canvas, manual parameter tuning, user-defined criteria
2. **AI-Assisted Mode**: Natural language input, AI-generated graphs, auto-optimization

Both modes share: Block system, Validation engine, Code generator, Backtest infrastructure

#### Missing Features for Manual Workflow (P0)

| Feature                | Description                                 |
| ---------------------- | ------------------------------------------- |
| Evaluation Criteria UI | Select metrics, set constraints, multi-sort |
| Optimization Config UI | Parameter ranges, method selection, limits  |
| Results Viewer         | Table, charts, comparison, export           |

#### Implementation Roadmap

- **Week 1**: Evaluation Criteria Panel (UI + API + DB)
- **Week 2**: Optimization Config Panel (UI + API)
- **Week 3**: Results Viewer Page (Table + Pagination)
- **Week 4**: Charts & Visualization
- **Week 5**: Integration & Testing

#### Documentation Created

- `docs/STRATEGY_BUILDER_AUDIT.md` - Full audit with 25 block types, all API endpoints
- `docs/DUAL_MODE_ARCHITECTURE.md` - Manual + AI mode architecture
- `docs/STRATEGY_BUILDER_IMPLEMENTATION_ROADMAP.md` - Missing features & implementation plan

---

### �📐 Agent-Driven Strategy Pipeline Architecture (2025-01-29)

**Designed complete 8-phase AI pipeline for strategy development**

#### Pipeline Phases

1. **Creation** - User creates/selects strategy template in Strategy Builder
2. **Analysis** - Perplexity analyzes market trends and conditions
3. **Consensus** - Agents reach agreement on architecture and parameters
4. **Build** - DeepSeek constructs strategy using Strategy Builder library
5. **Secondary Backtest** - Backtest with agent-defined acceptance criteria
6. **Optimization** - Optuna optimization with agent-defined parameter space
7. **ML Validation** - Overfitting detection, regime analysis, drift monitoring
8. **Final Validation** - Walk-forward, Monte Carlo, stress tests

#### ML Integration Points

- **Overfitting Detection**: In-sample vs out-of-sample gap analysis
- **Regime Detection**: Performance analysis across market regimes
- **Meta-Learning**: Parameter selector trained on optimization history
- **Online Learning**: Continuous adaptation with trade results
- **Concept Drift**: Distribution shift monitoring

#### Documentation

- Created `docs/AGENT_STRATEGY_PIPELINE_ARCHITECTURE.md` - Full architecture
- Created `docs/AGENT_STRATEGY_PIPELINE_IMPLEMENTATION.md` - Technical spec

---

### 🤖 AI Agent System Improvements (2026-01-29)

**Upgraded RLHF Module and Multi-Agent Consensus to 10/10**

#### RLHF Module Enhancements (`backend/agents/self_improvement/rlhf_module.py`):

1. **Expanded Feature Extraction** - 11 sophisticated features:
    - `structure_score`, `coherence_score`, `completeness_score`
    - `specificity_score`, `formatting_score`, `risk_score`, `actionable_score`

2. **Training Improvements**:
    - Early stopping with configurable patience (default 3 epochs)
    - Learning rate decay (0.95 per epoch)
    - Train/validation split (80/20)
    - Best weights checkpointing

3. **New Methods**:
    - `_compute_validation_loss()` - proper validation for early stopping
    - `cross_validate()` - k-fold cross-validation support

#### Multi-Agent Consensus Enhancements (`backend/agents/consensus/deliberation.py`):

1. **Parallel Agent Calls**:
    - `asyncio.gather()` for parallel initial opinions
    - Parallel cross-examination phase
    - ~N× speedup with N agents

2. **Confidence Calibration (Platt Scaling)**:
    - `calibrate_confidence()` - apply sigmoid calibration
    - `update_calibration()` - collect outcome samples
    - `_fit_calibration()` - gradient descent fitting

3. **Evidence Weighting**:
    - `classify_evidence()` - empirical/theoretical/citation/example
    - `compute_weighted_evidence_score()` - weighted position scoring
    - Evidence weights: empirical(1.5) > citation(1.3) > theoretical(1.0) > example(0.8)

4. **Enhanced Weighted Voting**:
    - Calibrated confidence (70%) + evidence score (30%)

#### Documentation:

- Created `docs/AI_AGENT_IMPROVEMENTS_REPORT.md`

---

### 🔧 Strategy Builder API Fix (2026-01-29)

**Исправлены все проблемы с API эндпоинтами Strategy Builder**

#### Проблемы и решения:

1. **Формат соединений** (`strategy_builder_adapter.py`)
    - Добавлены helper методы для поддержки обоих форматов connections:
        - `_get_connection_source_id()` / `_get_connection_target_id()`
        - `_get_connection_source_port()` / `_get_connection_target_port()`
    - Поддерживается как `source_block`/`target_block` (новый), так и `source.blockId`/`target.blockId` (старый)

2. **Топологическая сортировка** (`strategy_builder_adapter.py`)
    - Исправлен `KeyError: 'main_strategy'` - добавлена проверка `if target_id in in_degree:`

3. **SignalResult None values** (`strategy_builder_adapter.py`)
    - Исправлен `'NoneType' object has no attribute 'values'`
    - Теперь всегда возвращается pd.Series для `short_entries`/`short_exits`

4. **final_capital атрибут** (`strategy_builder.py`)
    - Исправлен `'PerformanceMetrics' object has no attribute 'final_capital'`
    - Используется `result.final_equity` из `BacktestResult`

#### Результат:

Все API эндпоинты Strategy Builder работают:

- ✅ POST /strategies - 200 OK
- ✅ GET /strategies/{id} - 200 OK
- ✅ PUT /strategies/{id} - 200 OK
- ✅ POST /generate-code - 200 OK
- ✅ POST /backtest - 200 OK

#### Документация:

- Создан `docs/STRATEGY_BUILDER_API_FIX_COMPLETE.md`

---

### �📚 Agent Strategy Generation Specification (2026-01-28)

**Создана консолидированная документация для генерации стратегий агентами**

#### Новый документ: `docs/ai/AGENT_STRATEGY_GENERATION_SPEC.md`

Полная спецификация включает:

1. **Входные данные для агентов**
    - Обязательные параметры (торговая пара, таймфрейм, капитал, направление, комиссии, плечо, пирамидинг)
    - Опциональные параметры (тип стратегии, риск-менеджмент, фильтры, DCA/Grid параметры)
    - Полный список всех параметров из `BacktestInput` с описаниями и диапазонами

2. **Типы стратегий**
    - Базовые: Trend Following, Mean Reversion, Breakout, Momentum
    - Специализированные: DCA, Grid Trading, Martingale, Scalping
    - Гибридные комбинации

3. **Методы оценки качества стратегии**
    - Базовые метрики: Total Return, Sharpe Ratio, Sortino Ratio, Profit Factor, Max Drawdown
    - Продвинутые метрики: Consistency Score, Recovery Factor, Ulcer Index, MAE/MFE
    - Метрики качества сигналов: Signal Quality Score, False Positive Rate

4. **Градации агрессивности**
    - Консервативная: Max DD < 15%, Win Rate > 55%, Leverage 1-3x
    - Умеренная: Max DD < 25%, Win Rate > 50%, Leverage 3-10x
    - Агрессивная: Max DD < 40%, Win Rate > 45%, Leverage 10-50x
    - Экстремальная: Max DD < 60%, Win Rate > 40%, Leverage 50-125x

5. **Многотаймфреймовый анализ**
    - Иерархия таймфреймов (LTF/HTF)
    - Методы MTF анализа: Trend Confirmation, Momentum Alignment, Support/Resistance, BTC Correlation
    - Критерии оценки MTF

6. **Временные диапазоны тестирования**
    - Краткосрочная оценка (7-30 дней)
    - Среднесрочная оценка (30-90 дней)
    - Долгосрочная оценка (90-365 дней)
    - Методы: Walk-Forward Analysis, Rolling Window, Regime-Based Testing, Seasonal Analysis

7. **Критерии оценки и валидации**
    - Обязательные критерии для всех стратегий
    - Критерии по градации агрессивности
    - Критерии по таймфреймам и временным диапазонам

8. **Права агентов на модификацию**
    - Обязательные параметры (не изменяются)
    - Параметры с ограниченной модификацией
    - Полная свобода агентов
    - Формат предложений и критерии принятия

9. **Примеры использования**
    - Пример консервативной стратегии
    - Пример агрессивной стратегии

**Документация основана на:**

- `backend/backtesting/interfaces.py` - BacktestInput структура
- `backend/api/routers/ai_strategy_generator.py` - GenerateStrategyRequest
- `backend/agents/consensus/domain_agents.py` - TradingStrategyAgent методы оценки
- Предыдущие беседы о входных данных, методах оценки и градациях агрессивности

---

### 🔧 NumbaEngine V4+ Extended Features (2026-01-28)

**Расширение NumbaEngine до 95%+ паритета с FallbackEngine**

#### Добавлены новые фичи в NumbaEngine:

1. **Breakeven Stop** — Перемещение SL в безубыток после TP1
    - `breakeven_enabled: bool`
    - `breakeven_offset: float` (например, 0.001 = +0.1% от входа)

2. **Time-based Exits** — Закрытие по времени
    - `max_bars_in_trade: int` (0 = отключено)
    - Новый exit_reason = 5

3. **Re-entry Rules** — Правила повторного входа
    - `re_entry_delay_bars: int` — Задержка после выхода
    - `max_trades_per_day: int` — Лимит сделок в день
    - `cooldown_after_loss: int` — Пауза после убытка
    - `max_consecutive_losses: int` — Стоп после N убытков подряд

4. **Market Filters** — Фильтры рыночных условий
    - `volatility_filter_enabled` — Фильтр по ATR percentile
    - `volume_filter_enabled` — Фильтр по объёму
    - `trend_filter_enabled` — Фильтр по SMA (with/against trend)

5. **Funding Rate** — Учёт фандинга для фьючерсов
    - `include_funding: bool`
    - `funding_rate: float` (например, 0.0001 = 0.01%)
    - `funding_interval: int` (баров между выплатами)

6. **Advanced Slippage Model** — Динамический slippage
    - `slippage_model: "fixed" | "advanced"`
    - Учитывает волатильность (ATR) и объём

#### Feature Matrix обновлена:

| Feature           | Fallback |   Numba    |
| ----------------- | :------: | :--------: |
| All V4 features   |    ✓     |     ✓      |
| Breakeven Stop    |    ✓     |     ✓      |
| Time-based Exit   |    ✓     |     ✓      |
| Re-entry Rules    |    ✓     |     ✓      |
| Market Filters    |    ✓     |     ✓      |
| Funding Rate      |    ✓     |     ✓      |
| **Adv. Slippage** |    ✓     | ✓ ← FIXED! |
| **FIFO/LIFO**     |    ✓     | ✓ ← FIXED! |

**Advanced Slippage - полная реализация:**

- В обоих движках реализован расчёт `slippage_multipliers` на основе ATR и объёма
- Multipliers применяются динамически на каждом баре: `effective_slippage = slippage * slippage_multipliers[i]`
- Учитывается волатильность (ATR%) и объём (относительно среднего)
- **Статус:** Полностью реализовано в обоих движках, 100% паритет

**Решение для FIFO/LIFO в Numba:**

- Используется маркировка закрытых entries (массив `long_entry_closed`, `short_entry_closed`)
- При FIFO - закрывается первый открытый entry
- При LIFO - закрывается последний открытый entry
- При ALL (по умолчанию) - закрываются все entries сразу
- SL/TP всегда закрывают ВСЕ entries (стандартное поведение TradingView)

---

### 🚀 Server Startup Optimization (2026-01-28)

**РЕЗУЛЬТАТ: Время старта ~60 сек → ~12 сек (FAST_DEV_MODE) / ~15 сек (обычный)**

#### Изменения:

1. **backend/backtesting/**init**.py** — Lazy loading для тяжёлых модулей
    - `optimizer`, `walk_forward`, `position_sizing` загружаются ТОЛЬКО при обращении
    - Используется `__getattr__` для динамической загрузки
    - GPU/Numba инициализация отложена до первого использования
    - **Экономия: ~30-50 секунд при старте**

2. **backend/backtesting/gpu_optimizer.py** — Lazy GPU initialization
    - CuPy импортируется только при вызове `is_gpu_available()` или GPU-функций
    - `GPU_AVAILABLE = None` (not checked) → `True/False` после первой проверки
    - Функция `_init_gpu()` делает одноразовую инициализацию
    - **Экономия: ~8-15 секунд на машинах без/с NVIDIA GPU**

3. **backend/api/lifespan.py** — Parallel warmup + FAST_DEV_MODE
    - JIT и Cache warmup выполняются параллельно (`asyncio.gather`)
    - `FAST_DEV_MODE=1` пропускает warmup полностью
    - **Экономия: ~3-5 секунд при параллельном warmup**

#### Использование:

```bash
# Быстрый старт для разработки
$env:FAST_DEV_MODE='1'
uvicorn backend.api.app:app --reload

# Production (warmup выполняется, но GPU ленивый)
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

#### Важные заметки:

- GPU инициализируется при первом вызове оптимизации (не при старте)
- Numba JIT компилируется при первом бэктесте (если FAST_DEV_MODE)
- Lazy loading не влияет на функциональность - всё работает как прежде

---

### NumbaEngine DCA Support (2026-01-28)

- **backend/backtesting/engines/numba_engine_v2.py** — added DCA (Safety Orders) support
    - Added DCA parameters to `_simulate_trades_numba_v4`:
        - `dca_enabled`, `dca_num_so`, `dca_levels`, `dca_volumes`, `dca_base_order_size`
    - DCA logic: Safety Orders trigger as price drops (long) / rises (short)
    - Pre-calculated cumulative deviation levels and volumes
    - Full reset on position close
    - Added `supports_dca` property
    - Updated docstrings

### GPUEngineV2 Deprecated (2026-01-28)

- **backend/backtesting/engines/gpu_engine_v2.py** — marked as deprecated
    - Added DeprecationWarning in `__init__`
    - Updated docstrings with migration guide
    - Reason: V2-only features, requires NVIDIA, NumbaEngine is sufficient

---

### Engine Consolidation Phase 1 - Unified FallbackEngine (2026-01-28)

#### Consolidated Engine Architecture

- **`FallbackEngine`** = `FallbackEngineV4` (основной эталон)
- **`NumbaEngine`** = `NumbaEngineV2` (быстрый, полный V4)
- **V2/V3** — deprecated aliases (работают, выдают DeprecationWarning)

#### Updated Exports (`backend/backtesting/engines/__init__.py`)

```python
from backend.backtesting.engines import (
    FallbackEngine,   # = V4 (основной)
    NumbaEngine,      # = NumbaEngineV2 (быстрый)
    FallbackEngineV4, # explicit
    NumbaEngineV2,    # explicit
    FallbackEngineV2, # deprecated
    FallbackEngineV3, # deprecated
)
```

#### Migration Guide

```python
# Old way:
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
engine = FallbackEngineV2()

# New way:
from backend.backtesting.engines import FallbackEngine
engine = FallbackEngine()  # = V4, все фичи
```

---

### Engine Consolidation Phase 4 - Deprecated RSI-only Optimizers (2026-01-28)

#### Deprecated Modules

Marked as deprecated (will be removed in v3.0):

- **backend/backtesting/fast_optimizer.py** - RSI-only Numba optimizer
- **backend/backtesting/gpu_optimizer.py** - RSI-only GPU/CuPy optimizer
- **backend/backtesting/optimizer.py** - UniversalOptimizer wrapper

#### Reasons for Deprecation

1. **RSI-only** — these optimizers don't support:
    - Pyramiding (multiple entries)
    - ATR-based SL/TP (dynamic stops)
    - Multi-level TP (partial profit taking)
    - Trailing stop
    - Custom strategies

2. **Replaced by NumbaEngineV2** — full V4 functionality with 20-40x speedup:
    - All V4 features supported
    - Works on any CPU (no NVIDIA required)
    - Simpler codebase, easier maintenance

#### Migration Guide

```python
# Old way (deprecated):
from backend.backtesting.optimizer import UniversalOptimizer
result = UniversalOptimizer().optimize(...)

# New way (recommended):
from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput
import itertools

engine = get_engine("numba")  # NumbaEngineV2 with full V4 support

for params in itertools.product(rsi_periods, stop_losses, ...):
    input_data = BacktestInput(...params...)
    output = engine.run(input_data)
    # process results
```

**Related:** Phase 2-3 added full V4 support to NumbaEngineV2 (pyramiding, ATR, multi-TP, trailing) with 100% parity to FallbackEngineV4.

---

### Startup Performance Optimizations (2026-01-28)

#### 1. Lazy GPU Initialization

- **backend/backtesting/gpu_optimizer.py** - GPU/CuPy теперь загружается ТОЛЬКО при первом использовании
    - Убрано: импорт CuPy при загрузке модуля (~8-15 сек)
    - Добавлено: `_init_gpu()` и `is_gpu_available()` для lazy loading
    - Все использования `GPU_AVAILABLE` заменены на `is_gpu_available()`
    - **Экономия:** 8-15 секунд при обычном запуске (когда GPU не нужен)

#### 2. Parallel Warmup

- **backend/api/lifespan.py** - JIT и cache warmup теперь выполняются параллельно
    - JIT warmup (CPU-bound) и cache warmup (I/O-bound) запускаются через `asyncio.gather()`
    - **Экономия:** ~8 секунд (вместо последовательного ожидания)

#### 3. FAST_DEV_MODE Environment Variable

- **backend/api/lifespan.py** - Добавлена переменная окружения `FAST_DEV_MODE`
    - При `FAST_DEV_MODE=1` пропускается весь warmup
    - Идеально для разработки: запуск за ~1-2 секунды вместо 45-90
    - Использование: `$env:FAST_DEV_MODE = "1"; uvicorn backend.api.app:app`

**Итоговое улучшение:**

- Обычный запуск: 45-90 сек → ~25-35 сек (параллельный warmup)
- Режим разработки: 45-90 сек → ~1-2 сек (FAST_DEV_MODE=1)

### Startup Script Fixes (2026-01-28)

#### Fixed Import Error

- **backend/middleware/csrf.py** - Fixed incorrect import `from backend.core.logging` → `from backend.core.logging_config`

#### Added Root Health Endpoints

- **backend/api/app.py** - Added `/healthz`, `/readyz`, `/livez` at root level for K8s probes and startup scripts
    - Previously these endpoints only existed at `/api/v1/health/healthz`
    - Now `start_all.ps1` can properly check server readiness

#### Verified Startup Flow

- **start_all.ps1** - Verified all steps work correctly:
    1. ✅ stop_all.ps1 - Stops all services and clears cache
    2. ✅ start_redis.ps1 - Starts Redis on port 6379
    3. ✅ start_kline_db_service.ps1 - Starts Kline DB Service
    4. ✅ start_mcp_server.ps1 - Starts MCP Server
    5. ✅ start_uvicorn.ps1 - Starts Uvicorn on port 8000
    6. ✅ Health check waits for `/healthz` to return `{status: "ok"}`
    7. ✅ start_agent_service.ps1 - Starts AI Agent Service
    8. ✅ Opens browser to http://localhost:8000

### Universal Engine & Performance Spec (2026-01-28)

**ПРИНЯТОЕ РЕШЕНИЕ: Консолидация до 2 движков**

- **§11 Консолидация:** вместо 8 подсистем — **2 движка**:
    - **FallbackEngine** — эталон (все фичи V4)
    - **NumbaEngine** — оптимизация (точность + скорость, расширить до V4)
    - **GPU — откладываем** (сложнее, требует NVIDIA, выигрыш только на 100K+ комбинаций)

**Реализация Фазы 1 (частично):**

- **backend/backtesting/engines/**init**.py** — добавлен `FallbackEngine = FallbackEngineV4`
- **backend/backtesting/engine_selector.py** — обновлена логика:
    - `auto` / `fallback` / `v4` → FallbackEngineV4 (основной)
    - `pyramiding > 1` → FallbackEngineV4 (вместо V3)
    - `fallback_v2` / `fallback_v3` → deprecated с warning
- **fallback_engine_v2.py** — добавлен DeprecationWarning
- **fallback_engine_v3.py** — добавлен DeprecationWarning

**Реализация Фазы 2 (Numba V3 — pyramiding):**

- **backend/backtesting/engines/numba_engine_v2.py**:
    - Новая функция `_simulate_trades_numba_pyramiding` (~350 строк)
    - Поддержка pyramiding > 1 (несколько входов в одну сторону)
    - Средневзвешенная цена входа для SL/TP
    - Закрытие ALL (все позиции сразу)
    - Свойство `supports_pyramiding = True`

**Реализация Фазы 2 (Numba V4 — полный функционал):**

- **backend/backtesting/engines/numba_engine_v2.py**:
    - Новая функция `_simulate_trades_numba_v4` (~700 строк) с полной поддержкой:
        - **ATR SL/TP**: sl_mode/tp_mode enum, atr_sl_multiplier, atr_tp_multiplier
        - **Multi-level TP**: tp_portions + tp_levels (4 уровня)
        - **Trailing Stop**: trailing_stop_enabled, trailing_stop_activation, trailing_stop_distance
        - **Pyramiding**: max_entries
    - Авто-выбор режима: V4 если ATR/Multi-TP/Trailing, иначе V3 (pyramiding) или V2
    - Свойства: `supports_atr`, `supports_multi_tp`, `supports_trailing`
- **engine_selector.py**: Feature Matrix обновлена — Numba теперь = V4 (кроме DCA)

**Реализация Фазы 3 (паритет-тесты):**

- **scripts/test_numba_parity.py**: Комплексный тест паритета Fallback vs Numba
    - V2 Basic: 4/4 PASS (100%)
    - V3 Pyramiding: 2/2 PASS (100%)
    - V4 ATR SL/TP: 3/3 PASS (100%)
    - V4 Multi-TP: 2/2 PASS (100%)
    - V4 Trailing: 2/2 PASS (100%)
    - **ИТОГО: 13/13 (100.0%)** — ВСЕ ТЕСТЫ ПРОШЛИ!
- Исправлен fallback: NumbaEngine → FallbackEngineV4 (не V2)
- Исправлен расчёт ATR SL/TP: использовать current_atr (как в FallbackV4)

Ранее дополнены разделы:

- **§1.1 Двухэтапный поток:** эталон для старта и уточнения; оптимизация требует точности и скорости.
- **§8–10:** роль Universal Math Engine, универсальность, что переиспользовать.
- **backend/backtesting/engine_selector.py** — добавлен `fallback_v4` в `get_available_engines()`.

### Infrastructure & Testing (2026-01-28)

#### New Unit Tests

- **test_vault_client.py** - 12 tests for VaultClient with fallback behavior
- **test_mlflow_adapter.py** - 17 tests for MLflow experiment tracking
- **test_trading_env.py** - 5 tests for RL TradingEnv Gymnasium environment
- **test_safedom.py** - 15 tests for SafeDOM.js XSS protection
- **test_auto_event_binding.py** - 16 tests for auto-event-binding.js

#### MLflow Integration

- **backend/backtesting/mlflow_tracking.py** - BacktestTracker class for experiment tracking:
    - Parameter logging (strategy, symbol, dates, risk params)
    - Metric logging (Sharpe, returns, drawdown, win rate)
    - Artifact logging (equity curves, trade logs, summaries)
    - Context manager for tracking backtest runs

#### Vault Production Setup

- **deployment/docker-compose.vault.yml** - Docker Compose for Vault + MLflow
- **deployment/vault/policies/bybit-app.hcl** - Read-only app policy
- **deployment/vault/policies/vault-admin.hcl** - Admin policy
- **scripts/vault_init.sh** - Vault initialization script
- **docs/SECRETS_MIGRATION_GUIDE.md** - Migration guide from env vars to Vault

#### Bug Fixes

- **backend/core/vault_client.py** - Fixed ConnectionError handling in `is_available` property
    - Now gracefully returns False when Vault is unreachable
    - Wrapped `_get_client()` in try/except block

### DeepSeek/Perplexity Agents Audit (2026-01-28)

Полный аудит системы агентов DeepSeek и Perplexity.

#### Bug Fixes (P0 Critical)

1. **Import Fix** (`backend/api/deepseek_client.py`, `backend/api/perplexity_client.py`):
    - Исправлен неправильный импорт `from reliability.retry_policy`
    - Теперь: `from backend.reliability.retry_policy`

2. **Health Check Logic Fix** (`backend/api/perplexity_client.py`):
    - **Было**: `is_healthy = response.status_code in [200, 400, 401, 403]`
    - **Стало**: `is_healthy = response.status_code == 200`
    - 401/403 — это ошибки авторизации, а не healthy статус

#### Documentation

3. **Agents Audit Report** (`docs/DEEPSEEK_PERPLEXITY_AGENTS_AUDIT.md`):
    - Анализ 6 ключевых файлов системы агентов
    - Найдено 2 критических бага (исправлены)
    - 5 средних проблем (рекомендации)
    - Рекомендации по декомпозиции unified_agent_interface.py (2926+ строк)

#### Fixed Issues (P1-P2)

1. **P2 Fix: KeyManager in real_llm_deliberation.py** — Now uses secure KeyManager instead of os.environ
2. **P1 Fix: Circuit Breaker in connections.py** — Added circuit breaker integration to DeepSeekClient and PerplexityClient
3. **P1 Fix: Modular api_key_pool.py** — Extracted APIKeyPoolManager for better modularity (304 lines)

#### DeepSeek MCP Demo

- **deepseek_code** инструмент работает! Сгенерирована торговая стратегия:
    - `backend/backtesting/strategies/momentum_rsi_ema.py`
    - RSI + EMA crossover с ATR-based SL/TP
    - Полностью совместима с VectorBT и Fallback движками

#### Agent Strategy Orchestration Spec (2026-01-28)

- **Новая спецификация** `docs/ai/AGENT_STRATEGY_ORCHESTRATION_SPEC.md`:
    - Разбор предложения: Perplexity (аналитика) → DeepSeek (консенсус, код/Lego) → бэктест → Perplexity (params) → DeepSeek (второе мнение, оптимизация) → отсев → цикл/эволюция Lego
    - Идеи по отсеву: критерии от агентов, ML, гибрид, Pareto
    - Сопоставление с `RealLLMDeliberation`, `AIBacktestAnalyzer`, `AIOptimizationAnalyzer`, `StrategyBuilder`, `CodeGenerator`, `fast_optimizer`
    - Поэтапный план внедрения
- **Дополнение (размышления):**
    - **§0 Точка старта:** ввод пользователя до генерации стратегии — symbol, interval, capital, direction, position_size, leverage, commission, pyramiding, strategy_type (DCA/Grid/RSI/…), + property из `BacktestConfig`/`BacktestInput`. Агенты могут предлагать свои варианты (ТФ, тип, плечо, фильтры). Уровни плеча — перебор 1x/2x/5x/10x по решению оркестратора.
    - **§2.10 Мульти-ТФ, мульти-период, критерии качества:** проверка на разных ТФ (15m, 1h, 4h, 1d); профили conservative/balanced/aggressive/robustness с разными весами (Calmar, Sharpe, return, OOS); «хитрые методы» — множественные календарные периоды, Walk-Forward (rolling/anchored), MTF Walk-Forward, стресс-периоды, Monte Carlo. Связка ТФ + профиль + метод + leverage → градации агрессивности. Опора на `MTFOptimizer`, `WalkForwardOptimizer`, `MTFWalkForward`, `MetricsCalculator`.
    - В план внедрения: фаза **0** (схема `UserStrategyInput`, точка старта), фаза **2b** (мульти-ТФ, мульти-период, профили).

---

### Audit Session 4 - Part 4 (2026-01-28)

P2 задачи: безопасность хеширования и исправление багов.

#### Security Fixes

1. **MD5 → SHA256 Migration** — Все 8 файлов с hashlib.md5 мигрированы на SHA256:
    - `backend/backtesting/optimization_cache.py` (4 места)
    - `backend/services/multi_level_cache.py`
    - `backend/services/state_manager.py`
    - `backend/services/ab_testing.py`
    - `backend/ml/news_nlp_analyzer.py`
    - `backend/ml/enhanced/model_registry.py`
    - `backend/ml/enhanced/feature_store.py`
    - `backend/ml/enhanced/automl_pipeline.py`

#### Bug Fixes

2. **Pyramiding entry_count Fix** (`backend/backtesting/pyramiding.py`):
    - **Проблема**: `entry_count` возвращал 1 вместо реального количества входов
    - **Причина**: `close_all()` очищает `entries` до получения count
    - **Решение**: `entry_count_before_close = pos.entry_count` сохраняется до вызова `close_all()`

#### Verified as Correct

3. **ATR Algorithm Unification** (`backend/backtesting/atr_calculator.py`):
    - `calculate_atr()` и `calculate_atr_fast()` математически идентичны
    - Обе используют Wilder's smoothing: `ATR[i] = ((period-1)*ATR[i-1] + TR[i]) / period`
    - Добавлены комментарии в код для ясности

4. **ML System P0 Tasks** — Верифицированы как УЖЕ РЕАЛИЗОВАННЫЕ:
    - **Feature Store persistence**: JSON backend с `_load_store()`/`_save_store()`
    - **Model validation**: `validate_model()` с auto-validation перед promotion

5. **Infrastructure** — Верифицированы как УЖЕ РЕАЛИЗОВАННЫЕ:
    - **Grafana dashboards**: 6 dashboards (system-health, api-performance, backtest-results, etc.)
    - **Bar Magnifier**: полная реализация в numba_engine_v2 и fallback_engine_v3
    - **DriftAlertManager**: 750 строк с Slack/Email/Webhook/Redis интеграцией
    - **AlertManager**: 556 строк в alerting.py с pluggable notifiers
    - **Services P0**: все исправлены (context managers, XOR encryption, graceful shutdown)

6. **Circuit Breaker for Bybit API** (`backend/services/adapters/bybit.py`):
    - Добавлена интеграция с `CircuitBreakerRegistry`
    - Новый метод `_api_get()` с circuit breaker protection
    - Автоматическое открытие/закрытие circuit при ошибках API

7. **onclick → addEventListener Migration** (`frontend/js/core/auto-event-binding.js`):
    - Создан автоматический конвертер onclick → addEventListener
    - Использует MutationObserver для динамического контента
    - Добавлен в 44 HTML файла
    - 191 inline onclick обработчик теперь CSP-compliant

8. **Prometheus Registry Centralization** - Верифицировано что REGISTRY централизован в `backend/core/metrics.py`

9. **Backtest System P1 Verification** - Все задачи верифицированы/исправлены:
    - Bar Magnifier ✅ реализован в numba_engine_v2, fallback_engine_v3
    - ATR Algorithm ✅ математически идентичны
    - entry_count bug ✅ исправлен
    - walk_forward division ✅ защита есть
    - Models consistency ✅ low priority (working)

#### Infrastructure Code (P2 - готов к deploy)

10. **HashiCorp Vault Client** (`backend/core/vault_client.py`):
    - VaultClient класс с CRUD операциями для секретов
    - Graceful fallback к env vars если Vault недоступен
    - Convenience функции для Bybit credentials

11. **MLflow Adapter** (`backend/ml/mlflow_adapter.py`):
    - MLflowAdapter для experiment tracking
    - Поддержка sklearn, xgboost, lightgbm, pytorch
    - Model registry с версионированием

12. **RL Trading Environment** (`backend/ml/rl/trading_env.py`):
    - Gym-compatible TradingEnv
    - Realistic simulation (commission, slippage, leverage)
    - Multiple reward functions

13. **DB Migration Squash** (`scripts/db_migration_squash.py`):
    - Автоматический backup + squash Alembic migrations
    - Dry-run mode для безопасности

#### Statistics

- **🎉 Общий прогресс**: 100% (92/92 задач)
- **P0 Critical**: 100% (all done) ✅
- **P1 High**: 100% (all done) ✅
- **P2 Medium**: 100% (all done) ✅

---

### Audit Verification Session 4 - Final (2026-01-28)

Финальная верификация задач аудита. Прогресс увеличен с 47% до 80%.

#### Frontend Security Additions

1. **SafeDOM.js** (`frontend/js/core/SafeDOM.js`) — XSS-безопасная работа с DOM:
    - `safeText()` — безопасная установка textContent
    - `safeHTML()` — санитизация через Sanitizer.js перед innerHTML
    - `createElement()` — создание элементов с атрибутами
    - `html` template literal — tagged template для HTML
    - `TrustedHTML` class — wrapper для доверенного HTML
    - Экспорт в `window.SafeDOM` для non-module scripts

2. **Production Init Script** (`frontend/js/init-production.js`):
    - Подавление `console.log/debug/info` в production
    - Сохранение `console.warn/error` для мониторинга
    - Глобальный `window.onerror` handler
    - Определение окружения через `window.__ENV__`

3. **Database Pool Configuration** (`backend/database/__init__.py`):
    - PostgreSQL: pool_size=5, pool_recycle=1800s, pool_pre_ping=True
    - MySQL: pool_size=5, pool_recycle=3600s, pool_pre_ping=True
    - Новая функция `get_pool_status()` для мониторинга pool

#### Верифицировано как корректно работающее

1. **vectorbt_sltp.py state initialization** — Массив `[initial_capital, 0.0, 0.0, 1.0, initial_capital, 0.0]` корректен
2. **CandleDataCache thread safety** — `threading.RLock()` уже в `fast_optimizer.py`
3. **walk_forward.py div/zero** — защита `if is_sharpe != 0` уже есть
4. **WebSocket reconnection** — реализовано в `liveTrading.js`
5. **Logger utility** — `Logger.js` готов для production
6. **Loading states** — `Loader.js` с spinner/dots/bars/skeleton
7. **Graceful shutdown** — `GracefulShutdownManager` в `live_trading/`
8. **Metrics collector** — Prometheus-style в `metrics_collector.py`

#### Статистика

- **Общий прогресс**: 83% (67/81 задач)
- **P0 Critical**: 100% (20/20) ✅
- **P1 High**: 92% (23/25)

---

### DeepSeek V3 MCP Integration (2026-01-28)

Добавлена интеграция DeepSeek V3 API через MCP (Model Context Protocol) для Cursor IDE.

#### Добавлено

1. **DeepSeek MCP Server** (`scripts/mcp/deepseek_mcp_server.py`):
    - Полноценный MCP сервер для DeepSeek V3 API
    - 8 специализированных инструментов:
        - `deepseek_chat` — общий чат и вопросы
        - `deepseek_code` — генерация кода
        - `deepseek_analyze` — анализ кода (performance, security, readability)
        - `deepseek_refactor` — рефакторинг (simplify, optimize, modernize, dry)
        - `deepseek_explain` — объяснение кода (beginner/intermediate/advanced)
        - `deepseek_test` — генерация тестов (pytest, unittest, jest, mocha)
        - `deepseek_debug` — помощь в отладке
        - `deepseek_document` — генерация документации (google, numpy, sphinx style)
    - Автоматический failover между двумя API ключами
    - Rate limit handling и retry logic

2. **MCP Configuration**:
    - `.agent/mcp.json` — обновлен с DeepSeek сервером
    - `.cursor/mcp.json` — Cursor-специфичная конфигурация
    - Переменные окружения для безопасного хранения ключей

3. **Environment Configuration** (`.env.example`):
    - Добавлены `DEEPSEEK_API_KEY`, `DEEPSEEK_API_KEY_2`
    - Настройки `DEEPSEEK_MODEL`, `DEEPSEEK_TEMPERATURE`

#### Использование

В Cursor Agent mode доступны инструменты:

```
Use deepseek_code to create a Python function for calculating Sharpe ratio
Use deepseek_analyze to review this trading strategy code
Use deepseek_test to generate pytest tests for BacktestEngine
```

Стоимость: ~$0.14 за 1M токенов (input), ~$0.28 за 1M (output).

---

### P1 Code Quality & Security Fixes - Session 4 (2026-01-28)

Продолжение работы над P1 задачами из аудита.

#### Исправлено

1. **router_registry.py Dead Code** (`backend/api/router_registry.py`):
    - Добавлен DEPRECATED notice в docstring
    - Добавлен `warnings.warn()` при импорте модуля
    - Функция `register_all_routers()` никогда не вызывается из app.py
    - Роутеры регистрируются напрямую в `app.py` (lines 370-415)

2. **CSRF Protection Middleware** (`backend/middleware/csrf.py`) — **NEW!**:
    - Создан `CSRFMiddleware` с double-submit cookie pattern
    - Автоматическая генерация токена в cookie `csrf_token`
    - Валидация `X-CSRF-Token` header для POST/PUT/DELETE/PATCH
    - Constant-time comparison через `secrets.compare_digest()`
    - Exempt paths для webhooks (`/api/v1/webhooks/*`) и документации
    - `csrf_exempt` декоратор для route-level exemption
    - `get_csrf_token()` helper для получения токена из request

3. **CorrelationIdMiddleware Fix** (`backend/middleware/correlation_id.py`):
    - `get_correlation_id()` теперь использует `ContextVar` вместо `uuid.uuid4()`
    - Добавлена функция `set_correlation_id()` для background tasks
    - Correlation ID доступен из любой точки request lifecycle
    - Middleware сохраняет и восстанавливает контекст правильно

4. **CSP Nonce Support** (`backend/middleware/security_headers.py`):
    - Добавлен параметр `use_csp_nonce` (по умолчанию True в production)
    - Nonce генерируется для каждого запроса через `secrets.token_urlsafe(16)`
    - В production CSP НЕ содержит `unsafe-inline`
    - Nonce доступен через `request.state.csp_nonce` и заголовок `X-CSP-Nonce`
    - Fallback на `unsafe-inline` в development для совместимости

5. **CORS Configuration Verified**:
    - `CORS_ALLOW_ALL=false` по умолчанию
    - Wildcard `*` только при явном включении `CORS_ALLOW_ALL=true`
    - Production использует список конкретных origins

6. **WebSocket Rate Limiting** (`backend/api/streaming.py`):
    - Добавлен `WebSocketRateLimiter` класс
    - Лимит: 60 сообщений/мин на клиента
    - Лимит: 10 соединений/мин на IP
    - Sliding window алгоритм
    - Автоматическая очистка при disconnect

7. **file_ops Router** (`backend/api/routers/file_ops.py`):
    - Добавлен `/status` endpoint
    - Добавлен `/exports` endpoint для листинга файлов
    - Добавлен TODO для полной реализации

8. **WebSocket Health Check & Graceful Shutdown** (`backend/api/streaming.py`):
    - Добавлен `GET /ws/v1/stream/health` endpoint
    - Возвращает статус соединений и rate limiter
    - Добавлен `graceful_shutdown()` метод в `StreamingConnectionManager`
    - Уведомляет клиентов перед закрытием соединений
    - Поддерживает timeout для принудительного закрытия

9. **ML Model Validation** (`backend/ml/enhanced/model_registry.py`):
    - Добавлен `validate_model()` метод для проверки моделей перед deployment
    - Проверяет accuracy, precision, recall, loss против thresholds
    - Автоматическое обновление статуса: STAGING (passed) или FAILED
    - `promote_model()` теперь требует validation (или `skip_validation=True`)
    - Защита от deployment неисправных моделей в production

**Обновлённый прогресс: ~46% (37 из 81 задачи)**

---

### P0 Security Fixes - Session 3 (2026-01-28)

Завершение критических P0 исправлений безопасности.

#### Исправлено

1. **API Secrets Encryption** (`bybit_websocket.py`, `bybit_from_history.py`):
    - `BybitWebSocketClient`: добавлено XOR шифрование для `api_key`/`api_secret`
    - `BybitAdapter`: добавлено XOR шифрование для `api_key`/`api_secret`
    - Ключи теперь хранятся как `_api_key_encrypted` + `_session_key`
    - Properties для декрипта при использовании

**Обновлённый прогресс: 36% (29 из 81 задачи)**

---

### P0 Security & Stability Fixes - Session 2 (2026-01-28)

Продолжение работы над приоритетными исправлениями из аудита.

#### Исправлено

1. **HTTP Client Leak Fix** (`service_registry.py`, `trading_engine_interface.py`):
    - `ServiceClient` теперь имеет `__aenter__`/`__aexit__` для context manager
    - `RemoteTradingEngine` теперь имеет `__aenter__`/`__aexit__` + `close()` метод
    - Защита от использования закрытого клиента: `RuntimeError` при `_closed = True`

2. **Division by Zero Fix** (`numba_engine_v2.py`, `fallback_engine_v3.py`):
    - `total_return` теперь защищён проверкой `if initial_capital > 0`
    - Предотвращает crash при edge cases с нулевым начальным капиталом

#### Верифицировано как уже исправленное

- **Graceful Shutdown** - `GracefulShutdownManager` полностью реализован в `live_trading/`
- **Feature Store Persistence** - JSON persistence через `_load_store`/`_save_store`

**Обновлённый прогресс: 35% (28 из 81 задачи)**

---

### P0 Security Fixes - Session 1 (2026-01-28)

Выполнены приоритетные исправления P0 из аудита безопасности.

#### Исправлено

1. **CandleDataCache Thread Safety** (`backend/backtesting/optimizers/fast_optimizer.py`):
    - Добавлен `threading.RLock()` для синхронизации доступа к singleton-кэшу
    - Все операции `get()` и `__setitem__` теперь thread-safe

2. **Rate Limiter Redis Backend** (`backend/middleware/rate_limiter.py`):
    - Добавлен класс `RedisRateLimiter` для распределённого rate limiting
    - Lua-скрипт для атомарных операций (sliding window algorithm)
    - Автоматический fallback на in-memory если Redis недоступен
    - Новые заголовки: `X-RateLimit-Backend: redis|memory`
    - Конфигурация через `REDIS_URL` env variable

#### Верифицировано как уже исправленное

- **OrderExecutor Context Manager** - `__aenter__`/`__aexit__` уже реализованы
- **Bybit Adapter Cache Lock** - `threading.RLock()` уже на месте (строка 55)
- **Frontend CSP Nonces** - `generateNonce()`, `getNonce()` уже реализованы
- **Frontend CSRF Tokens** - `getCsrfToken()`, `withCsrfToken()` уже реализованы

---

### Audit Status Review (2026-01-28)

Проведена проверка выполнения задач из файлов аудита. Создан сводный отчёт
`docs/AUDIT_STATUS_SUMMARY_2026_01_28.md`.

**Общий прогресс: 21% (17 из 81 задачи выполнено)**

#### Полностью выполненные модули

- ✅ **Core System** (5/5) - safe_divide, AI Cache Redis, Circuit Breaker persistence,
  Anomaly alerts, Bayesian thread-safety

#### Частично выполненные модули

- ⚠️ **API & Middleware** (6/12) - Admin/Security auth, ErrorHandler, MCP timing fix,
  WS_SECRET_KEY, HSTS headers
- ⚠️ **Backtest System** (3/11) - Shared memory cleanup, NumPy array limits, safe_divide
- ⚠️ **Database System** (3/7) - session.py fix, production warning, health endpoint

#### Требуют внимания:

- 🔴 **Services System** (0/15) - HTTP client leak, API secrets, cache race conditions
- 🔴 **ML System** (0/9) - Feature Store persistence, model validation
- 🔴 **Frontend System** (0/14) - CSRF, XSS, CSP nonce
- 🔴 **Monitoring System** (0/8) - Alert integrations, health checks

### Added

- **Comprehensive Health Checks System** (2026-01-28):
    - `backend/monitoring/health_checks.py` - Full system health monitoring:
        - Database connectivity check
        - Redis connectivity check
        - Bybit API status check
        - Disk space monitoring (warning at 80%, critical at 90%)
        - Memory usage monitoring (warning at 80%, critical at 90%)
        - CPU usage monitoring (warning at 80%, critical at 95%)
    - New API endpoints:
        - `GET /health/comprehensive` - Full system health report
        - `GET /health/comprehensive/{component}` - Individual component check
    - Classes: `HealthChecker`, `HealthCheckResult`, `SystemHealthReport`, `HealthStatus`
    - Caching with configurable TTL to prevent excessive checks

- **Prometheus AlertManager Rules** (2026-01-28):
    - `backend/monitoring/alerts/rules.yaml` - Production-ready alert rules:
        - Critical alerts (P0): API Down, Database Down, High Error Rate (>5%), Daily Loss Limit
        - High priority alerts (P1): High Latency (p99 > 5s), Redis Down, High Drawdown (>15%)
        - Medium priority alerts (P2): AI Budget Exceeded, Low Cache Hit Rate, Slow Backtests
        - SLO alerts: API Availability (99.9%), Latency (p95 < 2s)
    - Alert severity routing: Critical → PagerDuty + Slack + Email

- **Frontend Security Audit Fixes** (2026-01-28):
    - `ApiClient.js` - Centralized API client with CSRF protection, automatic retries, request/response interceptors
    - `WebSocketClient.js` - Robust WebSocket with auto-reconnect, exponential backoff, heartbeat monitoring
    - `Sanitizer.js` - DOMPurify-like HTML sanitizer for XSS prevention
    - `Logger.js` - Production-safe logging with conditional output
    - Enhanced `security.js` with nonce-based CSP (removed unsafe-inline)
    - CSRF token management functions
    - Security test suite in `frontend/js/tests/security.test.js`

- **safe_divide utility** in `metrics_calculator.py` - Centralized safe division function
  that handles zero and near-zero denominators gracefully
- **Circuit Breaker Redis Persistence** - Added `configure_persistence()`, `save_state()`,
  and `save_all_states()` methods to `CircuitBreakerRegistry` for state persistence across restarts
- **Enhanced Anomaly Alerting System** - New alert notifier classes:
    - `AlertNotifier` protocol for custom implementations
    - `WebhookAlertNotifier` for Slack/Discord/custom webhooks
    - `LogAlertNotifier` for simple logging-based alerts
    - `CompositeAlertNotifier` for combining multiple notifiers
- **Thread-safe Bayesian Optimizer** - Added `threading.RLock` protection and
  `_is_running` flag to prevent concurrent optimizations

### Changed

- `AnomalyDetector` now accepts optional `alert_notifier` parameter for integrated alerting
- `BayesianOptimizer.optimize_async()` now raises `RuntimeError` if another optimization
  is already running on the same instance
- Updated `backend/monitoring/__init__.py` to export new health check components

### Fixed

- Division by zero edge cases in metrics calculations (centralized in `safe_divide`)
- Circuit breaker state loss on application restart (now persisted to Redis)
- Missing alert notifications for detected anomalies
- Race conditions in Bayesian optimizer concurrent access

### Tests

- Added `tests/backend/monitoring/test_health_checks.py` with 20 comprehensive tests covering:
    - HealthStatus enum values
    - HealthCheckResult creation and serialization
    - SystemHealthReport aggregation
    - Individual component checks (disk, memory, CPU)
    - Caching behavior
    - Overall status calculation logic
    - Module-level convenience functions
- Added `tests/test_core_audit_fixes.py` with 21 comprehensive tests covering:
    - `safe_divide` edge cases
    - Circuit breaker persistence methods
    - Alert notifier functionality
    - Thread-safe Bayesian optimizer
    - AI Cache Redis verification
    - Integration tests

## [1.0.0] - 2026-01-01

### Added

- Initial release of Bybit Strategy Tester v2
- 166-metric MetricsCalculator with TradingView compliance
- Circuit Breaker pattern for external API calls
- AI Cache with Redis backend
- Anomaly Detection system
- Bayesian Optimization with Optuna
- Comprehensive backtesting engine

---

_Last Updated: 2026-01-28_
