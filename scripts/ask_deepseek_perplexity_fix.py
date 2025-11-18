#!/usr/bin/env python3
"""
DeepSeek: Помощь в диагностике проблемы с Perplexity API
"""

import os
import requests
import json
from pathlib import Path

# API Keys
DEEPSEEK_API_KEY = "sk-2d9ac5c9d6454757951c4c037b9dcdef"
PERPLEXITY_API_KEY = "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"

def call_deepseek(prompt: str) -> str:
    """Вызов DeepSeek для помощи"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "Ты эксперт по REST APIs и debugging. Помоги решить проблему с API запросом."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }
    
    print("📤 Спрашиваем DeepSeek...")
    
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return f"Error {response.status_code}: {response.text}"

def main():
    print("=" * 80)
    print("DEEPSEEK: ДИАГНОСТИКА PERPLEXITY API ПРОБЛЕМЫ")
    print("=" * 80)
    print()
    
    # Подробное описание проблемы
    problem_description = f"""У меня проблема с Perplexity API. Помоги найти решение.

**СИМПТОМЫ:**
- Status Code: 401 Unauthorized
- Response: HTML страница с "401 Authorization Required"
- Server: cloudflare (openresty/1.27.4)
- Есть Set-Cookie с __cf_bm (Cloudflare bot management)

**МОЙ КОД:**
```python
headers = {{
    "Authorization": "Bearer {PERPLEXITY_API_KEY[:20]}...",
    "Content-Type": "application/json"
}}

payload = {{
    "model": "sonar-pro",
    "messages": [
        {{"role": "user", "content": "Hello, can you help me?"}}
    ]
}}

response = requests.post(
    "https://api.perplexity.ai/chat/completions",
    headers=headers,
    json=payload,
    timeout=30
)
# Результат: 401 Unauthorized
```

**КОНТЕКСТ:**
- API ключ: {PERPLEXITY_API_KEY[:30]}...
- Endpoint: https://api.perplexity.ai/chat/completions
- Раньше API работал нормально
- Пользователь НЕ в России
- DeepSeek API работает отлично с теми же настройками

**ЧТО УЖЕ ПРОБОВАЛ:**
1. Разные модели (sonar, sonar-pro)
2. Минимальный payload
3. Разные timeout значения
4. Проверил API ключ (скопирован правильно)

**ВОПРОСЫ:**
1. Почему Cloudflare возвращает 401 вместо прямого API ответа?
2. Может быть проблема с форматом Authorization header?
3. Нужны ли дополнительные headers для Perplexity API?
4. Может быть Perplexity изменил API endpoint или формат?
5. Что означает __cf_bm cookie (bot management)?

**ЗАДАЧА:**
Дай конкретные рекомендации по исправлению проблемы. Если нужно изменить код - покажи рабочий пример."""

    # Спрашиваем DeepSeek
    answer = call_deepseek(problem_description)
    
    print()
    print("=" * 80)
    print("ОТВЕТ DEEPSEEK:")
    print("=" * 80)
    print()
    print(answer)
    print()
    print("=" * 80)
    
    # Сохраняем ответ
    report_path = Path("DEEPSEEK_PERPLEXITY_FIX.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# DeepSeek: Диагностика проблемы Perplexity API\n\n")
        f.write(f"**Дата:** 2025-11-01\n\n")
        f.write("## Проблема\n\n")
        f.write("```\n")
        f.write("Status Code: 401 Unauthorized\n")
        f.write("Response: Cloudflare HTML page\n")
        f.write("```\n\n")
        f.write("## Решение от DeepSeek\n\n")
        f.write(answer)
    
    print(f"📄 Ответ сохранён: {report_path}")

if __name__ == "__main__":
    main()
