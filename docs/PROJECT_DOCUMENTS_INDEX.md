# 📚 Полный список документов проекта

**Дата:** 2026-02-26
**Статус:** Актуализирован

---

## 📋 Документы аудита (основа для работ)

### Главные конфигурационные файлы

| Файл | Назначение | Статус |
|------|------------|--------|
| `QWEN.md` | 🔑 Главная конфигурация Qwen AI | ✅ Актуален |
| `CLAUDE.md` | Конфигурация для Claude AI | ✅ Актуален |
| `AGENTS.MD` | Глобальные правила для всех AI агентов | ✅ Актуален |
| `CONTINUE.md` | 📌 Текущий статус и продолжение сессий | ✅ Актуален |
| `.qwen/config.json` | Конфигурация Qwen Code | ✅ Актуален |

### Основные документы проекта

| Файл | Назначение | Статус |
|------|------------|--------|
| `README.md` | Общая информация о проекте | ✅ Актуален |
| `QUICKSTART.md` | Быстрый старт | ✅ Актуален |
| `QUICK_REFERENCE.md` | Справочник команд | ✅ Актуален |
| `CONTRIBUTING.md` | Правила контрибуции | ✅ Актуален |
| `CHANGELOG.md` | История изменений | ✅ Актуален |

---

## 🏗️ Архитектурные документы

### Архитектура ядра

| Файл | Назначение |
|------|------------|
| `docs/architecture/ENGINE_ARCHITECTURE.md` | Архитектура бэктест движка |
| `docs/architecture/ENGINE_PARITY.md` | Паритет движков (TradingView) |
| `docs/architecture/FALLBACK_ENGINE_V4.md` | Документация FallbackEngineV4 |
| `docs/architecture/HYBRID_TWO_PHASE_PIPELINE.md` | Hybrid two-phase pipeline |
| `docs/architecture/OPTIMIZATION_RECOMMENDATIONS.md` | Рекомендации по оптимизации |
| `docs/architecture/RL_ENVIRONMENT.md` | RL окружение |
| `docs/architecture/STRATEGIES_PROCESS_FLOW.md` | Flow стратегий |
| `docs/architecture/STRATEGY_BUILDER_ARCHITECTURE.md` | Архитектура Strategy Builder |
| `docs/architecture/STRATEGY_BUILDER_KNOWN_LIMITATIONS.md` | Известные ограничения Strategy Builder |
| `docs/architecture/UNIVERSAL_ENGINE_PERFORMANCE_SPEC.md` | Спецификация производительности |

### Архитектурные решения

| Файл | Назначение |
|------|------------|
| `docs/DECISIONS.md` | Архитектурные решения |
| `docs/DEPRECATION_SCHEDULE.md` | График депрекации компонентов |
| `docs/DUAL_MODE_ARCHITECTURE.md` | Дуальная архитектура |
| `docs/ENGINE_OPTIMIZER_MODERNIZATION_PROPOSALS.md` | Предложения по модернизации |
| `docs/STATE_MANAGEMENT_AND_API_VERSIONING.md` | Управление состоянием и версионирование API |

---

## 📊 Документы по метрикам и TradingView

| Файл | Назначение |
|------|------------|
| `docs/reference/TRADINGVIEW_METRICS_REFERENCE.md` | 📊 Полный справочник метрик TradingView |
| `docs/reference/TRADINGVIEW_METRICS_MAPPING.md` | Маппинг метрик |
| `docs/reference/TRADINGVIEW_COMPARISON.md` | Сравнение с TradingView |
| `docs/reference/VECTORBT_IMPROVEMENT_PLAN.md` | План улучшений VectorBT |
| `docs/reference/VECTORBT_VS_FALLBACK.md` | Сравнение VectorBT vs Fallback |

---

## 🔌 API документы

| Файл | Назначение |
|------|------------|
| `docs/API_REFERENCE.md` | Справочник API |
| `docs/API_INVENTORY.md` | Инвентарь API endpoints |
| `docs/SDK_REFERENCE.md` | Справочник SDK |
| `docs/api/README.md` | README API |

---

## 🎯 Strategy Builder документы

### Главные документы

