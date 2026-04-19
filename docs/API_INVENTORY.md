# API Inventory — использование endpoints frontend

**Дата:** 2026-01-31  
**Источник:** AUDIT_PROJECT_EXTENDED.md, рекомендация «Инвентаризация API»

## Endpoints, используемые frontend

| Endpoint | Файл(ы) | Назначение |
|----------|---------|------------|
| `GET/POST/DELETE /api/v1/marketdata/symbols/blocked` | strategy_builder.js | Блокировка тикеров |
| `GET /api/v1/marketdata/tickers` | strategy_builder.js | Список тикеров по категории |
| `GET /api/v1/marketdata/symbols/local` | strategy_builder.js, debug | Локальные символы |
| `GET /api/v1/marketdata/symbols-list` | strategy_builder.js, debug | Список символов |
| `GET/DELETE /api/v1/marketdata/symbols/db-groups` | strategy_builder.js | Группы тикеров в БД |
| `POST /api/v1/marketdata/symbols/sync-all-tf` | strategy_builder.js | Синхронизация свечей |
| `GET /api/v1/strategies/`, `GET /strategies/{id}` | strategyCRUD.js, strategies.js | CRUD стратегий |
| `POST /api/v1/strategies/`, `PUT /strategies/{id}` | strategyCRUD.js | Создание/обновление |
| `DELETE /api/v1/strategies/{id}` | strategyCRUD.js | Удаление |
| `POST /api/v1/strategies/{id}/duplicate` | strategyCRUD.js | Дублирование |
| `POST /api/v1/strategies/{id}/activate` | strategyCRUD.js | Активация |
| `POST /api/v1/strategies/{id}/pause` | strategyCRUD.js | Пауза |
| `GET /api/v1/strategies/types` | strategyCRUD.js | Типы стратегий |
| `GET /api/v1/strategy-builder/strategies/{id}` | strategy_builder.js | Загрузка стратегии |
| `POST /api/v1/strategy-builder/strategies` | strategy_builder.js | Создание |
| `PUT /api/v1/strategy-builder/strategies/{id}` | strategy_builder.js | Обновление |
| `GET /api/v1/strategy-builder/strategies/{id}/generate-code` | strategy_builder.js | Генерация кода |
| `POST /api/v1/strategy-builder/strategies/{id}/backtest` | strategy_builder.js, optimization_panels.js | Бэктест |
| `WS /api/v1/strategy-builder/ws/validate` | strategy_builder_ws.js | WebSocket валидация |
| `GET /api/v1/backtests/{id}` | backtest_results.js, strategy_builder.js | Результат бэктеста |
| `GET /api/v1/backtests/` | analytics_advanced.js | Список бэктестов |
| `GET /api/v1/optimizations/` | optimization.js | Список оптимизаций |
| `GET /api/v1/optimizations/{id}/status` | optimization.js, optimization_panels.js | Статус |
| `GET /api/v1/optimizations/{id}/results` | optimization.js, optimization_results.js | Результаты |
| `POST /api/v1/optimizations/grid-search-sse` | optimization_panels.js | SSE grid search |
| `POST /api/v1/optimizations/{id}/cancel` | optimization.js | Отмена |
| `GET /api/v1/marketplace/*` | marketplace.js | Marketplace |
| `GET /api/v1/dashboard/market/tickers` | trading.js | Топ тикеров |
| `GET /api/v1/chat/history/*` | streaming_chat.js | История чата |
| `POST /api/v1/monte-carlo/analyze` | analytics_advanced.js | Monte Carlo |
| `POST /api/v1/monte-carlo/robustness` | — | Monte Carlo robustness (slippage_stress, price_randomization) |
| `POST /api/v1/market-regime/detect` | analytics_advanced.js | Market regime |
| `POST /api/v1/agents/backtest/ai-analyze` | backtest_results.js | AI анализ |

## Роутеры без прямого использования frontend (возможный legacy)

Роутеры, для которых в текущем frontend не найдены fetch/API-вызовы:

- **admin** — админ-панель (может использоваться отдельно)
- **cache** — кэш (возможно используется middleware/backend)
- **chaos** — chaos engineering
- **circuit_breakers** — Circuit breakers dashboard
- **csv_export** — экспорт CSV
- **data_quality** — качество данных
- **db_metrics** — метрики БД
- **degradation** — degradation
- **enhanced_ml** — ML
- **executions** — исполнения
- **file_ops** — файловые операции
- **health_monitoring** — health (может использоваться internal)
- **inference** — ML inference
- **key_rotation** — ротация ключей
- **kms** — KMS
- **live_trading** — live trading (отдельный режим)
- **monitoring** — Prometheus
- **orchestration** — оркестрация
- **property_testing** — property testing
- **rate_limiting** — rate limiting
- **reasoning** — reasoning
- **secrets_scanner** — сканер секретов
- **slo_error_budget** — SLO
- **state_management** — state
- **synthetic_monitoring** — синтетический мониторинг
- **test_runner** — тесты
- **tick_charts** — tick charts
- **tracing** — трейсинг
- **trading_halt** — остановка торговли
- **walk_forward** — walk-forward (возможно через optimizations)

## Legacy / Internal роутеры (без использования frontend)

Помечены как `[legacy]` — кандидаты на документирование отдельного использования (CLI, скрипты, внешние системы). **Не удалять** без подтверждения.

| Tag | Роутер | Примечание |
|-----|--------|------------|
| [legacy] | admin | Админ-панель |
| [legacy] | chaos | Chaos engineering |
| [legacy] | circuit_breakers | Circuit breakers dashboard |
| [legacy] | csv_export | Экспорт CSV |
| [legacy] | data_quality | Качество данных |
| [legacy] | db_metrics | Метрики БД |
| [legacy] | degradation | Graceful degradation |
| [legacy] | enhanced_ml | ML registry/models |
| [legacy] | executions | Исполнения ордеров |
| [legacy] | file_ops | Файловые операции |
| [legacy] | key_rotation | Ротация API ключей |
| [legacy] | kms | KMS интеграция |
| [legacy] | monitoring | Prometheus metrics |
| [legacy] | orchestration | LangGraph оркестрация |
| [legacy] | property_testing | Property-based testing |
| [legacy] | rate_limiting | Rate limiting API |
| [legacy] | secrets_scanner | Сканер секретов |
| [legacy] | slo_error_budget | SLO Error Budget |
| [legacy] | state_management | State management |
| [legacy] | synthetic_monitoring | Синтетический мониторинг |
| [legacy] | test_runner | Запуск тестов из UI |
| [legacy] | tracing | OpenTelemetry |
| [legacy] | trading_halt | Остановка торговли |
| [internal] | health_monitoring | Внутренние health checks |
| [internal] | cache | Backend cache API |

## Рекомендации

1. **Legacy:** Endpoints помечены в этой таблице. Для добавления OpenAPI-тега `x-legacy: true` — отдельная задача.
2. **Документировать:** admin, live_trading, monitoring — отдельные user flows.
3. **Не удалять:** Роутеры могут использоваться CLI, скриптами, внешними системами.
