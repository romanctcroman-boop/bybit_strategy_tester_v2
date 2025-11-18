# 🤖 DeepSeek AI Robot - Полная документация

**Версия:** 1.0.0  
**Дата:** 8 ноября 2025  
**Статус:** Production Ready

---

## 📋 Содержание

1. [Введение](#введение)
2. [Архитектура](#архитектура)
3. [Установка](#установка)
4. [Быстрый старт](#быстрый-старт)
5. [Конфигурация](#конфигурация)
6. [Использование](#использование)
7. [AI Интеграции](#ai-интеграции)
8. [API Reference](#api-reference)
9. [Примеры](#примеры)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Введение

**DeepSeek AI Robot** - автономный агент для анализа и улучшения кода с использованием трёх AI систем:

- **DeepSeek** - глубокий анализ и генерация исправлений
- **Perplexity** - исследования и best practices
- **Copilot** - валидация и дополнительные улучшения

### Ключевые возможности:

✅ **Циклический анализ** - повторяет Analyze → Fix → Test до 100%  
✅ **Self-validation** - проверяет свои изменения тестами  
✅ **Autonomous operation** - работает без вмешательства  
✅ **Multi-AI collaboration** - консенсус от 3 AI систем  
✅ **Extended permissions** - файлы, git, тесты, DB  
✅ **Quality metrics** - расчёт качества 0-100%  
✅ **Human escalation** - автоматическая эскалация при проблемах

---

## 🏗️ Архитектура

```
DeepSeek AI Robot
├── robot.py              # Core: циклический анализ и управление
├── ai_integrations.py    # AI клиенты: DeepSeek, Perplexity, Copilot
├── ARCHITECTURE.md       # Детальная архитектура
└── README.md             # Эта документация
```

### Компоненты:

```
┌─────────────────────────────────────────────┐
│         DeepSeek AI Robot                   │
│                                             │
│  Analyzer → Executor → Validator           │
│        ↓         ↓          ↓               │
│     Quality Engine (до 100%)               │
│        ↓         ↓          ↓               │
│  DeepSeek   Copilot   Perplexity          │
└─────────────────────────────────────────────┘
```

---

## 📦 Установка

### Требования:

- Python 3.10+
- pytest, mypy, black (для валидации)
- API ключи: DeepSeek, Perplexity

### Шаг 1: Установка зависимостей

```bash
pip install httpx python-dotenv
```

### Шаг 2: Настройка API ключей

Создайте `.env` файл:

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
PERPLEXITY_API_KEY=pplx-your-perplexity-key
```

### Шаг 3: Установка инструментов

```bash
pip install pytest mypy black isort
```

---

## 🚀 Быстрый старт

### Пример 1: Базовое использование

```python
from pathlib import Path
from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel

# Создаём робота
robot = DeepSeekRobot(
    project_root=Path.cwd(),
    autonomy_level=AutonomyLevel.SEMI_AUTO
)

# Запускаем improvement loop
result = await robot.run_until_perfect(
    target_quality=95.0,
    max_iterations=5
)

print(f"Final quality: {result['final_quality']}%")
```

### Пример 2: Одиночный цикл

```python
# Запустить только 1 цикл анализа
cycle_result = await robot.run_improvement_cycle()

print(f"Quality improvement: {cycle_result.quality_after - cycle_result.quality_before:+.1f}%")
```

### Пример 3: AI Collaboration

```python
from automation.deepseek_robot.ai_integrations import AICollaborationOrchestrator

orchestrator = AICollaborationOrchestrator(Path.cwd())

# Совместный анализ проблемы
result = await orchestrator.collaborative_analysis(
    code="def divide(a, b): return a / b",
    problem="Handle division by zero",
    context="Python 3.13, production code"
)

print(f"DeepSeek fix: {result['deepseek_fix']}")
print(f"Perplexity insights: {result['perplexity_insights']}")
```

---

## ⚙️ Конфигурация

### Файл `robot_config.json`:

```json
{
  "autonomy_level": "semi-auto",
  "target_quality": 95,
  "max_iterations": 5,
  
  "ai_providers": {
    "deepseek": {
      "model": "deepseek-coder",
      "temperature": 0.1
    },
    "perplexity": {
      "model": "sonar-pro"
    }
  },
  
  "quality_metrics": {
    "code_quality_weight": 0.4,
    "test_quality_weight": 0.3,
    "architecture_weight": 0.2,
    "documentation_weight": 0.1
  },
  
  "tools": {
    "pytest": {
      "enabled": true,
      "args": ["-v", "--tb=short"]
    },
    "mypy": {
      "enabled": true
    },
    "black": {
      "enabled": true,
      "line_length": 100
    },
    "isort": {
      "enabled": true
    }
  }
}
```

### Уровни автономности:

```python
# MANUAL: требует подтверждения на каждый шаг
robot = DeepSeekRobot(
    project_root=Path.cwd(),
    autonomy_level=AutonomyLevel.MANUAL
)

# SEMI_AUTO: batch approval (показывает план, ждёт одобрения)
robot = DeepSeekRobot(
    project_root=Path.cwd(),
    autonomy_level=AutonomyLevel.SEMI_AUTO
)

# FULL_AUTO: полная автономность
robot = DeepSeekRobot(
    project_root=Path.cwd(),
    autonomy_level=AutonomyLevel.FULL_AUTO
)
```

---

## 💻 Использование

### Use Case 1: Ежедневная оптимизация

```python
async def daily_optimization():
    robot = DeepSeekRobot(Path.cwd())
    
    result = await robot.run_until_perfect(
        target_quality=90,  # Не 100% для ежедневной работы
        max_iterations=3
    )
    
    if result['success']:
        print("✅ Code optimized!")
    else:
        print("⚠️  Manual intervention needed")
```

### Use Case 2: Pre-deploy проверка

```python
async def pre_deploy_check():
    robot = DeepSeekRobot(
        project_root=Path.cwd(),
        autonomy_level=AutonomyLevel.FULL_AUTO
    )
    
    result = await robot.run_until_perfect(
        target_quality=100,  # Обязательно 100% перед деплоем
        max_iterations=10
    )
    
    if result['final_quality'] < 100:
        raise RuntimeError("Deploy blocked: quality < 100%")
    
    print("✅ Ready for deploy!")
```

### Use Case 3: Рефакторинг legacy кода

```python
async def refactor_legacy():
    robot = DeepSeekRobot(Path("src/legacy"))
    
    # Установим цель 95% (legacy код сложно довести до 100%)
    result = await robot.run_until_perfect(
        target_quality=95,
        max_iterations=10
    )
    
    print(f"Improvement: {result['final_quality'] - result['initial_quality']:.1f}%")
```

---

## 🤝 AI Интеграции

### DeepSeek API

**Использование:**
```python
from automation.deepseek_robot.ai_integrations import DeepSeekClient

deepseek = DeepSeekClient(
    model="deepseek-coder",
    temperature=0.1
)

# Анализ кода
result = await deepseek.analyze_code(
    code="...",
    instruction="Find bugs and suggest fixes"
)

# Генерация исправления
fix = await deepseek.generate_fix(
    problem_description="NullPointerException",
    original_code="..."
)
```

**Модели:**
- `deepseek-coder`: лучшая для кода
- `deepseek-chat`: универсальная

---

### Perplexity API

**Использование:**
```python
from automation.deepseek_robot.ai_integrations import PerplexityClient

perplexity = PerplexityClient(model="sonar-pro")

# Поиск информации
result = await perplexity.search(
    query="Best practices for async Python"
)

# Исследование best practices
best_practices = await perplexity.research_best_practices(
    topic="error handling",
    language="python"
)

# Поиск решения проблемы
solution = await perplexity.find_solution(
    problem="ImportError: No module named 'httpx'",
    context="Python 3.13, venv"
)
```

**Модели:**
- `sonar`: быстрая с интернетом
- `sonar-pro`: мощная с интернетом

---

### Copilot Integration

**Использование:**
```python
from automation.deepseek_robot.ai_integrations import CopilotIntegration

copilot = CopilotIntegration(Path.cwd())

# Запрос валидации
request = await copilot.request_validation(
    original_code="...",
    fixed_code="...",
    problem_description="..."
)
# Создаёт файл .copilot/validation_request.json
# Откройте в VS Code для review

# Запрос идей по рефакторингу
ideas = await copilot.request_refactoring_ideas(
    code="...",
    context="Improve performance"
)
```

---

### Collaborative Analysis

**Использование всех AI вместе:**
```python
from automation.deepseek_robot.ai_integrations import AICollaborationOrchestrator

orchestrator = AICollaborationOrchestrator(Path.cwd())

result = await orchestrator.collaborative_analysis(
    code=buggy_code,
    problem="Memory leak in event loop",
    context="asyncio, Python 3.13"
)

# Результат:
# - DeepSeek: анализ + fix
# - Perplexity: best practices + insights
# - Copilot: валидация (pending manual review)
```

---

## 📚 API Reference

### DeepSeekRobot

```python
class DeepSeekRobot:
    def __init__(
        self,
        project_root: Path,
        config_path: Optional[Path] = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.SEMI_AUTO
    ):
        """Инициализация робота"""
    
    async def run_improvement_cycle(self) -> CycleResult:
        """Запуск одного цикла Analyze → Fix → Test"""
    
    async def run_until_perfect(
        self,
        target_quality: float = 100.0,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """Запуск циклов до достижения target_quality"""
    
    async def analyze_project(self) -> List[Problem]:
        """Анализ проекта: поиск проблем"""
    
    async def generate_fixes(self, problems: List[Problem]) -> List[Fix]:
        """Генерация исправлений для проблем"""
    
    async def apply_fixes(self, fixes: List[Fix]) -> Tuple[int, int]:
        """Применение исправлений"""
    
    async def validate_changes(self) -> Dict[str, Any]:
        """Валидация через тесты и линтеры"""
```

### QualityMetrics

```python
@dataclass
class QualityMetrics:
    code_quality: float = 0.0       # 0-100, вес 40%
    test_quality: float = 0.0       # 0-100, вес 30%
    architecture_quality: float = 0.0  # 0-100, вес 20%
    documentation_quality: float = 0.0  # 0-100, вес 10%
    
    @property
    def total(self) -> float:
        """Общее качество 0-100"""
```

---

## 🎨 Примеры

### Пример 1: Проверка кода перед коммитом

```python
#!/usr/bin/env python
"""Pre-commit hook: проверка качества кода"""

import asyncio
from pathlib import Path
from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel

async def pre_commit_check():
    robot = DeepSeekRobot(
        project_root=Path.cwd(),
        autonomy_level=AutonomyLevel.FULL_AUTO
    )
    
    # Один цикл проверки
    result = await robot.run_improvement_cycle()
    
    if result.quality_after < 90:
        print(f"❌ Quality too low: {result.quality_after:.1f}%")
        print("   Fix issues before committing!")
        return False
    
    print(f"✅ Quality check passed: {result.quality_after:.1f}%")
    return True

if __name__ == "__main__":
    success = asyncio.run(pre_commit_check())
    exit(0 if success else 1)
```

### Пример 2: CI/CD Integration

```yaml
# .github/workflows/quality-check.yml
name: Code Quality Check

on: [push, pull_request]

jobs:
  quality-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          pip install httpx python-dotenv pytest mypy black
      
      - name: Run DeepSeek Robot
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          python -c "
          import asyncio
          from pathlib import Path
          from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel
          
          async def check():
              robot = DeepSeekRobot(Path.cwd(), autonomy_level=AutonomyLevel.FULL_AUTO)
              result = await robot.run_until_perfect(target_quality=95, max_iterations=3)
              exit(0 if result['success'] else 1)
          
          asyncio.run(check())
          "
```

---

## 🔧 Troubleshooting

### Проблема: "DEEPSEEK_API_KEY not found"

**Решение:**
```bash
# Проверьте .env файл
cat .env | grep DEEPSEEK_API_KEY

# Или установите напрямую
export DEEPSEEK_API_KEY="sk-your-key"
```

### Проблема: "pytest not found"

**Решение:**
```bash
pip install pytest mypy black isort
```

### Проблема: Robot застрял (no progress)

**Признаки:**
- Качество не растёт 3 цикла подряд
- Робот эскалирует к человеку

**Решение:**
1. Проверьте логи: `robot_audit.log`
2. Посмотрите на проблемы: `robot.current_problems`
3. Ручная правка сложных случаев
4. Перезапуск робота

### Проблема: Тесты падают после исправлений

**Причина:** DeepSeek сделал неправильное исправление

**Решение:**
- Robot автоматически откатывает (rollback) при падении тестов
- Проверьте `.robot_backups/` для ручного восстановления

---

## 📈 Метрики качества

### Code Quality (40%)
- ✅ Линтеры: 0 errors, <10 warnings
- ✅ Type hints: >90% coverage
- ✅ Complexity: <10 cyclomatic
- ✅ Duplication: <5%

### Test Quality (30%)
- ✅ Tests passing: 100%
- ✅ Coverage: >80%
- ✅ Test speed: <30s для unit tests

### Architecture Quality (20%)
- ✅ Dependencies: No cycles
- ✅ Coupling: <30%
- ✅ Cohesion: >70%

### Documentation Quality (10%)
- ✅ Docstrings: >90%
- ✅ README: Complete
- ✅ Comments: Clear & updated

---

## 🚀 Roadmap

### v1.0 (Current) ✅
- Core robot с циклическим анализом
- Интеграция DeepSeek, Perplexity, Copilot
- Quality metrics 0-100%
- Autonomous operation

### v1.1 (Planning) 🔜
- VS Code extension integration
- Real-time Copilot collaboration
- Advanced rollback strategies
- ML-based prioritization

### v2.0 (Future) 🔮
- Multi-project orchestration
- Predictive analysis
- Auto-scaling optimizations
- Team collaboration features

---

## 📞 Поддержка

- **Issues:** GitHub Issues
- **Docs:** `automation/deepseek_robot/ARCHITECTURE.md`
- **Examples:** `automation/deepseek_robot/examples/`

---

**Создано:** DeepSeek AI + GitHub Copilot + Perplexity AI  
**Лицензия:** MIT  
**Версия:** 1.0.0
