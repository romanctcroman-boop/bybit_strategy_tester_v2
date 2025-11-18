# 📋 Week 3: Integration Tests - План работы

**Дата начала**: 2025-01-29  
**Оценка**: 10 часов  
**Статус**: ⏳ НАЧАТО

---

## 🎯 Цели Week 3

Создать comprehensive integration тесты для проверки работы системы как единого целого:
1. **E2E Tests** - полный цикл работы
2. **Stress Tests** - нагрузочное тестирование
3. **Recovery Tests** - тесты восстановления после сбоев

---

## 📋 Задачи

### 1. E2E Tests (4 часа) ⏳
**Цель**: Проверить полный цикл работы всех компонентов

**Сценарии**:
- [ ] Full test cycle: изменение файла → запуск тестов → DeepSeek анализ → отчёт
- [ ] Audit cycle: триггер → проверка кода → Perplexity анализ → сохранение
- [ ] Health check cycle: мониторинг → проверка компонентов → JSON отчёт
- [ ] Key rotation cycle: проверка expiry → ротация → re-encryption
- [ ] Multi-component interaction: test_watcher + audit_agent + APIs

**Файлы для создания**:
- `tests/integration/test_e2e_test_watcher.py`
- `tests/integration/test_e2e_audit_agent.py`
- `tests/integration/test_e2e_health_check.py`
- `tests/integration/test_e2e_key_rotation.py`

---

### 2. Stress Tests (3 часа) ⏳
**Цель**: Проверить поведение под высокой нагрузкой

**Сценарии**:
- [ ] Parallel file changes (10+ одновременно)
- [ ] High API request rate (rate limiting)
- [ ] Memory leak detection (long-running processes)
- [ ] Concurrent async operations (SafeAsyncBridge)
- [ ] Database stress (multiple connections)

**Файлы для создания**:
- `tests/stress/test_parallel_execution.py`
- `tests/stress/test_api_rate_limits.py`
- `tests/stress/test_memory_leaks.py`
- `tests/stress/test_concurrent_operations.py`

---

### 3. Recovery Tests (3 часа) ⏳
**Цель**: Проверить recovery после различных failure scenarios

**Сценарии**:
- [ ] Component crash recovery (PM2 restart)
- [ ] Network failure (API unavailable)
- [ ] Disk full scenario
- [ ] Database connection loss
- [ ] Invalid/corrupted config files
- [ ] API key rotation during operation

**Файлы для создания**:
- `tests/recovery/test_component_crash.py`
- `tests/recovery/test_network_failure.py`
- `tests/recovery/test_disk_full.py`
- `tests/recovery/test_invalid_config.py`

---

## 📊 Метрики успеха

### Coverage:
- [ ] E2E tests: 100% critical paths
- [ ] Stress tests: Pass без memory leaks
- [ ] Recovery tests: Graceful degradation

### Performance:
- [ ] E2E cycle: < 30 seconds
- [ ] Stress: Handle 10+ parallel operations
- [ ] Recovery: < 5 seconds для restart

### Reliability:
- [ ] All tests pass consistently (3 runs)
- [ ] No flaky tests
- [ ] Clear error messages

---

## 🛠️ Необходимые инструменты

### Для E2E:
```bash
pip install pytest-asyncio pytest-timeout
```

### Для Stress:
```bash
pip install memory-profiler psutil
```

### Для Recovery:
```bash
# Моки для API failures
pip install responses aioresponses
```

---

## 📝 Текущий прогресс

```
Week 3: Integration Tests
├── [⏳] E2E Tests (0%)
│   ├── [ ] test_watcher full cycle
│   ├── [ ] audit_agent full cycle
│   ├── [ ] health_check cycle
│   └── [ ] key_rotation cycle
│
├── [⏳] Stress Tests (0%)
│   ├── [ ] Parallel execution
│   ├── [ ] API rate limits
│   ├── [ ] Memory leaks
│   └── [ ] Concurrent operations
│
└── [⏳] Recovery Tests (0%)
    ├── [ ] Component crash
    ├── [ ] Network failure
    ├── [ ] Disk full
    └── [ ] Invalid config

Overall: 0% complete
```

---

**Next**: Start with E2E test_watcher cycle
