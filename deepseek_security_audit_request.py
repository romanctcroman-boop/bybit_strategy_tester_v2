#!/usr/bin/env python3
"""
Отправка полного отчёта в DeepSeek для экспертного аудита безопасности,
архитектуры Multi-Agent Channel и составления плана дальнейших работ
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from backend.security.key_manager import get_decrypted_key


def read_tz_documents():
    """Читаем все ТЗ документы"""
    docs = {}
    
    tz_files = [
        (r"d:\PERP\Demo\Техническое задание MCP-оркестратора_1.md", "TZ_MCP_1"),
        (r"d:\PERP\Demo\Техническое задание MCP-оркестратора_2.md", "TZ_MCP_2"),
        (r"d:\PERP\Demo\Расширенное техническое задание_3-1.md", "TZ_3_1"),
        (r"d:\PERP\Demo\Расширенное техническое задание_3-2.md", "TZ_3_2"),
    ]
    
    total_chars = 0
    for file_path, key in tz_files:
        tz_path = Path(file_path)
        if tz_path.exists():
            with open(tz_path, 'r', encoding='utf-8') as f:
                content = f.read()
                docs[key] = content
                total_chars += len(content)
                print(f"✅ {key}: {len(content):,} символов")
        else:
            print(f"❌ Не найден: {file_path}")
    
    print(f"\n📊 Всего загружено: {total_chars:,} символов из {len(docs)} документов")
    return docs


def read_security_implementation():
    """Читаем реализацию безопасности"""
    security_files = {
        "crypto.py": "backend/security/crypto.py",
        "key_manager.py": "backend/security/key_manager.py",
        "master_key_manager.py": "backend/security/master_key_manager.py",
        "audit_logger.py": "backend/security/audit_logger.py",
        "multi_agent_channel.py": "scripts/multi_agent_channel.py",
    }
    
    implementations = {}
    total_lines = 0
    
    for name, path in security_files.items():
        file_path = Path(path)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                implementations[name] = content
                lines = content.count('\n')
                total_lines += lines
                print(f"✅ {name}: {lines} строк")
        else:
            print(f"❌ Не найден: {path}")
    
    print(f"\n📊 Всего кода: {total_lines} строк из {len(implementations)} файлов")
    return implementations


def read_audit_reports():
    """Читаем предыдущие отчёты аудита"""
    reports = {}
    
    report_files = {
        "executive_summary": "EXECUTIVE_SUMMARY_TZ_AUDIT.md",
        "e2e_improvements": "E2E_DEEPSEEK_IMPROVEMENTS.md",
        "multi_agent_status": "VISUAL_ROADMAP.md",
    }
    
    for name, filename in report_files.items():
        file_path = Path(filename)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                reports[name] = f.read()
                print(f"✅ {name}: прочитан")
    
    return reports


def send_to_deepseek(prompt: str) -> dict:
    """Отправка запроса в DeepSeek API"""
    import requests
    
    DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": """Ты - эксперт по безопасности, архитектуре и разработке мультиагентных систем.
Специализируешься на:
- Криптографии и защите API ключей
- Безопасности AI-систем и MCP серверов
- Архитектуре Multi-Agent коммуникации
- Аудите проектов по техническим заданиям
- Best practices для production deployment

Твоя задача: провести глубокий аудит проекта, оценить compliance с ТЗ, выявить риски 
и составить детальный план дальнейших работ с приоритетами."""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 8000
    }
    
    print("\n📤 Отправка запроса в DeepSeek API...")
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Получен ответ от DeepSeek!")
        return result
    else:
        print(f"❌ Ошибка DeepSeek API: {response.status_code}")
        print(response.text)
        return {"error": response.text}


def main():
    print("=" * 80)
    print("🔍 DEEPSEEK SECURITY & ARCHITECTURE AUDIT")
    print("=" * 80)
    print()
    
    # 1. Читаем ТЗ документы
    print("📋 ШАГ 1: Загрузка ТЗ документов")
    print("-" * 80)
    tz_docs = read_tz_documents()
    print()
    
    # 2. Читаем реализацию безопасности
    print("🔒 ШАГ 2: Загрузка кода безопасности")
    print("-" * 80)
    security_code = read_security_implementation()
    print()
    
    # 3. Читаем предыдущие отчёты
    print("📊 ШАГ 3: Загрузка отчётов аудита")
    print("-" * 80)
    audit_reports = read_audit_reports()
    print()
    
    # 4. Формируем запрос для DeepSeek
    print("✍️  ШАГ 4: Формирование запроса для DeepSeek")
    print("-" * 80)
    
    prompt = f"""# ЗАПРОС НА ГЛУБОКИЙ АУДИТ ПРОЕКТА

