# Шаг 1.1: Инвентаризация MCP инструментов

**Дата:** 2026-02-26  
**Статус:** ✅ Завершён  
**Задача:** P0-4 — Circuit breakers на MCP инструменты

---

## Цель

Провести полную инвентаризацию всех MCP инструментов в проекте для последующего назначения per-tool circuit breakers.

---

## Методология

1. Поиск всех файлов с регистрацией MCP инструментов
2. Извлечение имён инструментов из декораторов `@mcp.tool()`
3. Группировка по категориям
4. Подсчёт количества

---

## Результаты

### Найденные файлы с инструментами

| Файл | Путь | Инструментов |
|------|------|-------------|
| `indicators.py` | `backend/agents/mcp/tools/` | 6 |
| `risk.py` | `backend/agents/mcp/tools/` | 2 |
| `backtest.py` | `backend/agents/mcp/tools/` | 2 |
| `strategy.py` | `backend/agents/mcp/tools/` | 3 |
| `strategy_builder.py` | `backend/agents/mcp/tools/` | 52 |
| `memory.py` | `backend/agents/mcp/tools/` | 5 |
| `system.py` | `backend/agents/mcp/tools/` | 3 |
| `agent_tools.py` | `backend/api/mcp/tools/` | 3 |
| `file_tools.py` | `backend/api/mcp/tools/` | 3 |
| **ВСЕГО** | | **79** |

---

## Полный список инструментов

### Категория 1: Индикаторы (6)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `calculate_rsi` | `indicators.py` | prices, period |
| `calculate_macd` | `indicators.py` | prices, fast_period, slow_period, signal_period |
| `calculate_bollinger_bands` | `indicators.py` | prices, period, std_dev |
| `calculate_atr` | `indicators.py` | high, low, close, period |
| `analyze_trend` | `indicators.py` | prices, high, low |
| `find_support_resistance` | `indicators.py` | high, low, close |

### Категория 2: Риски (2)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `calculate_position_size` | `risk.py` | account_size, risk_percent, stop_loss_percent |
| `calculate_risk_reward` | `risk.py` | entry_price, stop_loss, take_profit |

### Категория 3: Бэктестирование (2)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `run_backtest` | `backtest.py` | symbol, interval, start_date, end_date, strategy_params |
| `get_backtest_metrics` | `backtest.py` | backtest_id |

### Категория 4: Стратегии (3)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `list_strategies` | `strategy.py` | — |
| `validate_strategy` | `strategy.py` | strategy_params |
| `evolve_strategy` | `strategy.py` | strategy_id, evolution_params |

### Категория 5: Strategy Builder (52)

**CRUD операции:**
- `builder_create_strategy`
- `builder_get_strategy`
- `builder_update_strategy`
- `builder_delete_strategy`
- `builder_list_strategies`

**Блоки:**
- `builder_add_block`
- `builder_remove_block`
- `builder_update_block`
- `builder_get_block`
- `builder_connect_blocks`
- `builder_disconnect_blocks`

**Бэктест:**
- `builder_run_backtest`
- `builder_get_backtest_status`
- `builder_get_backtest_results`
- `builder_cancel_backtest`

**Код:**
- `builder_generate_code`
- `builder_export_code`

**Версионирование:**
- `builder_get_versions`
- `builder_revert_version`
- `builder_delete_version`

**Индикаторы (20 блоков):**
- `builder_add_rsi_block`
- `builder_add_macd_block`
- `builder_add_bollinger_block`
- `builder_add_atr_block`
- `builder_add_sma_block`
- `builder_add_ema_block`
- `builder_add_stochastic_block`
- `builder_add_supertrend_block`
- `builder_add_qqe_block`
- `builder_add_adx_block`
- `builder_add_cci_block`
- `builder_add_mfi_block`
- `builder_add_williams_r_block`
- `builder_add_obv_block`
- `builder_add_cmf_block`
- `builder_add_vwap_block`
- `builder_add_pivot_points_block`
- `builder_add_fibonacci_block`
- `builder_add_ichimoku_block`
- `builder_add_parabolic_sar_block`