| Файл | Назначение |
|------|------------|
| `docs/STRATEGY_BUILDER_INDEX.md` | 📑 Главный индекс Strategy Builder |
| `docs/STRATEGY_BUILDER_TECHNICAL_SPECIFICATION.md` | Техническая спецификация |
| `docs/STRATEGY_BUILDER_IMPLEMENTATION_STATUS.md` | Статус реализации |
| `docs/STRATEGY_BUILDER_E2E_TEST_RESULTS.md` | Результаты E2E тестов |

### Реализация и фиксы

| Файл | Назначение |
|------|------------|
| `docs/STRATEGY_BUILDER_ADAPTER_API.md` | API адаптера |
| `docs/STRATEGY_BUILDER_API_FIX_COMPLETE.md` | ✅ Завершён фикс API |
| `docs/STRATEGY_BUILDER_API_ISSUES.md` | Проблемы API |
| `docs/STRATEGY_BUILDER_BLOCKS_FIX.md` | Фикс блоков |
| `docs/STRATEGY_BUILDER_CACHE_FIX.md` | Фикс кэша |
| `docs/STRATEGY_BUILDER_IMPLEMENTATION_ROADMAP.md` | Дорожная карта реализации |
| `docs/STRATEGY_BUILDER_MIGRATION_AND_E2E.md` | Миграция и E2E |
| `docs/STRATEGY_BUILDER_MIGRATION_COMPLETE.md` | ✅ Миграция завершена |
| `docs/STRATEGY_BUILDER_MODAL_FIX.md` | Фикс модального окна |
| `docs/STRATEGY_BUILDER_MODAL_FIX_V2.md` | Фикс модального окна v2 |
| `docs/STRATEGY_BUILDER_MODAL_FIX_V3.md` | Фикс модального окна v3 |
| `docs/STRATEGY_BUILDER_MODAL_FINAL_FIX.md` | ✅ Финальный фикс модального окна |
| `docs/STRATEGY_BUILDER_NEXT_STEPS.md` | Следующие шаги |
| `docs/STRATEGY_BUILDER_PHASE1_COMPLETE.md` | ✅ Фаза 1 завершена |
| `docs/STRATEGY_BUILDER_PHASE2_COMPLETE.md` | ✅ Фаза 2 завершена |
| `docs/STRATEGY_BUILDER_READY_TO_RUN.md` | Готов к запуску |
| `docs/STRATEGY_BUILDER_RSI_TEMPLATE.md` | RSI шаблон |
| `docs/STRATEGY_BUILDER_SYNTAX_FIX.md` | Фикс синтаксиса |
| `docs/STRATEGY_BUILDER_TEMPLATE_CREATED.md` | Шаблон создан |
| `docs/STRATEGY_BUILDER_TESTING_GUIDE.md` | Руководство по тестированию |
| `docs/STRATEGY_BUILDER_UI_FIX.md` | Фикс UI |
| `docs/STRATEGY_BUILDER_UI_FIX_V2.md` | Фикс UI v2 |
| `docs/STRATEGY_BUILDER_UI_QUICK_TEST.md` | Быстрый тест UI |
| `docs/STRATEGY_BUILDER_VALIDATE_FIX.md` | Фикс валидации |
| `docs/STRATEGY_BUILDER_VALIDATION_IMPROVEMENTS.md` | Улучшения валидации |

---

## 🗺️ Дорожные карты

| Файл | Назначение |
|------|------------|
| `docs/ROADMAP_REMAINING_TASKS.md` | Оставшиеся задачи |
| `docs/ROADMAP_ADVANCED_IDEAS.md` | Продвинутые идеи |
| `docs/IMPROVEMENT_ROADMAP.md` | Дорожная карта улучшений |
| `docs/PROJECT_READINESS_AND_STRATEGY_2026.md` | Готовность проекта 2026 |
| `docs/REMAINING_AND_NEW_TASKS.md` | Оставшиеся и новые задачи |
| `docs/REMAINING_INFRASTRUCTURE_TASKS.md` | Оставшиеся инфраструктурные задачи |
| `docs/IMPLEMENTATION_PLAN.md` | План реализации |
| `docs/OPTIMIZATION_REFACTORING.md` | Рефакторинг оптимизации |

---

## 📄 Документы по выполненным сессиям

### P0-1: Strategy Builder (выполнено)

**Директория:** `docs/` (корневая)

