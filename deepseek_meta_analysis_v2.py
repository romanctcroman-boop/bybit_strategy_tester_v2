"""
🤖 META-АНАЛИЗ v2: DeepSeek Agent анализирует свою архитектуру

После первых 4 оптимизаций:
✅ TF-IDF semantic similarity: 0% → 36.8% agreement
✅ Timeout: 30s → 60s
✅ Fast mode: 1.8x speedup
✅ Heap eviction: O(n) → O(log n)

Теперь спрашиваем: Что дальше?
"""

import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from automation.deepseek_robot.api_clients import DeepSeekClient

load_dotenv()


async def ask_deepseek_next_optimizations():
    """Спрашиваем DeepSeek о следующих оптимизациях"""
    
    # Load API keys
    deepseek_keys = []
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_keys.append(key)
    
    if not deepseek_keys:
        print("❌ No DeepSeek API keys found!")
        return
    
    print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys\n")
    
    client = DeepSeekClient(deepseek_keys[0], timeout=60.0)
    
    # Prepare meta-analysis prompt
    messages = [
        {
            "role": "system",
            "content": "Ты — DeepSeek Agent, эксперт по Python, архитектуре систем и оптимизации производительности."
        },
        {
            "role": "user",
            "content": """Проанализируй СВОЮ архитектуру после первых 4 оптимизаций.

УЖЕ ПРИМЕНЕНО (Wave 1):
1. ✅ TF-IDF semantic similarity: 0% → 36.8% agreement
2. ✅ Timeout увеличен: 30s → 60s (нет timeouts)
3. ✅ Fast mode (FIRST_COMPLETED): 1.8x speedup (21s → 11.8s)
4. ✅ Heap-based eviction: O(n) → O(log n)

ТЕКУЩЕЕ СОСТОЯНИЕ:
- 8 API keys DeepSeek (parallel execution)
- 1 Perplexity key
- ML-based cache (TF-IDF) с 80% hit rate
- Dual analytics: DeepSeek + Perplexity
- Agreement rate: 36.8% (было 0%, но можно лучше!)

ПРОБЛЕМЫ ДЛЯ АНАЛИЗА:
1. Agreement rate всё ещё низкий (36.8% vs цель 60-80%)
2. Fast mode даёт только 1.8x (ожидали 2x+)
3. Parallel execution: используем ли все 8 keys эффективно?
4. Cache hit rate 80% — можно ли улучшить до 90%+?
5. Memory usage: может быть утечки памяти?

ЗАДАЧА (Wave 2 Optimizations):
Найди СЛЕДУЮЩИЕ 3-5 оптимизаций для второй волны улучшений.

Верни JSON:
{
  "wave2_optimizations": [
    {
      "priority": 1-5,
      "name": "Название оптимизации",
      "problem": "Что не так сейчас",
      "solution": "Конкретное решение",
      "code_hint": "Где в коде (file.py:method)",
      "expected_impact": "Измеримая метрика (X% improvement)",
      "effort": "low/medium/high",
      "risk": "low/medium/high"
    }
  ],
  "agreement_rate_improvement": {
    "current": "36.8%",
    "target": "60-80%",
    "bottleneck": "Почему не растёт выше?",
    "solution": "Конкретное решение для роста"
  },
  "parallel_efficiency": {
    "current_usage": "Как используются 8 keys?",
    "bottleneck": "Что мешает полной загрузке?",
    "solution": "Как загрузить все 8 keys на 100%"
  },
  "quick_wins": [
    {
      "task": "Что можно сделать за 15-30 минут",
      "impact": "Ожидаемый эффект",
      "code": "Где менять"
    }
  ]
}

Дай конкретные, измеримые, быстро реализуемые решения для Wave 2!"""
        }
    ]
    
    print("="*80)
    print("🤖 META-АНАЛИЗ v2: Спрашиваем DeepSeek о Wave 2 оптимизаций...")
    print("="*80 + "\n")
    
    try:
        result = await client.chat_completion(
            messages=messages,
            model="deepseek-coder",
            temperature=0.1,
            max_tokens=3000
        )
        
        if result.get("success"):
            response = result.get("response", "")
            
            print("\n" + "="*80)
            print("📊 DEEPSEEK AGENT: WAVE 2 OPTIMIZATIONS")
            print("="*80 + "\n")
            
            print(response)
            
            # Save to file
            output_path = Path("deepseek_wave2_optimizations.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(response)
            
            print(f"\n\n✅ Анализ сохранён: {output_path}")
            
            # Display statistics
            print("\n" + "="*80)
            print("📊 СТАТИСТИКА ЗАПРОСА")
            print("="*80)
            print(f"   • Tokens used: {result.get('usage', {}).get('total_tokens', 'N/A')}")
            print(f"   • Prompt tokens: {result.get('usage', {}).get('prompt_tokens', 'N/A')}")
            print(f"   • Completion tokens: {result.get('usage', {}).get('completion_tokens', 'N/A')}")
            print("="*80 + "\n")
            
            return response
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


async def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("🤖 META-АНАЛИЗ v2: DeepSeek анализирует свою архитектуру")
    print("="*80)
    print("\nЦель: Найти Wave 2 оптимизации после успешного Wave 1")
    print("\nWave 1 Results:")
    print("  ✅ Agreement: 0% → 36.8%")
    print("  ✅ Speed: 21s → 11.8s (1.8x)")
    print("  ✅ Timeout fixed: 30s → 60s")
    print("  ✅ Cache: O(n) → O(log n)")
    print("\nЧто можно улучшить ещё?\n")
    
    await ask_deepseek_next_optimizations()
    
    print("\n" + "="*80)
    print("✅ META-АНАЛИЗ v2 ЗАВЕРШЁН")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
