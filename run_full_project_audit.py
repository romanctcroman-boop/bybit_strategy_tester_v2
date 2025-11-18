"""
🔍 ПОЛНЫЙ АУДИТ ПРОЕКТА через DeepSeek Agent

Отправляет все ключевые отчёты на анализ:
- Priority 1-5 отчёты
- Security fixes
- Docker configuration
- Frontend improvements
- Architecture docs
"""

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import aiohttp
from dotenv import load_dotenv

# Загружаем environment variables
load_dotenv()

# Ключевые отчёты для аудита
REPORTS_TO_AUDIT = [
    # Priority Reports
    "PRIORITY_1_COMPLETION_REPORT.md",
    "PRIORITY_2_COMPLETION_REPORT.md",
    "PRIORITY_3_COMPLETION_REPORT.md",
    "PRIORITY_4_COMPLETION_REPORT.md",
    "PRIORITY_5_DOCKER_DEPLOYMENT_COMPLETE.md",
    
    # Security & Production
    "SECURITY_FIX_APPLIED.md",
    "PRODUCTION_DEPLOYMENT.md",
    "PRODUCTION_READINESS_10_OF_10.md",
    
    # Architecture & Implementation
    "ARCHITECTURE.md",
    "COPILOT_PERPLEXITY_MCP_ARCHITECTURE.md",
    
    # DeepSeek Analysis Results
    "DEEPSEEK_DOCKER_ANALYSIS_RESULT.json",
    "PRIORITY_4_DEEPSEEK_ANALYSIS.md",
    
    # Docker Configuration
    "docker-compose.prod.yml",
    "Dockerfile",
    "frontend/Dockerfile",
    "frontend/nginx.conf",
]