| Документ | Статус | Назначение |
|----------|--------|------------|
| `STRATEGY_BUILDER_INDEX.md` | ✅ Создан | Главный индекс |
| `STRATEGY_BUILDER_TECHNICAL_SPECIFICATION.md` | ✅ Создан | Техническая спецификация |
| `STRATEGY_BUILDER_IMPLEMENTATION_STATUS.md` | ✅ Создан | Статус реализации |
| `STRATEGY_BUILDER_E2E_TEST_RESULTS.md` | ✅ Создан | Результаты E2E тестов |
| `STRATEGY_BUILDER_PHASE1_COMPLETE.md` | ✅ Создан | Отчёт о фазе 1 |
| `STRATEGY_BUILDER_PHASE2_COMPLETE.md` | ✅ Создан | Отчёт о фазе 2 |
| `STRATEGY_BUILDER_MIGRATION_COMPLETE.md` | ✅ Создан | Миграция завершена |
| `STRATEGY_BUILDER_API_FIX_COMPLETE.md` | ✅ Создан | API фикс завершён |
| `STRATEGY_BUILDER_MODAL_FINAL_FIX.md` | ✅ Создан | Финальный фикс модального окна |

**Фиксы и улучшения:**
- `STRATEGY_BUILDER_ADAPTER_API.md`
- `STRATEGY_BUILDER_API_ISSUES.md`
- `STRATEGY_BUILDER_BLOCKS_FIX.md`
- `STRATEGY_BUILDER_CACHE_FIX.md`
- `STRATEGY_BUILDER_MODAL_FIX.md` / `V2` / `V3`
- `STRATEGY_BUILDER_SYNTAX_FIX.md`
- `STRATEGY_BUILDER_UI_FIX.md` / `V2`
- `STRATEGY_BUILDER_VALIDATE_FIX.md`
- `STRATEGY_BUILDER_VALIDATION_IMPROVEMENTS.md`

---

### P0-2: Database Modernization (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `DATABASE_MODERNIZATION_COMPLETE.md` | ✅ Создан | ✅ Завершено |
| `DATABASE_MODERNIZATION_PLAN.md` | ✅ Создан | План модернизации |
| `DATABASE_OPERATIONS_REPORT.md` | ✅ Создан | Отчёт об операциях |

---

### P0-3: StateManager (в работе)

**Директория:** `docs/refactoring/p0-3-state-manager/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `PLAN.md` | ✅ Обновлён | Главный план миграции |
| `SESSION_REPORT.md` | ✅ Создан | Отчёт о текущей сессии |
| `NEXT_SESSION.md` | ✅ Создан | Быстрый старт для следующей сессии |
| `step-2-1-dashboard.md` | ✅ Создан | План миграции dashboard.js |
| `step-2-2-backtest-results.md` | ✅ Создан | План миграции backtest_results.js |
| `step-2-3-strategy-builder.md` | ✅ Создан | План миграции strategy_builder.js |
| `step-3-integration-tests.md` | ✅ Создан | План интеграционных тестов |
| `step-4-final-documentation.md` | ✅ Создан | План финальной документации |

**Исходный код:**
- `frontend/js/core/StateManager.js` (471 строка)
- `frontend/js/core/state-helpers.js` (280 строк)

**Тесты:**
- `tests/frontend/core/StateManager.test.js` (350 строк)
- `tests/frontend/core/state-helpers.test.js` (280 строк)

---

### P0-4: Circuit Breakers для MCP (выполнено)

**Директория:** `docs/refactoring/p0-4/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `step-1.1-inventory.md` | ✅ Создан | Инвентаризация MCP инструментов |
| `step-1.2-tests.md` | ✅ Создан | План тестов |
| `step-2-implementation.md` | ✅ Создан | Реализация circuit breakers |
| `step-3-testing.md` | ✅ Создан | Тестирование |

**Исходный код:**
- `backend/mcp/mcp_integration.py` (~300 строк добавлено)

**Тесты:**
- `tests/backend/mcp/test_mcp_integration.py` (интеграционные тесты)

---

### Phase 3: AI Agents & Optimization (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `PHASE3_FINAL_SUMMARY.md` | ✅ Создан | Финальный отчёт |
| `PHASE3_STEP2_COMPLETE.md` | ✅ Создан | Шаг 2 завершён |