**Условия (10 блоков):**
- `builder_add_crossover_block`
- `builder_add_crossunder_block`
- `builder_add_greater_than_block`
- `builder_add_less_than_block`
- `builder_add_between_block`
- `builder_add_and_condition_block`
- `builder_add_or_condition_block`
- `builder_add_not_condition_block`
- `builder_add_time_filter_block`
- `builder_add_volatility_filter_block`

**Выходы (7 блоков):**
- `builder_add_stop_loss_block`
- `builder_add_take_profit_block`
- `builder_add_trailing_stop_block`
- `builder_add_atr_exit_block`
- `builder_add_multi_tp_block`
- `builder_add_time_exit_block`
- `builder_add_signal_exit_block`

### Категория 6: Память (5)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `memory_store` | `memory.py` | content, category, metadata |
| `memory_recall` | `memory.py` | query, limit, category |
| `memory_get_stats` | `memory.py` | — |
| `memory_consolidate` | `memory.py` | from_category, to_category |
| `memory_forget` | `memory.py` | category, older_than_days |

### Категория 7: Система (3)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `check_system_health` | `system.py` | — |
| `generate_backtest_report` | `system.py` | backtest_id, format |
| `log_agent_action` | `system.py` | agent_id, action, details |

### Категория 8: Агент-агент (3)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `mcp_agent_to_agent_send_to_deepseek` | `agent_tools.py` | content, conversation_id, context |
| `mcp_agent_to_agent_send_to_perplexity` | `agent_tools.py` | content, conversation_id, context |
| `mcp_agent_to_agent_get_consensus` | `agent_tools.py` | question, agents, max_rounds |

### Категория 9: Файлы (3)

| Инструмент | Файл | Параметры |
|------------|------|-----------|
| `mcp_read_project_file` | `file_tools.py` | file_path, max_size_kb |
| `mcp_list_project_structure` | `file_tools.py` | max_depth, include_patterns |
| `mcp_analyze_code_quality` | `file_tools.py` | file_path, checks |

---

## Статистика

### По категориям

```
Strategy Builder:  ████████████████████████████████████████████  52 (66%)
Indicators:        █████████                                     6 (8%)
Memory:            █████                                           5 (6%)
System:            ███                                             3 (4%)
Agent-to-Agent:    ███                                             3 (4%)
File Tools:        ███                                             3 (4%)
Strategies:        ███                                             3 (4%)
Backtest:          ██                                              2 (3%)
Risk:              ██                                              2 (3%)
```

### По критичности

| Критичность | Категории | Инструментов | Обоснование |
|-------------|-----------|--------------|-------------|
| **Высокая** | Agent-to-Agent, Backtest | 5 | Прямые вызовы AI API, долгие операции |
| **Средняя** | Strategy Builder, System, Memory | 60 | Внутренние операции, средняя длительность |
| **Низкая** | Indicators, Risk, Files, Strategies | 14 | Быстрые вычисления, файлы |

---

## Выводы

1. **79 инструментов** — требуется автоматизация регистрации circuit breakers
2. **Strategy Builder доминирует** (52 инструмента, 66%) — возможно группировать по категориям
3. **Разная критичность** — разные пороги circuit breaker для категорий

---

## Рекомендации для Шага 2.1

1. **Автоматическая регистрация** — создать функцию `register_per_tool_breakers()`
2. **Группировка по категориям** — назначать breaker на категорию, а не на инструмент
3. **Разные пороги** — High: 3 failures, Medium: 5 failures, Low: 10 failures
4. **Мониторинг** — экспортировать метрики в Prometheus

---

## Следующий шаг

➡️ **Шаг 2.1: Создать реестр circuit breakers**

**Файл:** `backend/mcp/mcp_integration.py`  
**Изменения:** 
- Добавить `self.circuit_breakers: dict[str, CircuitBreaker]`
- Добавить `self.breaker_categories: dict[str, str]`
- Создать `register_per_tool_breakers()`

---

*Отчёт о шаге 1.1 завершён: 2026-02-26*
