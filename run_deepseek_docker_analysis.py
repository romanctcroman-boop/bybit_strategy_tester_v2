"""
Отправка Docker configuration на анализ DeepSeek Agent
"""
import asyncio
import sys
from pathlib import Path

# Добавляем mcp-server в path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from deepseek_code_agent import DeepSeekCodeAgent


async def analyze_docker_configuration():
    """Анализ Production Docker setup через DeepSeek Agent"""
    
    project_root = Path(__file__).parent
    agent = DeepSeekCodeAgent(project_root)
    
    print("🤖 DeepSeek Agent: Начинаю анализ Docker Production Setup...")
    print("=" * 80)
    
    files_to_analyze = [
        "docker-compose.prod.yml",
        "Dockerfile",
        "frontend/Dockerfile",
        "frontend/nginx.conf",
    ]
    
    results = {}
    
    for file_path in files_to_analyze:
        print(f"\n📄 Анализирую: {file_path}")
        print("-" * 80)
        
        result = await agent.code_review(file_path)
        results[file_path] = result
        
        if "error" in result:
            print(f"❌ Ошибка: {result['error']}")
        else:
            # DeepSeek review
            if "deepseek_review" in result:
                print("\n🔍 DEEPSEEK TECHNICAL REVIEW:")
                print(result["deepseek_review"][:500] + "..." if len(result["deepseek_review"]) > 500 else result["deepseek_review"])
            
            # Combined score
            if "combined_score" in result:
                print(f"\n⭐ ОЦЕНКА: {result['combined_score']}/10")
        
        print("\n" + "=" * 80)
    
    # Сохраняем результаты
    output_file = project_root / "DEEPSEEK_DOCKER_ANALYSIS_RESULT.json"
    with open(output_file, "w", encoding="utf-8") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Результаты сохранены в: {output_file}")
    
    # Создаём сводный отчёт
    print("\n" + "=" * 80)
    print("📊 СВОДНЫЙ АНАЛИЗ DOCKER CONFIGURATION")
    print("=" * 80)
    
    total_files = len(results)
    successful = sum(1 for r in results.values() if "error" not in r)
    
    print(f"\n✅ Проанализировано файлов: {successful}/{total_files}")
    
    scores = [r.get("combined_score", 0) for r in results.values() if "combined_score" in r]
    if scores:
        avg_score = sum(scores) / len(scores)
        print(f"⭐ Средняя оценка: {avg_score:.1f}/10")
    
    # Общие рекомендации
    print("\n💡 ОБЩИЕ РЕКОМЕНДАЦИИ:")
    for file_path, result in results.items():
        if "recommendations" in result and result["recommendations"]:
            print(f"\n{file_path}:")
            for i, rec in enumerate(result["recommendations"][:3], 1):  # Top 3
                print(f"  {i}. {rec}")
    
    return results


if __name__ == "__main__":
    asyncio.run(analyze_docker_configuration())