---

### Phase 4: Production Deployment (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `PHASE4_COMPLETE.md` | ✅ Создан | ✅ Фаза завершена |
| `PHASE4_DEPLOYMENT_REPORT.md` | ✅ Создан | Отчёт о развёртывании |
| `PHASE4_DEPLOYMENT_SUCCESS.md` | ✅ Создан | ✅ Развёртывание успешно |
| `PHASE4_FINAL_REPORT.md` | ✅ Создан | Финальный отчёт |
| `PHASE4_HANDOFF.md` | ✅ Создан | Передача проекта |
| `PHASE4_INDEX.md` | ✅ Создан | Индекс фазы 4 |
| `PHASE4_MONITORING_COMPLETE.md` | ✅ Создан | ✅ Мониторинг настроен |
| `PHASE4_QUICKSTART.md` | ✅ Создан | Быстрый старт |
| `PHASE4_README.md` | ✅ Создан | README |
| `PHASE4_SECURITY_HARDENING.md` | ✅ Создан | Усиление безопасности |
| `PHASE4_SUMMARY.md` | ✅ Создан | Сводка |
| `PHASE4_DELIVERABLES_CHECKLIST.md` | ✅ Создан | Чеклист результатов |

---

### Phase 5: Metrics & Risk Management (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `PHASE5_COMPLETE.md` | ✅ Создан | ✅ Фаза завершена |
| `PHASE5_FINAL_SUMMARY.md` | ✅ Создан | Финальный отчёт |
| `PHASE5_INDEX.md` | ✅ Создан | Индекс фазы 5 |
| `PHASE5_METRICS_COMPLETE.md` | ✅ Создан | ✅ Метрики настроены |
| `PHASE5_METRICS_INTEGRATION_COMPLETE.md` | ✅ Создан | ✅ Интеграция метрик |
| `PHASE5_PERFORMANCE_BASELINE.md` | ✅ Создан | Базовая производительность |
| `PHASE5_RISK_MANAGEMENT.md` | ✅ Создан | Управление рисками |
| `PHASE5_RISK_MANAGEMENT_COMPLETE.md` | ✅ Создан | ✅ Управление рисками завершено |
| `PHASE5_ALERT_CONFIGURATION.md` | ✅ Создан | Конфигурация алертов |
| `PHASE5_SESSION_SUMMARY.md` | ✅ Создан | Отчёт о сессии |

---

### Phase 1: Week 1 (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `PHASE1_WEEK1_REPORT.md` | ✅ Создан | Отчёт за неделю 1 |
| `WEEK1_OPTIMIZATIONS_DONE.md` | ✅ Создан | Оптимизации завершены |

---

### Phase 2: Week 2 (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `WEEK2_IMPLEMENTATION_SUMMARY.md` | ✅ Создан | Сводка реализации |
| `WEEK2_QUICK_START.md` | ✅ Создан | Быстрый старт |
| `WEEK2_REDIS_PUBSUB_DONE.md` | ✅ Создан | ✅ Redis Pub/Sub настроен |
| `WEEK2_WHATS_NEW.md` | ✅ Создан | Что нового |

---

### Phase 3: Week 3 (выполнено)

**Директория:** `docs/archive/`

| Документ | Статус | Назначение |
|----------|--------|------------|
| `WEEK3_DOCKER_NGINX_DEPLOYMENT.md` | ✅ Создан | Развёртывание Docker/Nginx |
| `WEEK3_QUICK_START.md` | ✅ Создан | Быстрый старт |

---

## 📊 Session Reports (отчёты о сессиях)

### Текущие сессии

| Документ | Сессия | Статус |
|----------|--------|--------|
| `docs/refactoring/p0-3-state-manager/SESSION_REPORT.md` | P0-3 StateManager | ✅ Создан |
| `docs/refactoring/p0-3-state-manager/NEXT_SESSION.md` | P0-3 Next Session | ✅ Создан |

### Архивные сессии

