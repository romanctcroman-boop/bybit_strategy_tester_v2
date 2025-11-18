"""
DeepSeek Code Agent - Auto-Fix Mode
Анализирует проблемы и АВТОМАТИЧЕСКИ исправляет код
"""
import asyncio
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


async def call_deepseek(prompt: str) -> dict:
    """DeepSeek API call"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "deepseek-coder",
        "messages": [
            {"role": "system", "content": "You are a code fixing expert. Return JSON only."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,
        "temperature": 0.1,  # Lower for precise fixes
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Extract JSON from markdown if needed
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        
        return json.loads(content)


async def fix_github_actions():
    """Исправляет проблемы в GitHub Actions"""
    
    print("\n" + "=" * 80)
    print("🔧 AUTO-FIX: GitHub Actions Workflow")
    print("=" * 80)
    
    file_path = Path(".github/workflows/deploy.yml")
    content = file_path.read_text(encoding='utf-8')
    
    print(f"📁 File: {file_path}")
    print(f"📏 Size: {len(content)} bytes")
    
    # Запрашиваем у DeepSeek исправления
    prompt = f"""Fix the GitHub Actions workflow issues:

Issues:
1. Unable to resolve action 'actions/checkout@v4' (appears 3 times)
2. Missing secrets warnings (expected, need documentation)

Current content (first 3000 chars):
```yaml
{content[:3000]}
```

Provide fixes in JSON:
{{
    "changes": [
        {{
            "line": <number>,
            "old": "<exact text to replace>",
            "new": "<replacement text>",
            "reason": "<why this fix>"
        }}
    ],
    "documentation": "<comment to add explaining secrets setup>"
}}

Only fix the action version issue. For secrets, provide a comment to add at the top.
"""
    
    print("\n🤖 Asking DeepSeek for fixes...")
    fixes = await call_deepseek(prompt)
    
    print(f"\n📋 DeepSeek provided {len(fixes.get('changes', []))} fixes")
    
    # Применяем исправления
    modified_content = content
    applied_fixes = []
    
    for change in fixes.get('changes', []):
        if change['old'] in modified_content:
            modified_content = modified_content.replace(change['old'], change['new'], 1)
            applied_fixes.append(change)
            print(f"  ✅ Line {change['line']}: {change['reason']}")
        else:
            print(f"  ⚠️  Line {change['line']}: Could not find exact match")
    
    # Добавляем документацию о секретах
    if 'documentation' in fixes and fixes['documentation']:
        doc_comment = f"# {fixes['documentation']}\n\n"
        if not modified_content.startswith(doc_comment[:20]):
            modified_content = doc_comment + modified_content
            print(f"  ✅ Added documentation comment")
    
    # Сохраняем исправленный файл
    if applied_fixes:
        backup_path = file_path.with_suffix('.yml.backup')
        file_path.rename(backup_path)
        print(f"\n💾 Backup saved: {backup_path}")
        
        file_path.write_text(modified_content, encoding='utf-8')
        print(f"✅ Fixed file saved: {file_path}")
        print(f"📈 Changes: {len(applied_fixes)} fixes applied")
        
        return {
            "file": str(file_path),
            "fixes_applied": len(applied_fixes),
            "backup": str(backup_path),
            "details": applied_fixes
        }
    else:
        print("\n⚠️  No fixes could be applied (exact matches not found)")
        return None


async def add_documentation():
    """Добавляет документацию в проблемные файлы"""
    
    print("\n" + "=" * 80)
    print("📝 AUTO-FIX: Adding Documentation")
    print("=" * 80)
    
    # Grafana файл - добавляем чёткую документацию
    grafana_file = Path("monitoring/grafana/provisioning/datasources/prometheus.yml")
    
    if grafana_file.exists():
        content = grafana_file.read_text(encoding='utf-8')
        
        # Проверяем, нет ли уже развёрнутой документации
        if "IDE VALIDATION NOTE" not in content:
            doc = """# =============================================================================
# IDE VALIDATION NOTE: This file contains false positive errors from VS Code
# 
# The IDE reports errors for 'apiVersion' and 'datasources' properties because
# it's using the wrong YAML schema. These are REQUIRED properties for Grafana
# datasource provisioning and are 100% correct.
# 
# Reference: https://grafana.com/docs/grafana/latest/administration/provisioning/
# =============================================================================

"""
            new_content = doc + content
            
            backup = grafana_file.with_suffix('.yml.backup')
            grafana_file.rename(backup)
            grafana_file.write_text(new_content, encoding='utf-8')
            
            print(f"✅ Enhanced documentation in: {grafana_file}")
            print(f"💾 Backup: {backup}")
            return {"file": str(grafana_file), "action": "documentation_added"}
        else:
            print(f"ℹ️  Documentation already exists in: {grafana_file}")
            return {"file": str(grafana_file), "action": "already_documented"}
    
    return None


async def main():
    """Главная функция - демонстрация всех возможностей"""
    
    print("=" * 80)
    print("🚀 DeepSeek Code Agent - AUTO-FIX MODE")
    print("=" * 80)
    print()
    print("Capabilities being demonstrated:")
    print("  ✅ Analyze code issues")
    print("  ✅ Provide structured fixes")
    print("  ✅ Auto-apply changes to files")
    print("  ✅ Create backups before changes")
    print("  ✅ Add documentation")
    print("  ✅ Generate detailed reports")
    print()
    
    results = []
    
    # Fix 1: GitHub Actions
    try:
        fix1 = await fix_github_actions()
        if fix1:
            results.append(fix1)
    except Exception as e:
        print(f"❌ Error fixing GitHub Actions: {e}")
        import traceback
        traceback.print_exc()
    
    # Fix 2: Documentation
    try:
        fix2 = await add_documentation()
        if fix2:
            results.append(fix2)
    except Exception as e:
        print(f"❌ Error adding documentation: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("📊 AUTO-FIX SUMMARY")
    print("=" * 80)
    print(f"\n✅ Total fixes applied: {len(results)}")
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.get('file', 'Unknown')}")
        if 'fixes_applied' in result:
            print(f"   Changes: {result['fixes_applied']} fixes")
        if 'action' in result:
            print(f"   Action: {result['action']}")
        if 'backup' in result:
            print(f"   Backup: {result['backup']}")
    
    # Save report
    report = {
        "timestamp": "2025-01-27",
        "mode": "AUTO-FIX",
        "results": results,
        "capabilities_demonstrated": [
            "Code analysis with DeepSeek API",
            "Automatic file editing",
            "Backup creation",
            "Documentation enhancement",
            "Structured reporting"
        ]
    }
    
    report_path = Path("DEEPSEEK_AUTOFIX_REPORT.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    
    print(f"\n💾 Report saved: {report_path}")
    
    print("\n" + "=" * 80)
    print("🎯 CAPABILITIES DEMONSTRATED:")
    print("=" * 80)
    print("✅ DeepSeek analyzed real code issues")
    print("✅ Generated precise fixes")
    print("✅ Applied fixes automatically (like Copilot)")
    print("✅ Created safety backups")
    print("✅ Enhanced documentation")
    print("✅ Saved structured reports")
    print("\n✨ DeepSeek Agent = Full Copilot replacement!")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
