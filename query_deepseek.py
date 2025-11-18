"""
Запрос к DeepSeek API для анализа проблемы E2E тестов
"""
import httpx
import json
import os

def query_deepseek(question: str) -> dict:
    """Отправить запрос в DeepSeek API"""
    
    api_key = os.getenv("DEEPSEEK_API_KEY", "sk-1630fbba63c64f88952c16ad33337242")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in E2E testing, Playwright, and backend/frontend integration. Provide detailed technical analysis and actionable recommendations."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "stream": False
    }
    
    print("📤 Отправка запроса в DeepSeek API...")
    print(f"🔑 API Key: {api_key[:15]}...")
    print(f"❓ Вопрос: {question[:100]}...\n")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result
            
    except httpx.TimeoutException:
        return {"error": "Request timed out after 60 seconds"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Вопрос о E2E тестах
    question = """
    **Контекст проблемы:**
    
    Playwright E2E authentication tests падали с ошибкой ECONNREFUSED - backend API на localhost:8000 не был запущен.
    
    **Симптомы:**
    - Vite frontend proxy показывал: "http proxy error: /api/v1/auth/login AggregateError [ECONNREFUSED]"
    - Все тесты с performLogin() падали с TimeoutError
    - 10/16 тестов failed из-за отсутствия backend
    
    **Решение:**
    Добавил backend в playwright.config.ts webServer массив:
    
    ```typescript
    webServer: [
      // Backend API server - ДОБАВЛЕНО
      {
        command: 'cd .. && .venv\\\\Scripts\\\\python.exe -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000',
        url: 'http://localhost:8000/healthz',
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
      },
      // Frontend Vite server
      {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
      },
    ]
    ```
    
    **Результаты:**
    - До исправления: 4/16 passing (25%)
    - После исправления: 14/16 passing (87.5%) ✅
    - 2 теста skipped intentionally (race condition + rate limit whitelist conflict)
    
    **Вопросы:**
    
    1. Это правильный подход для автоматического запуска backend перед E2E тестами?
    2. Какие улучшения можно добавить в playwright.config.ts?
    3. Как обрабатывать ситуацию когда backend долго стартует (миграции БД, etc)?
    4. Стоит ли добавить health check retry logic?
    5. Как правильно тестировать в CI/CD с этим подходом?
    6. Есть ли лучшие практики для управления зависимостями (backend/frontend/database) в E2E тестах?
    """
    
    result = query_deepseek(question)
    
    print("\n" + "=" * 80)
    print("🤖 DeepSeek Response")
    print("=" * 80 + "\n")
    
    if "error" in result:
        print(f"❌ Ошибка: {result['error']}")
    elif "choices" in result:
        answer = result["choices"][0]["message"]["content"]
        print(answer)
        
        # Статистика
        if "usage" in result:
            usage = result["usage"]
            print("\n" + "-" * 80)
            print(f"📊 Статистика:")
            print(f"   Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
            print(f"   Completion tokens: {usage.get('completion_tokens', 'N/A')}")
            print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
    else:
        print("❓ Неожиданный формат ответа:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
