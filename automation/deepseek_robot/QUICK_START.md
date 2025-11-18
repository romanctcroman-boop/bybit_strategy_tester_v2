# ⚡ Quick Start Guide - Advanced DeepSeek Agent

## 🎯 За 5 минут до запуска!

### Шаг 1: Установка зависимостей (1 минута)

```bash
cd d:\bybit_strategy_tester_v2
.venv\Scripts\activate

pip install numpy scikit-learn
```

**Проверка:**
```bash
python -c "import numpy, sklearn; print('✅ Dependencies OK')"
```

---

### Шаг 2: Настройка API ключей (2 минуты)

**Открыть:** `.env`

**Добавить:**
```env
# DeepSeek API Keys (минимум 4, максимум 8)
DEEPSEEK_API_KEY_1=your_deepseek_key_1_here
DEEPSEEK_API_KEY_2=your_deepseek_key_2_here
DEEPSEEK_API_KEY_3=your_deepseek_key_3_here
DEEPSEEK_API_KEY_4=your_deepseek_key_4_here

# Optional (для 8 ключей)
DEEPSEEK_API_KEY_5=your_deepseek_key_5_here
DEEPSEEK_API_KEY_6=your_deepseek_key_6_here
DEEPSEEK_API_KEY_7=your_deepseek_key_7_here
DEEPSEEK_API_KEY_8=your_deepseek_key_8_here

# Cache settings (можно оставить по умолчанию)
CACHE_MAX_SIZE=1000
CACHE_TTL_SECONDS=3600
CACHE_DIR=.cache/deepseek

# Performance (4 для 4 ключей, 8 для 8 ключей)
MAX_PARALLEL_WORKERS=4
RATE_LIMIT_PER_KEY=60
```

**Проверка:**
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); keys = [os.getenv(f'DEEPSEEK_API_KEY_{i}') for i in range(1,9) if os.getenv(f'DEEPSEEK_API_KEY_{i}')]; print(f'✅ Found {len(keys)} API keys')"
```

---

### Шаг 3: Запуск demo (2 минуты)

```bash
$env:PYTHONPATH = "D:\bybit_strategy_tester_v2"
D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe automation/deepseek_robot/demo_advanced_architecture.py
```

**Ожидаемый результат:**
```
🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯
  ADVANCED ARCHITECTURE DEMO SUITE
🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯

================================================================================
  DEMO 1: API Key Pool
================================================================================
✅ API Key Pool initialized
   • Keys: 4
   • Rate limit: 60 req/min per key
   • Total capacity: 240 req/min

... (5 more demos) ...

================================================================================
  DEMO SUITE COMPLETED
================================================================================
✅ All 6 demos executed successfully!
🚀 Ready for production integration!
```

---

## 🚀 Что дальше?

### Option A: Интеграция в robot.py (рекомендуется)

**Время:** 5-8 часов  
**Гайд:** `INTEGRATION_PLAN.md`

```bash
# Следовать шагам из INTEGRATION_PLAN.md
# Phase 1: Подготовка (1-2 часа)
# Phase 2: Интеграция (2-3 часа)
# Phase 3: Тестирование (1-2 часа)
# Phase 4: Мониторинг (30 минут)
```

### Option B: Использование standalone

**Время:** 10 минут

```python
# Создать файл: my_analysis.py

import asyncio
from pathlib import Path
from automation.deepseek_robot.advanced_architecture import (
    AdvancedWorkflowOrchestrator
)

async def main():
    # Ваши API ключи
    deepseek_keys = [
        "key1",
        "key2",
        "key3",
        "key4"
    ]
    
    # Создать orchestrator
    orchestrator = AdvancedWorkflowOrchestrator(
        deepseek_keys=deepseek_keys,
        perplexity_key="your_perplexity_key"
    )
    
    # Ваши задачи
    tasks = [
        {"query": "analyze robot.py for bugs"},
        {"query": "check performance issues"},
        {"query": "review security vulnerabilities"},
    ]
    
    # Запуск workflow
    results = await orchestrator.execute_workflow(tasks)
    
    print(f"✅ Completed in {results['total_duration']:.2f}s")
    print(f"Cache hit rate: {orchestrator.cache.get_stats()['hit_rate']}")