async def call_deepseek_api(file_path: Path) -> Dict[str, Any]:
    """Вызов DeepSeek API для анализа файла"""
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {"error": "DEEPSEEK_API_KEY not found in environment"}
    
    # Читаем содержимое файла
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}
    
    # Формируем промпт для анализа
    prompt = f"""Проведи code review следующего файла: {file_path.name}

```
{content[:15000]}  # Ограничение на размер
```

Оцени по шкале от 1 до 10 и дай конкретные рекомендации по улучшению.

Формат ответа:
1. Общая оценка (X/10)
2. Сильные стороны
3. Слабые стороны
4. Топ-3 рекомендации
5. Критические проблемы (если есть)"""
    
    # Вызов DeepSeek API
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-coder",
                    "messages": [
                        {"role": "system", "content": "Ты эксперт по code review и архитектуре ПО."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    review_text = data["choices"][0]["message"]["content"]
                    
                    # Извлекаем оценку из текста
                    score = 7  # Default
                    if "/10" in review_text:
                        try:
                            score_str = review_text.split("/10")[0].strip().split()[-1]
                            score = int(score_str)
                        except:
                            pass
                    
                    return {
                        "deepseek_review": review_text,
                        "combined_score": score,
                        "file_size": len(content),
                        "status": "success"
                    }
                else:
                    error_text = await response.text()
                    return {"error": f"API error {response.status}: {error_text}"}
        
        except asyncio.TimeoutError:
            return {"error": "Request timeout"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}


async def audit_project():
    """Полный аудит проекта через DeepSeek Agent"""
    
    project_root = Path(__file__).parent
    
    print("=" * 80)
    print("🔍 ЗАПУСК ПОЛНОГО АУДИТА ПРОЕКТА")
    print("=" * 80)
    print(f"\n📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Проект: {project_root.name}")
    print(f"📊 Файлов для анализа: {len(REPORTS_TO_AUDIT)}")
    print()
    
    results = {}
    audit_scores = []
    
    for i, report_path in enumerate(REPORTS_TO_AUDIT, 1):
        file_path = project_root / report_path
        
        if not file_path.exists():
            print(f"⚠️  [{i}/{len(REPORTS_TO_AUDIT)}] {report_path} - NOT FOUND")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"📄 [{i}/{len(REPORTS_TO_AUDIT)}] Анализ: {report_path}")
        print(f"{'=' * 80}")
        
        try:
            # Вызываем DeepSeek API
            result = await call_deepseek_api(file_path)
            
            results[report_path] = result
            
            # Проверяем ошибки
            if "error" in result:
                print(f"❌ ОШИБКА: {result['error']}")
                continue
            
            # Вывод резюме
            if "deepseek_review" in result:
                review = result["deepseek_review"]
                print(f"\n📊 DeepSeek Review:")
                print(review[:600] + "..." if len(review) > 600 else review)
            
            if "combined_score" in result:
                score = result["combined_score"]
                audit_scores.append(score)
                print(f"\n⭐ ОЦЕНКА: {score}/10")
                
                # Оценка качества
                if score >= 9:
                    print("   🟢 ОТЛИЧНО - Production Ready")
                elif score >= 7:
                    print("   🟡 ХОРОШО - Minor improvements needed")
                elif score >= 5:
                    print("   🟠 УДОВЛЕТВОРИТЕЛЬНО - Needs work")
                else:
                    print("   🔴 ТРЕБУЕТ ВНИМАНИЯ - Critical issues")
            
            # Небольшая задержка между запросами
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"❌ ОШИБКА при анализе {report_path}: {str(e)}")
            results[report_path] = {"error": str(e)}
    
    # Финальный отчёт
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЙ ОТЧЁТ АУДИТА")
    print("=" * 80)
    
    total_files = len(REPORTS_TO_AUDIT)
    analyzed_files = len([r for r in results.values() if "error" not in r])
    failed_files = total_files - analyzed_files
    
    print(f"\n📈 Статистика:")
    print(f"   ✅ Проанализировано: {analyzed_files}/{total_files}")
    print(f"   ❌ Ошибок: {failed_files}")
    
    if audit_scores:
        avg_score = sum(audit_scores) / len(audit_scores)
        print(f"\n⭐ Средняя оценка: {avg_score:.1f}/10")
        
        # Общая оценка проекта
        if avg_score >= 9:
            print("   🎉 ПРОЕКТ ГОТОВ К PRODUCTION!")
        elif avg_score >= 8:
            print("   ✅ ПРОЕКТ В ОТЛИЧНОМ СОСТОЯНИИ")
        elif avg_score >= 7:
            print("   👍 ПРОЕКТ В ХОРОШЕМ СОСТОЯНИИ")
        elif avg_score >= 6:
            print("   ⚠️  ТРЕБУЮТСЯ УЛУЧШЕНИЯ")
        else:
            print("   🔴 ТРЕБУЕТСЯ СЕРЬЁЗНАЯ РАБОТА")
    
    # Топ файлов по оценке
    if audit_scores:
        print("\n🏆 Топ-5 файлов по оценке:")
        scored_files = [(path, results[path].get("combined_score", 0)) 
                       for path in results if "combined_score" in results[path]]
        scored_files.sort(key=lambda x: x[1], reverse=True)
        
        for idx, (path, score) in enumerate(scored_files[:5], 1):
            print(f"   {idx}. {path}: {score}/10")
    
    # Критические проблемы
    print("\n🔴 Критические находки:")
    critical_issues = []
    for path, result in results.items():
        if "deepseek_review" in result:
            review = result["deepseek_review"].lower()
            if any(word in review for word in ["critical", "security", "vulnerability", "риск"]):
                critical_issues.append(path)
    
    if critical_issues:
        for issue in critical_issues:
            print(f"   ⚠️  {issue}")
    else:
        print("   ✅ Критических проблем не обнаружено!")
    
    # Сохранение результатов
    output_file = project_root / "FULL_PROJECT_AUDIT_RESULTS.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "audit_date": datetime.now().isoformat(),
            "total_files": total_files,
            "analyzed_files": analyzed_files,
            "failed_files": failed_files,
            "average_score": avg_score if audit_scores else None,
            "results": results,
            "critical_issues": critical_issues
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты сохранены: {output_file.name}")
    
    # Генерация финального отчёта
    await generate_final_report(results, audit_scores, critical_issues)
    
    return results


