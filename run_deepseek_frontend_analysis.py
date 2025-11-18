"""
Отправка CreateBacktestForm.tsx на анализ DeepSeek Agent
"""
import asyncio
import sys
from pathlib import Path

# Добавляем mcp-server в path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from deepseek_code_agent import DeepSeekCodeAgent


async def analyze_frontend_component():
    """Анализ CreateBacktestForm.tsx через DeepSeek Agent"""
    
    project_root = Path(__file__).parent
    agent = DeepSeekCodeAgent(project_root)
    
    print("🤖 DeepSeek Agent: Начинаю анализ CreateBacktestForm.tsx...")
    print("-" * 80)
    
    # Анализируем форму
    result = await agent.code_review("frontend/src/components/CreateBacktestForm.tsx")
    
    print("\n📊 РЕЗУЛЬТАТЫ АНАЛИЗА:")
    print("=" * 80)
    
    if "error" in result:
        print(f"❌ Ошибка: {result['error']}")
    else:
        # DeepSeek review
        if "deepseek_review" in result:
            print("\n🔍 DEEPSEEK TECHNICAL REVIEW:")
            print(result["deepseek_review"])
        
        # Perplexity best practices
        if "perplexity_review" in result:
            print("\n✨ PERPLEXITY BEST PRACTICES:")
            print(result["perplexity_review"])
        
        # Combined score
        if "combined_score" in result:
            print(f"\n⭐ ИТОГОВАЯ ОЦЕНКА: {result['combined_score']}/10")
        
        # Recommendations
        if "recommendations" in result:
            print("\n💡 РЕКОМЕНДАЦИИ:")
            for i, rec in enumerate(result["recommendations"], 1):
                print(f"{i}. {rec}")
    
    print("\n" + "=" * 80)
    
    # Сохраняем результаты
    output_file = project_root / "DEEPSEEK_FRONTEND_ANALYSIS_RESULT.json"
    with open(output_file, "w", encoding="utf-8") as f:
        import json
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Результаты сохранены в: {output_file}")
    
    return result


if __name__ == "__main__":
    asyncio.run(analyze_frontend_component())