| Документ | Сессия | Статус |
|----------|--------|--------|
| `docs/archive/SESSION_SUMMARY.md` | Общая сессия | ✅ Создан |
| `docs/archive/SESSION_SUMMARY_AI_IMPROVEMENTS.md` | AI улучшения | ✅ Создан |
| `docs/archive/SESSION_SUMMARY_AUDIT.md` | Аудит сессия | ✅ Создан |
| `docs/archive/PHASE5_SESSION_SUMMARY.md` | Phase 5 сессия | ✅ Создан |
| `docs/archive/multi_agent_session.md` | Multi-agent сессия | ✅ Создан |

---

## 🤖 AI Agent документы

### AI Agents

| Файл | Назначение |
|------|------------|
| `docs/AGENTS_TOOLS.md` | Инструменты AI агентов |
| `docs/ai/AI_AGENT_SYSTEM_DOCUMENTATION.md` | Документация системы AI агентов |
| `docs/ai/AI_AGENT_COMPARISON_WITH_FRAMEWORKS.md` | Сравнение с фреймворками |
| `docs/ai/AI_AGENT_EVOLUTION_PLAN.md` | План эволюции AI агентов |
| `docs/ai/CURSOR_COPILOT_SYNC.md` | Синхронизация Cursor/Copilot |
| `docs/ai-context.md` | AI контекст |

### AI Reports (archive)

| Документ | Статус |
|----------|--------|
| `AI_AGENTS_TEST_REPORT.md` | ✅ Создан |
| `AI_AGENT_RECOMMENDATIONS_IMPLEMENTATION.md` | ✅ Создан |
| `AI_AGENT_TESTING_FINAL_REPORT.md` | ✅ Создан |
| `AI_AUDIT_SUMMARY_20251206.md` | ✅ Создан |
| `AI_DEEP_AUDIT_FULL_REPORT.md` | ✅ Создан |
| `AI_MODERNIZATION_REPORT.md` | ✅ Создан |
| `DEEPSEEK_AUDIT_20260104_111559.md` | ✅ Создан |
| `DEEPSEEK_BACKTEST_CONSULT_20260104_183013.md` | ✅ Создан |
| `DEEPSEEK_BUG_AUDIT_20260104_115025.md` | ✅ Создан |
| `DEEPSEEK_CODE_REVIEW.md` | ✅ Создан |
| `DEEPSEEK_FINAL_EVALUATION.md` | ✅ Создан |
| `DEEPSEEK_IMPLEMENTATION_REPORT.md` | ✅ Создан |
| `DEEPSEEK_OPTIMIZATION_RECOMMENDATIONS.md` | ✅ Создан |
| `PERPLEXITY_BEST_PRACTICES_*.md` | ✅ Создан |

---

## 📈 Audit Reports

### Главные аудиты

| Документ | Статус |
|----------|--------|
| `AUDIT_REPORT.md` | ✅ Создан |
| `AUDIT_SUMMARY.md` | ✅ Создан |
| `AUDIT_IMPLEMENTATION_REPORT.md` | ✅ Создан |
| `AUDIT_IMPROVEMENTS_REPORT.md` | ✅ Создан |
| `AUDIT_TZ_COMPLIANCE.md` | ✅ Создан |
| `MANUAL_AUDIT_RESPONSE.md` | ✅ Создан |
| `DEEP_AUDIT_RESPONSE.md` | ✅ Создан |

### Компонентные аудиты

| Документ | Статус |
|----------|--------|
| `BACKTESTING_TEST_REPORT.md` | ✅ Создан |
| `DASHBOARD_AUDIT_REPORT.md` | ✅ Создан |
| `FRONTEND_AUDIT_REPORT.md` | ✅ Создан |
| `METRICS_AUDIT_REPORT.md` | ✅ Создан |
| `METRICS_TV_AUDIT_20260107.md` | ✅ Создан |
| `SECURITY_TEST_REPORT.md` | ✅ Создан |

---

## 🧪 Testing Reports

| Документ | Статус |
|----------|--------|
| `ADVANCED_TEST_REPORT.md` | ✅ Создан |
| `INTEGRATION_TEST_REPORT.md` | ✅ Создан |
| `ML_AI_INTEGRATION_PHASE3_REPORT.md` | ✅ Создан |
| `PERFORMANCE_REPORT.md` | ✅ Создан |
| `TRADINGVIEW_COMPARISON_REPORT.md` | ✅ Создан |
| `TV_COMPARISON_FINAL_REPORT.md` | ✅ Создан |
| `TV_METRICS_FINAL_REPORT.md` | ✅ Создан |

