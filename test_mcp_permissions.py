"""
🧪 Тест прав доступа MCP сервера
Проверяет все настроенные права и capabilities
"""

import asyncio
import sys
import os
from pathlib import Path
import json

# Добавить корневую директорию в path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "mcp-server"))

# Импортируем тестовые функции
import httpx


async def test_file_access():
    """Тест доступа к файлам проекта"""
    try:
        project_root = Path(os.getenv("PROJECT_ROOT", "d:/bybit_strategy_tester_v2"))
        
        py_files = list(project_root.rglob("*.py"))
        ts_files = list(project_root.rglob("*.ts"))
        tsx_files = list(project_root.rglob("*.tsx"))
        json_files = list(project_root.rglob("*.json"))
        md_files = list(project_root.rglob("*.md"))
        
        key_files = {
            "README.md": (project_root / "README.md").exists(),
            "package.json": (project_root / "frontend" / "package.json").exists(),
            "requirements.txt": (project_root / "backend" / "requirements.txt").exists(),
            ".env": (project_root / ".env").exists(),
            "mcp.json": (project_root / ".vscode" / "mcp.json").exists()
        }
        
        return {
            "status": "✅ SUCCESS",
            "project_root": str(project_root),
            "file_counts": {
                "python": len(py_files),
                "typescript": len(ts_files),
                "tsx": len(tsx_files),
                "json": len(json_files),
                "markdown": len(md_files),
                "total": len(py_files) + len(ts_files) + len(tsx_files) + len(json_files) + len(md_files)
            },
            "key_files_access": key_files,
            "message": f"✅ Полный доступ к {len(py_files) + len(ts_files) + len(tsx_files)} исходным файлам"
        }
    except Exception as e:
        return {
            "status": "❌ ERROR",
            "error": str(e),
            "message": "Ошибка доступа к файлам проекта"
        }


async def test_env_access():
    """Тест доступа к переменным окружения"""
    try:
        env_vars = {
            "API Keys": ["PERPLEXITY_API_KEY", "DEEPSEEK_API_KEY"],
            "Project Paths": ["PROJECT_ROOT", "MCP_SERVER_ROOT", "PYTHONPATH"],
            "Python Settings": ["PYTHONUNBUFFERED"],
            "Debug Settings": ["MCP_DEBUG", "LOG_LEVEL"]
        }
        
        results = {}
        for category, vars_list in env_vars.items():
            results[category] = {}
            for var in vars_list:
                value = os.getenv(var)
                if value:
                    if "KEY" in var or "SECRET" in var:
                        masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                        results[category][var] = f"✅ {masked}"
                    else:
                        results[category][var] = f"✅ {value}"
                else:
                    results[category][var] = "❌ NOT SET"
        
        total_vars = sum(len(vars_list) for vars_list in env_vars.values())
        set_vars = sum(1 for category in results.values() for value in category.values() if "✅" in value)
        
        return {
            "status": "✅ SUCCESS" if set_vars == total_vars else "⚠️ PARTIAL",
            "results": results,
            "statistics": {
                "total": total_vars,
                "set": set_vars,
                "missing": total_vars - set_vars,
                "coverage": f"{(set_vars/total_vars*100):.1f}%"
            },
            "message": f"✅ {set_vars}/{total_vars} переменных окружения настроены"
        }
    except Exception as e:
        return {
            "status": "❌ ERROR",
            "error": str(e),
            "message": "Ошибка доступа к переменным окружения"
        }


