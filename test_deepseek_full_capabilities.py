"""
DeepSeek Code Agent - Полная демонстрация возможностей
Использует DeepSeek API + Copilot инструменты для исправления кода
"""
import asyncio
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not found in .env")


async def call_deepseek(prompt: str, model: str = "deepseek-coder") -> dict:
    """Вызов DeepSeek API с детальным ответом"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert code analyzer. Provide structured analysis in JSON format."
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,
        "temperature": 0.2,
    }
    
    print("  🌐 Sending request to DeepSeek API...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Try to parse as JSON
        try:
            return json.loads(content)
        except:
            return {"analysis": content, "raw": True}


async def analyze_problems():
    """Анализ всех проблем IDE через DeepSeek"""
    
    print("=" * 80)
    print("DeepSeek Code Agent - Full Capabilities Demonstration")
    print("=" * 80)
    print()
    
    # Собираем все проблемы
    problems = {
        "prometheus.yml": {
            "file": "monitoring/grafana/provisioning/datasources/prometheus.yml",
            "errors": [
                {"line": 9, "issue": "Property apiVersion is not allowed"},
                {"line": 11, "issue": "Property datasources is not allowed"}
            ]
        },
        "deploy.yml": {
            "file": ".github/workflows/deploy.yml",
            "errors": [
                {"line": 48, "issue": "Unable to resolve action actions/checkout@v4"},
                {"line": 84, "issue": "Unable to resolve action actions/checkout@v4"},
                {"line": 115, "issue": "Unable to resolve action actions/checkout@v4"},
                {"line": 92, "issue": "Context access might be invalid: DOCKER_USERNAME"},
                {"line": 93, "issue": "Context access might be invalid: DOCKER_PASSWORD"},
                {"line": 102, "issue": "Context access might be invalid: DOCKER_USERNAME"},
                {"line": 103, "issue": "Context access might be invalid: DOCKER_USERNAME"},
                {"line": 104, "issue": "Context access might be invalid: DOCKER_USERNAME"},
                {"line": 105, "issue": "Context access might be invalid: DOCKER_USERNAME"},
                {"line": 125, "issue": "Context access might be invalid: KUBE_CONFIG"},
                {"line": 135, "issue": "Context access might be invalid: DATABASE_URL"},
                {"line": 136, "issue": "Context access might be invalid: DEEPSEEK_API_KEY"},
                {"line": 137, "issue": "Context access might be invalid: PERPLEXITY_API_KEY"},
                {"line": 175, "issue": "Context access might be invalid: SLACK_WEBHOOK"}
            ]
        }
    }
    
    results = []
    
    for file_key, file_info in problems.items():
        print(f"\n{'=' * 80}")
        print(f"📁 Analyzing: {file_info['file']}")
        print(f"{'=' * 80}")
        print(f"Found {len(file_info['errors'])} issues")
        
        file_path = Path(file_info['file'])
        
        if not file_path.exists():
            print(f"  ❌ File not found!")
            continue
        
        # Читаем файл
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Показываем проблемные строки
        print(f"\n📝 Problem lines:")
        for error in file_info['errors'][:3]:  # Показываем первые 3
            line_num = error['line']
            if line_num <= len(lines):
                print(f"  Line {line_num}: {lines[line_num-1][:60]}...")
                print(f"    Issue: {error['issue']}")
        
        if len(file_info['errors']) > 3:
            print(f"  ... and {len(file_info['errors']) - 3} more issues")
        
        # Создаём запрос к DeepSeek
        error_summary = "\n".join([
            f"- Line {e['line']}: {e['issue']}" 
            for e in file_info['errors']
        ])
        
        prompt = f"""Analyze this file and its reported issues.

File: {file_info['file']}
Type: {'YAML (Grafana config)' if 'grafana' in file_info['file'] else 'YAML (GitHub Actions)'}

Issues reported by IDE:
{error_summary}

File content (first 2000 chars):
```
{content[:2000]}
```

Provide analysis in JSON format:
{{
    "real_errors": [list of actual errors that need fixing],
    "false_positives": [list of false positives that should be ignored],
    "recommendations": [list of recommendations],
    "needs_fixes": true/false,
    "explanation": "brief explanation"
}}
"""
        
        print("\n🤖 Asking DeepSeek for analysis...")
        analysis = await call_deepseek(prompt)
        
        print("\n📊 DeepSeek Analysis:")
        if "raw" in analysis:
            print(f"  {analysis['analysis'][:300]}...")
        else:
            print(f"  Real errors: {len(analysis.get('real_errors', []))}")
            print(f"  False positives: {len(analysis.get('false_positives', []))}")
            print(f"  Needs fixes: {analysis.get('needs_fixes', 'unknown')}")
            print(f"  Explanation: {analysis.get('explanation', 'N/A')[:100]}...")
        
        results.append({
            "file": file_info['file'],
            "total_issues": len(file_info['errors']),
            "analysis": analysis
        })
        
        # Небольшая пауза между запросами
        await asyncio.sleep(1)
    
    # Итоговый отчёт
    print("\n" + "=" * 80)
    print("📊 Final Summary")
    print("=" * 80)
    
    total_issues = sum(r['total_issues'] for r in results)
    print(f"\n✅ Total files analyzed: {len(results)}")
    print(f"⚠️  Total issues found: {total_issues}")
    
    for result in results:
        print(f"\n📁 {result['file']}:")
        print(f"  Issues: {result['total_issues']}")
        
        analysis = result['analysis']
        if "raw" in analysis:
            print(f"  Analysis: Available (raw format)")
        else:
            real_errors = len(analysis.get('real_errors', []))
            false_pos = len(analysis.get('false_positives', []))
            print(f"  Real errors: {real_errors}")
            print(f"  False positives: {false_pos}")
            print(f"  Needs action: {'Yes' if analysis.get('needs_fixes') else 'No'}")
    
    # Сохраняем отчёт
    report_path = Path("DEEPSEEK_ANALYSIS_FULL_REPORT.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# DeepSeek Code Agent - Full Analysis Report\n\n")
        f.write("**Date:** November 8, 2025\n\n")
        f.write(f"**Total Files:** {len(results)}\n")
        f.write(f"**Total Issues:** {total_issues}\n\n")
        
        for result in results:
            f.write(f"## {result['file']}\n\n")
            f.write(f"**Issues Found:** {result['total_issues']}\n\n")
            f.write("**DeepSeek Analysis:**\n```json\n")
            f.write(json.dumps(result['analysis'], indent=2))
            f.write("\n```\n\n")
    
    print(f"\n💾 Full report saved to: {report_path}")
    
    # Демонстрация возможностей
    print("\n" + "=" * 80)
    print("🎯 DeepSeek Agent Capabilities Demonstrated:")
    print("=" * 80)
    print("✅ Read files from disk")
    print("✅ Analyze code structure")
    print("✅ Detect false positives")
    print("✅ Provide structured JSON output")
    print("✅ Give actionable recommendations")
    print("✅ Save detailed reports")
    print("\n✨ DeepSeek can do everything Copilot does + more!")
    
    return results


async def main():
    try:
        results = await analyze_problems()
        print("\n✅ Analysis complete!")
        return results
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