if __name__ == "__main__":
    asyncio.run(main())
```

Запуск:
```bash
python my_analysis.py
```

---

## 📚 Документация

### Для начинающих
- **IMPLEMENTATION_COMPLETE.md** - Обзор всей реализации
- **Этот файл** - Quick start за 5 минут

### Для разработчиков
- **ADVANCED_ARCHITECTURE.md** - Полная документация (1200+ строк)
- **INTEGRATION_PLAN.md** - План интеграции в robot.py
- **advanced_architecture.py** - Исходный код (700 строк)

### Примеры
- **demo_advanced_architecture.py** - 6 демо всех компонентов

---

## 🐛 Troubleshooting

### Проблема: ModuleNotFoundError: No module named 'automation'

**Решение:**
```bash
$env:PYTHONPATH = "D:\bybit_strategy_tester_v2"
# Или добавить в начало скрипта:
import sys
sys.path.insert(0, "D:/bybit_strategy_tester_v2")
```

### Проблема: ImportError: numpy not found

**Решение:**
```bash
pip install numpy scikit-learn
```

### Проблема: FileNotFoundError: .cache/demo

**Решение:**
```bash
mkdir -p .cache/demo
# Или в Python:
from pathlib import Path
Path(".cache/demo").mkdir(parents=True, exist_ok=True)
```

### Проблема: No DeepSeek API keys found

**Решение:**
Проверить `.env`:
```bash
cat .env | grep DEEPSEEK_API_KEY
# Должно показать минимум 4 ключа
```

---

## ✅ Checklist перед использованием

- [ ] Python 3.10+ установлен
- [ ] Virtual environment активирован
- [ ] `numpy` и `scikit-learn` установлены
- [ ] Минимум 4 API ключа в `.env`
- [ ] Demo запущена успешно
- [ ] Понимание workflow: DeepSeek → Perplexity → DeepSeek → Copilot

---

## 🎯 Ключевые возможности

1. **Multi-API Keys:** 4-8 ключей для parallel execution
2. **Intelligent Cache:** ML-based с semantic search
3. **Context Persistence:** Agent "помнит" историю
4. **4-Stage Workflow:** DeepSeek → Perplexity → DeepSeek → Copilot
5. **Performance:** 4-8x speedup (parallel) + 100-200x (cache)

---

## 💡 Pro Tips

### Tip 1: Увеличение производительности
```env
# Если у вас 8 ключей:
MAX_PARALLEL_WORKERS=8
# Speedup: до 8x!
```

### Tip 2: Настройка кэша
```env
# Для больших проектов:
CACHE_MAX_SIZE=2000
CACHE_TTL_SECONDS=7200  # 2 часа
```

### Tip 3: Semantic search threshold
```python
# В коде:
similar = cache.find_similar(query, threshold=0.85)
# 0.7 - более мягкий (больше matches)
# 0.9 - более строгий (меньше matches)
```

### Tip 4: Мониторинг
```python
# Периодически проверять метрики:
stats = orchestrator.cache.get_stats()
print(f"Hit rate: {stats['hit_rate']}")
print(f"Size: {stats['size']}/{stats['max_size']}")

pool_stats = orchestrator.deepseek_executor.key_pool.get_stats()
print(f"Total requests: {pool_stats['total_requests']}")
print(f"Errors: {pool_stats['total_errors']}")
```

---

## 🚀 Готово!

Вы готовы использовать advanced architecture!

**Следующие шаги:**
1. ✅ Запустить demo (если ещё не сделали)
2. 📖 Прочитать ADVANCED_ARCHITECTURE.md для деталей
3. 🔧 Интегрировать в robot.py (INTEGRATION_PLAN.md)
4. 🎯 Использовать в production!

**Вопросы?** Смотри документацию:
- IMPLEMENTATION_COMPLETE.md
- ADVANCED_ARCHITECTURE.md
- INTEGRATION_PLAN.md

**Удачи!** 🎉
