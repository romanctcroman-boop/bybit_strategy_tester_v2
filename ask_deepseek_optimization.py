"""
🤖 Спросим у DeepSeek Agent: как оптимизировать себя?

Meta-анализ: AI анализирует свою собственную архитектуру
и предлагает конкретные оптимизации.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from automation.deepseek_robot.api_clients import DeepSeekClient
from dotenv import load_dotenv

load_dotenv()


async def ask_deepseek_about_optimization():
    """Спрашиваем DeepSeek Agent о его собственных оптимизациях"""
    
    # Load API keys
    deepseek_keys = []
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_keys.append(key)
    
    if not deepseek_keys:
        print("❌ No DeepSeek API keys found!")
        return
    
    print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys")
    
    client = DeepSeekClient(deepseek_keys[0])
    
    # Read all relevant files
    files_to_analyze = [
        "automation/deepseek_robot/api_clients.py",
        "automation/deepseek_robot/advanced_architecture.py",
        "automation/deepseek_robot/robot.py",
        "automation/deepseek_robot/dual_analytics_engine.py",
    ]
    
    code_context = ""
    for filepath in files_to_analyze:
        full_path = project_root / filepath
        if full_path.exists():
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                code_context += f"\n\n{'='*80}\n"
                code_context += f"FILE: {filepath}\n"
                code_context += f"{'='*80}\n\n"
                code_context += content
    
    # Prepare meta-analysis prompt with MESSAGES format
    messages = [
        {
            "role": "system",
            "content": "Ты — DeepSeek Agent, эксперт по Python, архитектуре систем и оптимизации производительности."
        },
        {
            "role": "user",
            "content": f"""Проанализируй СВОЮ СОБСТВЕННУЮ архитектуру и найди узкие места.

ТЕКУЩЕЕ СОСТОЯНИЕ:
- 8 API keys DeepSeek + 1 Perplexity key
- Параллельное выполнение (8 workers)
- ML-based кэш (TF-IDF) с 80% hit rate
- Dual analytics (DeepSeek + Perplexity)
- Autonomous agent: 100% quality за 2 цикла

ПРОБЛЕМЫ:
1. Agreement rate: 0% между DeepSeek и Perplexity
2. Среднее время: 22.5 сек/файл
3. Разные форматы ответов (JSON vs текст)

ЗАДАЧА:
Найди КОНКРЕТНЫЕ узкие места и предложи оптимизации.

Верни JSON:
{{
  "critical_bottlenecks": [
    {{"issue": "...", "location": "file:line", "impact": "high/medium/low", 
      "proposed_fix": "...", "code_example": "...", "expected_improvement": "X%"}}
  ],
  "agreement_rate_fix": {{
    "root_cause": "Почему 0%?",
    "solution": "Как исправить",
    "implementation": "Конкретный код"
  }},
  "priority_ranking": [
    {{"rank": 1, "task": "...", "effort": "...", "impact": "...", "risk": "..."}}
  ]
}}

ФАЙЛЫ ДЛЯ АНАЛИЗА:
{", ".join(files_to_analyze)}

Дай детальный анализ с измеримыми метриками!"""
        }
    ]
    
    print("\n" + "="*80)
    print("🤖 Спрашиваем DeepSeek Agent о его собственных оптимизациях...")
    print("="*80 + "\n")
    
    # Ask DeepSeek
    result = await client.chat_completion(
        messages=messages,
        model="deepseek-coder",
        temperature=0.1,
        max_tokens=4000
    )
    
    print("\n" + "="*80)
    print("📊 ОТВЕТ DEEPSEEK AGENT (META-АНАЛИЗ)")
    print("="*80 + "\n")
    
    print(result['content'])
    
    # Save to file
    output_path = project_root / "deepseek_self_optimization_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result['content'])
    
    print(f"\n\n✅ Анализ сохранён: {output_path}")
    
    # Display statistics
    print("\n" + "="*80)
    print("📊 СТАТИСТИКА ЗАПРОСА")
    print("="*80)
    print(f"   • Tokens used: {result.get('usage', {}).get('total_tokens', 'N/A')}")
    print(f"   • Prompt tokens: {result.get('usage', {}).get('prompt_tokens', 'N/A')}")
    print(f"   • Completion tokens: {result.get('usage', {}).get('completion_tokens', 'N/A')}")
    print("="*80 + "\n")


async def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("🤖 META-АНАЛИЗ: DeepSeek Agent анализирует свою архитектуру")
    print("="*80 + "\n")
    
    await ask_deepseek_about_optimization()
    
    print("\n" + "="*80)
    print("✅ META-АНАЛИЗ ЗАВЕРШЁН")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