## 📋 КОНТЕКСТ ПРОЕКТА

**Проект**: Bybit Strategy Tester v2 - мультиагентная платформа для генерации и тестирования торговых стратегий

**Текущая реализация**:
- ✅ Encrypted API Keys Management (AES-256-GCM + PBKDF2)
- ✅ Multi-Agent Communication Channel (DeepSeek ↔ Perplexity)
- ✅ MCP Server (Model Context Protocol)
- ⚠️ Sandbox Execution (требует улучшений)
- ⚠️ Full ТЗ Compliance (частичная реализация)

---

## 🔒 РЕАЛИЗАЦИЯ БЕЗОПАСНОСТИ

### 1. Криптография (backend/security/crypto.py)

```python
{security_code.get('crypto.py', 'NOT FOUND')[:2000]}
...
```

### 2. Key Manager (backend/security/key_manager.py)

```python
{security_code.get('key_manager.py', 'NOT FOUND')[:2000]}
...
```

### 3. Multi-Agent Channel (scripts/multi_agent_channel.py)

```python
{security_code.get('multi_agent_channel.py', 'NOT FOUND')[:2000]}
...
```

**Текущий статус**:
- Commit: 43f69288 - security: Update multi_agent_channel.py to use encrypted API keys
- Ключи зашифрованы: PERPLEXITY_API_KEY (53 chars), DEEPSEEK_API_KEY (35 chars)
- Алгоритм: AES-256-GCM, PBKDF2 (100k iterations)
- Performance: ~1-2ms первая расшифровка, ~1μs кэш

---

## 📝 ТЕХНИЧЕСКИЕ ЗАДАНИЯ

### ТЗ-1: MCP Оркестратор (Часть 1)

{tz_docs.get('TZ_MCP_1', 'NOT LOADED')[:3000]}
...

### ТЗ-2: MCP Оркестратор (Часть 2)

{tz_docs.get('TZ_MCP_2', 'NOT LOADED')[:3000]}
...

### ТЗ-3.1: Мультиагентная лаборатория

{tz_docs.get('TZ_3_1', 'NOT LOADED')[:3000]}
...

### ТЗ-3.2: Детализация компонентов

{tz_docs.get('TZ_3_2', 'NOT LOADED')[:3000]}
...

---

## 📊 ПРЕДЫДУЩИЕ АУДИТЫ

### Executive Summary (предыдущий аудит)

{audit_reports.get('executive_summary', 'NOT LOADED')[:2000]}
...

**Ключевые находки**:
- Оценка: 4.3/10
- До Production: 8-12 недель
- Критические пробелы: Sandbox (0/10), Auth (0/10), Security (3/10)

---

## 🎯 ЗАДАЧИ ДЛЯ DEEPSEEK

### 1. SECURITY AUDIT
Проведи глубокий аудит реализации безопасности:

**Вопросы**:
- ✅ Достаточно ли AES-256-GCM + PBKDF2 (100k iter) для production?
- ✅ Правильно ли реализован KeyManager (singleton, caching)?
- ✅ Есть ли уязвимости в Multi-Agent Channel?
- ❓ Достаточно ли текущей изоляции для AI-generated code?
- ❓ Какие дополнительные security controls нужны?

**Оцени по шкале 0-10**:
- Encryption strength
- Key management
- Access control
- Audit logging
- Incident response

### 2. MULTI-AGENT ARCHITECTURE AUDIT
Оцени реализацию канала связи DeepSeek ↔ Perplexity:

**Вопросы**:
- ✅ Правильно ли реализован collaborative_analysis()?
- ✅ Эффективен ли context sharing (2000 chars)?
- ❓ Нужны ли дополнительные iterations?
- ❓ Как улучшить performance (~14-22 сек/сессия)?
- ❓ Какие метрики отслеживать?

**Оцени**:
- Communication pattern
- Context management
- Error handling
- Scalability
- Cost efficiency

### 3. COMPLIANCE AUDIT
Проверь соответствие всем 4 ТЗ документам:

**Критерии**:
- JSON-RPC 2.0 Protocol (ТЗ-1)
- Redis Streams + Consumer Groups (ТЗ-1)
- Sandbox Execution + Security (ТЗ-2)
- MCP Coordinator (ТЗ-3.1)
- Reasoning Agents (ТЗ-3.1)
- CodeGen + ML Integration (ТЗ-3.2)

