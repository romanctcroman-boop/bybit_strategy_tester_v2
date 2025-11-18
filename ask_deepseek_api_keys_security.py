"""
Консультация с DeepSeek: Безопасное управление API ключами
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Import secure key manager
sys.path.insert(0, str(project_root / "backend"))
from security.key_manager import get_decrypted_key

# DeepSeek API configuration (secure)
DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def ask_deepseek_about_api_keys():
    """Спросить DeepSeek о безопасном управлении API ключами"""
    
    print("\n" + "="*70)
    print("  🤖 КОНСУЛЬТАЦИЯ С DEEPSEEK: API KEYS SECURITY")
    print("="*70 + "\n")
    
    # Подготовка контекста проекта
    project_context = """
# КОНТЕКСТ ПРОЕКТА: Bybit Strategy Tester v2

## Текущая ситуация:
- GitHub Push Protection заблокировал push из-за обнаруженных API ключей
- Найдены ключи: Perplexity API (pplx-...) и DeepSeek API (sk-...)
- Ключи ДЕЙСТВУЮЩИЕ и нужны для работы проекта
- Файлы с ключами были в старых коммитах

## Архитектура проекта:
- Backend: FastAPI (Python)
- Frontend: React + TypeScript (Vite)
- Database: PostgreSQL
- MCP Server: Python (для AI интеграции)
- Deployment: Docker, планируется production на AWS/DigitalOcean

## Места использования API ключей:
1. Backend (backend/services/):
   - Perplexity AI для анализа стратегий
   - DeepSeek для code review и оптимизации
   
2. Frontend (опционально):
   - Может потребоваться для client-side AI features
   
3. MCP Server (mcp-server/):
   - Использует оба ключа для AI reasoning

4. Scripts (scripts/):
   - Утилиты для анализа и тестирования

## Текущее хранение:
- .env файл (не в Git, но локально)
- Hardcoded в некоторых скриптах (проблема!)
- Environment variables в runtime

## Требования:
1. GitHub не должен видеть ключи напрямую (Pass Push Protection)
2. Ключи должны быть зашифрованы в репозитории
3. Модули должны автоматически дешифровывать ключи при запуске
4. UI для управления ключами (Settings в браузере)
5. Возможность ротации ключей без пересборки
6. Безопасность в production (AWS Secrets Manager?)
7. Development environment должен быть удобным
"""

    # Вопросы для DeepSeek
    questions = """
# ВОПРОСЫ:

## 1. Архитектура безопасного хранения
Как правильно реализовать систему шифрования/дешифрования API ключей для:
- Development environment (локальная разработка)
- Staging environment
- Production environment

Какой алгоритм шифрования использовать? Fernet? AES-256?

## 2. Шифрование в Git репозитории
Как зашифровать ключи ДО коммита чтобы:
- GitHub не видел plain text ключи
- Можно было автоматически дешифровать на dev машинах
- Pre-commit hook для автоматического шифрования?

## 3. Управление master key
Где хранить master encryption key:
- Локально (.env?)
- AWS Secrets Manager?
- HashiCorp Vault?
- Azure Key Vault?

Как передавать master key команде разработчиков безопасно?

## 4. Frontend Settings UI
Как реализовать Settings страницу для управления ключами:
- Форма для ввода/изменения API keys
- Шифрование на клиенте перед отправкой на backend?
- Или backend шифрует после получения?
- JWT аутентификация для доступа к Settings

## 5. Backend API для ключей
Структура API endpoints:
```python
POST /api/settings/keys/encrypt - Зашифровать новый ключ
GET  /api/settings/keys/list    - Список ключей (masked)
PUT  /api/settings/keys/rotate  - Ротация ключа
DEL  /api/settings/keys/revoke  - Отзыв ключа
```

Правильно ли? Как обеспечить безопасность?

## 6. Автоматическая дешифровка в модулях
Как сделать чтобы модули автоматически получали расшифрованные ключи:
```python
# Вместо:
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Должно быть:
from backend.security.key_manager import get_decrypted_key
PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
```

## 7. CI/CD и GitHub Actions
Как передавать ключи в GitHub Actions для тестов:
- GitHub Secrets?
- Encrypted secrets в репозитории?
- Как дешифровать в CI pipeline?

## 8. Production deployment
AWS/DigitalOcean best practices:
- AWS Systems Manager Parameter Store?
- Environment variables в Docker?
- Kubernetes Secrets?

## 9. Audit и monitoring
Как логировать использование ключей:
- Кто когда изменил ключ
- Неудачные попытки дешифровки
- Алерты при подозрительной активности

## 10. Migration plan
Пошаговый план миграции от текущего состояния:
1. Создать key_manager модуль
2. Зашифровать существующие ключи
3. Обновить все модули
4. Создать Settings UI
5. Настроить CI/CD
6. Deploy в production

Дай конкретный код и команды для каждого шага!
"""

    full_prompt = f"{project_context}\n\n{questions}"
    
    print("📤 Отправка запроса в DeepSeek API...\n")
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a security expert specializing in API key management, encryption, and secure software development. Provide detailed, production-ready solutions with code examples."
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            temperature=0.3,
            max_tokens=8000
        )
        
        answer = response.choices[0].message.content
        
        # Метрики
        usage = response.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
        
        # Стоимость (DeepSeek: $0.001 per 1K tokens)
        cost = (total_tokens / 1000) * 0.001
        
        print("\n" + "="*70)
        print("  ✅ ОТВЕТ ОТ DEEPSEEK")
        print("="*70 + "\n")
        print(answer)
        print("\n" + "="*70)
        print(f"  📊 Метрики:")
        print(f"     Prompt tokens:     {prompt_tokens:,}")
        print(f"     Completion tokens: {completion_tokens:,}")
        print(f"     Total tokens:      {total_tokens:,}")
        print(f"     Cost:              ${cost:.4f}")
        print("="*70 + "\n")
        
        # Сохранить результат
        result = {
            "timestamp": datetime.now().isoformat(),
            "question": "API Keys Security Architecture",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost,
            "answer": answer
        }
        
        filename = f"DEEPSEEK_API_KEYS_SECURITY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Результат сохранён: {filename}\n")
        
        # Создать markdown версию
        md_filename = filename.replace('.json', '.md')
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write(f"# DeepSeek Consultation: API Keys Security\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Tokens:** {total_tokens:,} (Prompt: {prompt_tokens:,}, Completion: {completion_tokens:,})\n\n")
            f.write(f"**Cost:** ${cost:.4f}\n\n")
            f.write("---\n\n")
            f.write(answer)
        
        print(f"📄 Markdown версия: {md_filename}\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Ошибка при обращении к DeepSeek API: {e}\n")
        return None

if __name__ == "__main__":
    result = ask_deepseek_about_api_keys()
    
    if result:
        print("="*70)
        print("  🎯 СЛЕДУЮЩИЕ ШАГИ:")
        print("="*70)
        print("\n1. Прочитать полный ответ в JSON файле")
        print("2. Реализовать рекомендации DeepSeek")
        print("3. Создать key_manager модуль")
        print("4. Обновить все модули для использования key_manager")
        print("5. Создать Settings UI в frontend")
        print("6. Настроить CI/CD с encrypted secrets")
        print("7. Deploy в production с AWS Secrets Manager\n")