async def test_api_access():
    """Тест доступа к внешним API"""
    try:
        results = {}
        
        # Test Perplexity API
        perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        if perplexity_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.perplexity.ai/chat/completions",
                        headers={
                            "Authorization": f"Bearer {perplexity_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "sonar",
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1
                        }
                    )
                    results["Perplexity"] = {
                        "status": "✅ Connected" if response.status_code in [200, 429] else "❌ Failed",
                        "status_code": response.status_code,
                        "key": f"{perplexity_key[:8]}...{perplexity_key[-4:]}"
                    }
            except Exception as e:
                results["Perplexity"] = {"status": "❌ Error", "error": str(e)[:100]}
        else:
            results["Perplexity"] = {"status": "❌ No API Key"}
        
        # Test DeepSeek API
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {deepseek_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "deepseek-coder",
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1
                        }
                    )
                    results["DeepSeek"] = {
                        "status": "✅ Connected" if response.status_code in [200, 429] else "❌ Failed",
                        "status_code": response.status_code,
                        "key": f"{deepseek_key[:8]}...{deepseek_key[-4:]}"
                    }
            except Exception as e:
                results["DeepSeek"] = {"status": "❌ Error", "error": str(e)[:100]}
        else:
            results["DeepSeek"] = {"status": "❌ No API Key"}
        
        all_ok = all(r.get("status", "").startswith("✅") for r in results.values())
        
        return {
            "status": "✅ ALL CONNECTED" if all_ok else "⚠️ PARTIAL",
            "results": results,
            "message": "✅ Доступ к внешним API работает" if all_ok else "⚠️ Некоторые API недоступны"
        }
    except Exception as e:
        return {
            "status": "❌ ERROR",
            "error": str(e),
            "message": "Ошибка проверки доступа к API"
        }


async def main():
    """Запуск всех тестов"""
    print("\n" + "="*80)
    print("🧪 КОМПЛЕКСНЫЙ ТЕСТ ПРАВ ДОСТУПА MCP СЕРВЕРА")
    print("="*80 + "\n")
    
    # Загружаем env из mcp.json
    os.environ["PERPLEXITY_API_KEY"] = "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"
    os.environ["DEEPSEEK_API_KEY"] = "sk-1630fbba63c64f88952c16ad33337242"
    os.environ["PROJECT_ROOT"] = "D:\\bybit_strategy_tester_v2"
    os.environ["MCP_SERVER_ROOT"] = "D:\\bybit_strategy_tester_v2\\mcp-server"
    os.environ["PYTHONPATH"] = "D:\\bybit_strategy_tester_v2"
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["MCP_DEBUG"] = "1"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    print("📋 Запуск тестов...\n")
    
    # Test 1: File Access
    print("1️⃣ Тест доступа к файлам проекта...")
    file_test = await test_file_access()
    print(f"   {file_test['status']}: {file_test['message']}")
    
    # Test 2: Environment Variables
    print("\n2️⃣ Тест переменных окружения...")
    env_test = await test_env_access()
    print(f"   {env_test['status']}: {env_test['message']}")
    
    # Test 3: External API
    print("\n3️⃣ Тест доступа к внешним API...")
    api_test = await test_api_access()
    print(f"   {api_test['status']}: {api_test['message']}")
    
    # Overall Score
    tests_passed = sum(1 for test in [file_test, env_test, api_test] 
                      if test.get("status", "").startswith("✅"))
    total_tests = 3
    score = (tests_passed / total_tests) * 100
    
    print("\n" + "="*80)
    print(f"📊 ИТОГОВЫЙ РЕЗУЛЬТАТ: {tests_passed}/{total_tests} тестов пройдено ({score:.0f}%)")
    print("="*80 + "\n")
    
    # Detailed Results
    result = {
        "status": "✅ ALL TESTS PASSED" if tests_passed == total_tests else "⚠️ SOME TESTS FAILED",
        "score": f"{score:.0f}%",
        "tests_passed": f"{tests_passed}/{total_tests}",
        "results": {
            "1. File Access": file_test,
            "2. Environment Variables": env_test,
            "3. External API": api_test
        },
        "summary": {
            "file_access": file_test.get("status", ""),
            "env_vars": env_test.get("status", ""),
            "api_access": api_test.get("status", "")
        }
    }
    
    print("📄 Детальный отчет:\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