**Создай матрицу**:
| Требование | Статус | Оценка | Комментарий |
|------------|--------|--------|-------------|
| ... | ✅/⚠️/❌ | 0-10 | ... |

### 4. ROADMAP & PRIORITIES
Составь детальный план работ:

**Формат**:
```
Phase 1: КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ (срок)
- [ ] Task 1 (приоритет, время)
- [ ] Task 2 (приоритет, время)

Phase 2: АРХИТЕКТУРНЫЕ УЛУЧШЕНИЯ (срок)
- [ ] Task 3 (приоритет, время)
- [ ] Task 4 (приоритет, время)

Phase 3: СТАБИЛИЗАЦИЯ (срок)
- [ ] Task 5 (приоритет, время)
```

**Обязательно укажи**:
- Приоритет (CRITICAL, HIGH, MEDIUM, LOW)
- Оценку времени (часы/дни)
- Dependencies между задачами
- Риски и mitigation strategies

---

## 📈 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

1. **Security Assessment Report**
   - Оценка текущей безопасности (0-10)
   - Список уязвимостей с severity
   - Рекомендации по улучшению

2. **Architecture Review**
   - Оценка Multi-Agent Channel
   - Рекомендации по оптимизации
   - Best practices для production

3. **Compliance Matrix**
   - Таблица соответствия всем ТЗ
   - Процент выполнения по каждому разделу
   - Недостающие компоненты

4. **Detailed Roadmap**
   - 3 фазы работ с конкретными задачами
   - Приоритеты и сроки
   - Оценка времени до production

5. **Risk Assessment**
   - Критические риски (блокируют production)
   - Высокие риски (ограничивают масштабирование)
   - Mitigation strategies для каждого риска

---

## 🔥 ФОКУС АНАЛИЗА

**Особое внимание**:
1. Безопасность sandbox execution для AI-generated code
2. Эффективность Multi-Agent коммуникации
3. Compliance с индустриальными стандартами (OWASP, NIST)
4. Production readiness (SLA, monitoring, alerting)
5. Scalability (horizontal scaling, load balancing)

**Формат ответа**: Детальный markdown отчёт с конкретными примерами кода, 
рекомендациями и actionable plan.

**Время на анализ**: Возьми столько токенов, сколько нужно для полного аудита.

---

Дата запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Запрошено: Roman (GitHub Copilot + DeepSeek consultation)
"""
    
    print(f"📏 Размер запроса: {len(prompt):,} символов")
    print()
    
    # 5. Отправка в DeepSeek
    print("🚀 ШАГ 5: Отправка запроса в DeepSeek API")
    print("-" * 80)
    
    result = send_to_deepseek(prompt)
    
    if "error" not in result:
        # 6. Сохранение результатов
        print()
        print("💾 ШАГ 6: Сохранение результатов")
        print("-" * 80)
        
        # JSON с полными данными
        json_path = Path("DEEPSEEK_SECURITY_AUDIT.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON сохранён: {json_path}")
        
        # Markdown отчёт
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            
            md_path = Path("DEEPSEEK_SECURITY_AUDIT_REPORT.md")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("# 🔍 DeepSeek Security & Architecture Audit\n\n")
                f.write(f"**Дата**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Модель**: deepseek-chat\n")
                f.write(f"**Токенов**: {result.get('usage', {}).get('total_tokens', 'N/A')}\n\n")
                f.write("---\n\n")
                f.write(content)
            
            print(f"✅ Markdown отчёт: {md_path}")
            
            # Статистика
            usage = result.get('usage', {})
            print()
            print("📊 Статистика использования API:")
            print(f"  • Prompt tokens: {usage.get('prompt_tokens', 'N/A'):,}")
            print(f"  • Completion tokens: {usage.get('completion_tokens', 'N/A'):,}")
            print(f"  • Total tokens: {usage.get('total_tokens', 'N/A'):,}")
            
            # Краткий preview
            print()
            print("📝 Предпросмотр ответа (первые 500 символов):")
            print("-" * 80)
            print(content[:500])
            print("...")
            print("-" * 80)
        
        print()
        print("=" * 80)
        print("✅ АУДИТ ЗАВЕРШЁН УСПЕШНО!")
        print("=" * 80)
        print()
        print(f"📂 Результаты сохранены:")
        print(f"  • {json_path}")
        print(f"  • {md_path}")
        print()
        
    else:
        print()
        print("=" * 80)
        print("❌ ОШИБКА ПРИ АУДИТЕ")
        print("=" * 80)
        print(result["error"])


if __name__ == "__main__":
    main()