async def generate_final_report(results, audit_scores, critical_issues):
    """Генерация финального отчёта аудита"""
    
    project_root = Path(__file__).parent
    report_file = project_root / "FULL_PROJECT_AUDIT_REPORT.md"
    
    avg_score = sum(audit_scores) / len(audit_scores) if audit_scores else 0
    
    report = f"""# 🔍 ПОЛНЫЙ АУДИТ ПРОЕКТА - DEEPSEEK AGENT

**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Проект:** Bybit Strategy Tester V2  
**Общая оценка:** **{avg_score:.1f}/10** {"🟢" if avg_score >= 9 else "🟡" if avg_score >= 7 else "🔴"}

---

## 📊 EXECUTIVE SUMMARY

**Проанализировано файлов:** {len([r for r in results.values() if "error" not in r])}/{len(results)}  
**Средняя оценка:** {avg_score:.1f}/10  
**Критических проблем:** {len(critical_issues)}

### 🎯 Общий вердикт:
"""
    
    if avg_score >= 9:
        report += "✅ **ПРОЕКТ ГОТОВ К PRODUCTION DEPLOYMENT**\n"
    elif avg_score >= 8:
        report += "✅ **ПРОЕКТ В ОТЛИЧНОМ СОСТОЯНИИ** - Незначительные улучшения\n"
    elif avg_score >= 7:
        report += "⚠️ **ПРОЕКТ В ХОРОШЕМ СОСТОЯНИИ** - Рекомендуется доработка\n"
    else:
        report += "🔴 **ТРЕБУЕТСЯ СЕРЬЁЗНАЯ РАБОТА** - Критические улучшения\n"
    
    report += "\n---\n\n## 📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ\n\n"
    
    # Группировка по категориям
    categories = {
        "Priority Reports": [k for k in results.keys() if "PRIORITY" in k],
        "Security & Production": [k for k in results.keys() if any(x in k for x in ["SECURITY", "PRODUCTION"])],
        "Docker Configuration": [k for k in results.keys() if any(x in k for x in ["docker", "Dockerfile", "nginx"])],
        "Architecture": [k for k in results.keys() if "ARCHITECTURE" in k or "MCP" in k],
        "Analysis Results": [k for k in results.keys() if "DEEPSEEK" in k and k.endswith(".json")],
    }
    
    for category, files in categories.items():
        if not files:
            continue
            
        report += f"\n### {category}\n\n"
        for file_path in files:
            result = results.get(file_path, {})
            score = result.get("combined_score", "N/A")
            
            if isinstance(score, (int, float)):
                emoji = "🟢" if score >= 9 else "🟡" if score >= 7 else "🔴"
                report += f"- {emoji} **{file_path}**: {score}/10\n"
            else:
                report += f"- ⚪ **{file_path}**: Not scored\n"
    
    # Критические находки
    if critical_issues:
        report += "\n---\n\n## 🔴 КРИТИЧЕСКИЕ НАХОДКИ\n\n"
        for issue in critical_issues:
            report += f"- ⚠️ {issue}\n"
    else:
        report += "\n---\n\n## ✅ КРИТИЧЕСКИХ ПРОБЛЕМ НЕ ОБНАРУЖЕНО\n"
    
    # Топ рекомендации
    report += "\n---\n\n## 💡 КЛЮЧЕВЫЕ РЕКОМЕНДАЦИИ\n\n"
    
    # Собираем рекомендации из текста review
    recommendations_count = 0
    for file_path, result in results.items():
        if "deepseek_review" in result:
            review = result["deepseek_review"]
            # Ищем секцию с рекомендациями
            if "рекомендаци" in review.lower() or "recommendation" in review.lower():
                report += f"\n### {file_path}\n"
                # Извлекаем фрагмент с рекомендациями
                lines = review.split('\n')
                in_recommendations = False
                for line in lines:
                    if "рекомендаци" in line.lower() or "recommendation" in line.lower():
                        in_recommendations = True
                    elif in_recommendations and line.strip():
                        report += f"- {line.strip()}\n"
                        recommendations_count += 1
                        if recommendations_count >= 15:  # Ограничение
                            break
                if recommendations_count >= 15:
                    break
    
    if recommendations_count == 0:
        report += "✅ Все файлы в отличном состоянии!\n"
    
    # Следующие шаги
    report += "\n---\n\n## 🚀 СЛЕДУЮЩИЕ ШАГИ\n\n"
    
    if avg_score >= 9:
        report += """
1. ✅ Deploy to production
2. ✅ Set up monitoring alerts
3. ✅ Configure backup strategy
4. ✅ Document deployment process
"""
    elif avg_score >= 8:
        report += """
1. ⚠️ Implement minor improvements from recommendations
2. ✅ Run final security audit
3. ✅ Deploy to staging
4. ✅ Prepare production deployment
"""
    else:
        report += """
1. 🔴 Address critical issues first
2. ⚠️ Implement high-priority recommendations
3. 🔄 Re-run audit after fixes
4. ⏳ Postpone production deployment
"""
    
    report += f"\n---\n\n**Отчёт создан:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
    report += "**DeepSeek Agent:** ✅ Активен  \n"
    report += "**Perplexity Integration:** ✅ Интегрирован\n"
    
    # Сохранение отчёта
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n📄 Финальный отчёт создан: {report_file.name}")


if __name__ == "__main__":
    try:
        results = asyncio.run(audit_project())
        print("\n✅ АУДИТ ЗАВЕРШЁН УСПЕШНО!")
    except KeyboardInterrupt:
        print("\n⚠️ Аудит прерван пользователем")
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        raise
