# Strategy Builder — индекс документации

**Дата:** 2026-01-31  
**Цель:** Консолидация документации Strategy Builder (рекомендация AUDIT_PROJECT_EXTENDED)

---

## Текущая документация (primary)

| Документ | Описание |
|----------|----------|
| [STRATEGY_BUILDER_ARCHITECTURE.md](architecture/STRATEGY_BUILDER_ARCHITECTURE.md) | Архитектура, API, интеграции |
| [STRATEGY_BUILDER_ADAPTER_API.md](STRATEGY_BUILDER_ADAPTER_API.md) | Adapter API, маппинг блоков |
| [AUDIT_PARAMETERS_WINDOW.md](AUDIT_PARAMETERS_WINDOW.md) | Аудит окна Параметры |
| [AUDIT_LIBRARY_BLOCK.md](AUDIT_LIBRARY_BLOCK.md) | Аудит блока Библиотека |

---

## Исторические документы (legacy, для справки)

Документы ниже фиксируют завершённые фазы и исправления. Актуальная информация — в primary docs выше.

| Документ | Тема |
|----------|------|
| STRATEGY_BUILDER_IMPLEMENTATION_STATUS.md | Статус внедрения |
| STRATEGY_BUILDER_IMPLEMENTATION_ROADMAP.md | Roadmap |
| STRATEGY_BUILDER_PHASE1_COMPLETE.md | Phase 1 |
| STRATEGY_BUILDER_PHASE2_COMPLETE.md | Phase 2 |
| STRATEGY_BUILDER_MIGRATION_COMPLETE.md | Миграция |
| STRATEGY_BUILDER_E2E_TEST_RESULTS.md | E2E тесты |
| STRATEGY_BUILDER_TESTING_GUIDE.md | Гайд по тестированию |
| STRATEGY_BUILDER_TECHNICAL_SPECIFICATION.md | Техническая спецификация |
| STRATEGY_BUILDER_MODAL_FIX*.md, STRATEGY_BUILDER_UI_FIX*.md | Исправления UI/модалов |
| STRATEGY_BUILDER_CACHE_FIX.md, STRATEGY_BUILDER_BLOCKS_FIX.md | Исправления кэша/блоков |
| STRATEGY_BUILDER_API_FIX_COMPLETE.md, STRATEGY_BUILDER_API_ISSUES.md | API |
| STRATEGY_BUILDER_RSI_TEMPLATE*.md | RSI шаблон |

---

## Структура кода

```
frontend/js/pages/
├── strategy_builder.js      # Основной модуль (~11k строк)
├── strategy_builder_ws.js   # WebSocket валидация
├── strategy_builder_debug.js
└── symbol_picker_debug.js

backend/
├── api/routers/strategy_builder.py
├── backtesting/strategy_builder_adapter.py
└── services/strategy_builder/
```

## План декомпозиции strategy_builder.js (AUDIT_PROJECT_EXTENDED)

Рекомендуемые модули для выделения (будущий рефакторинг):

| Модуль | Содержимое | Строк (прибл.) |
|--------|------------|----------------|
| `strategy_builder_block_library.js` | blockLibrary, getDefaultParams, getBlockPorts | ~2500 |
| `strategy_builder_map_blocks.js` | mapBlocksToBackendParams(blocks, connections) | ~200 |
| `strategy_builder_canvas.js` | drag, drop, connections, marquee, renderBlocks | ~800 |
| `strategy_builder_properties.js` | Properties panel, symbol picker, Dunnah Base | ~600 |

Оставшееся в `strategy_builder.js`: init, event listeners, save/load, backtest, templates. Зависимости: передача strategyBlocks, connections в mapBlocksToBackendParams; общие переменные (selectedBlockId, zoom).