---

## 📁 Архивные документы (legacy)

**Директория:** `docs/archive/` (132 файла)

### AI DeepSeek аудиты

- `AI_DEEP_AUDIT_REPORT_20251207_203311.md`
- `AI_DEEP_AUDIT_REPORT_20251207_204552.md`
- `DEEPSEEK_RECOMMENDATIONS_REPORT.md`
- `DEEPSEEK_RECOMMENDATIONS_V2.md`
- `DEEPSEEK_FIXES_REPORT.md`

### VectorBT консультации

- `deepseek_vectorbt_consultation.md`
- `deepseek_vectorbt_full_consultation.md`
- `perplexity_vectorbt_consultation.md`

### Deployment guides

- `DEPLOYMENT_GUIDE.md`
- `DEPLOYMENT_QUICKSTART.md`
- `DEPLOYMENT_VALIDATION_FINAL.md`
- `AUTOSTART_DETAILED_GUIDE.md`
- `AUTOSTART_GUIDE.md`

### Production

- `PRODUCTION_CHECKLIST.md`
- `PRODUCTION_INDEX.md`
- `PRODUCTION_SETUP.md`
- `PROJECT_INDEX.md`
- `PROJECT_STATUS_FINAL.md`

### Metrics

- `COMPLETE_METRICS_REPORT.md`
- `METRICS_COMPARISON_REPORT.md`
- `METRICS_VERIFICATION_SUMMARY.md`
- `TRADINGVIEW_DEEP_ANALYSIS.md`

### Database

- `DATABASE_MODERNIZATION_PLAN.md`
- `DATABASE_MODERNIZATION_COMPLETE.md`
- `DATABASE_OPERATIONS_REPORT.md`

### Code quality

- `CODE_CLEANUP_SUMMARY.md`
- `BACKTEST_FIXES_SUMMARY.md`
- `BACKTESTER_STRUCTURE_REPORT.md`
- `OPTIMIZATION_SUMMARY.md`
- `FINAL_OPTIMIZATION_REPORT.md`
- `FINAL_REPORT.md`

### Documentation

- `DOCUMENTATION_INDEX.md`
- `README_FINAL.md`
- `README.old.md`

---

## 📊 Сводная статистика

### Активные документы (не archive)

| Категория | Количество |
|-----------|------------|
| Главные конфигурационные | 5 |
| Основные документы проекта | 5 |
| Архитектурные | 13 |
| Метрики и TradingView | 5 |
| API | 4 |
| Strategy Builder | 25+ |
| Дорожные карты | 8 |
| P0-3 StateManager (текущий) | 8 |
| P0-4 Circuit Breakers (готово) | 4 |
| **ИТОГО активных** | **~77** |

### Архивные документы (docs/archive)

| Категория | Количество |
|-----------|------------|
| Phase 1-5 отчёты | 25+ |
| Session reports | 5 |
| AI Agent reports | 15+ |
| Audit reports | 10+ |
| Testing reports | 10+ |
| Legacy документы | 67+ |
| **ИТОГО архив** | **~132** |

### **ВСЕГО документов: ~209**

---

## 🔑 Ключевые документы для работы

### Для продолжения P0-3 StateManager

1. **CONTINUE.md** — текущий статус
2. **docs/refactoring/p0-3-state-manager/NEXT_SESSION.md** — быстрый старт
3. **docs/refactoring/p0-3-state-manager/PLAN.md** — детальный план
4. **QWEN.md** — контекст проекта

### Для понимания проекта

1. **README.md** — общая информация
2. **docs/architecture/ENGINE_ARCHITECTURE.md** — архитектура движка
3. **docs/STRATEGY_BUILDER_INDEX.md** — Strategy Builder
4. **docs/reference/TRADINGVIEW_METRICS_REFERENCE.md** — метрики

### Для новых сессий

1. **CONTINUE.md** — что делать дальше
2. **docs/refactoring/P0_EXECUTION_PLAN.md** — общий план P0
3. **docs/ROADMAP_REMAINING_TASKS.md** — оставшиеся задачи

---

*Список актуализирован: 2026-02-26*
*Всего документов: ~209 (активных: ~77, архив: ~132)*
