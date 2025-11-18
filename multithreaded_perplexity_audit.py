"""
🔥 Multithreaded Perplexity Audit Engine
Использует ThreadPoolExecutor + 8 Perplexity API ключей для параллельного анализа

Features:
- 8x parallel execution (real multithreading)
- Automatic API key rotation
- Progress tracking
- Comprehensive directory analysis
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from dotenv import load_dotenv
import time

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent
AI_AUDIT_DIR = PROJECT_ROOT / "ai_audit_results"
OUTPUT_DIR = PROJECT_ROOT / "parallel_audit_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Load 8 Perplexity API keys
PERPLEXITY_KEYS = [
    os.getenv("PERPLEXITY_API_KEY"),
    os.getenv("PERPLEXITY_API_KEY_1"),
    os.getenv("PERPLEXITY_API_KEY_2"),
    os.getenv("PERPLEXITY_API_KEY_3"),
    os.getenv("PERPLEXITY_API_KEY_4"),
    os.getenv("PERPLEXITY_API_KEY_5"),
    os.getenv("PERPLEXITY_API_KEY_6"),
    os.getenv("PERPLEXITY_API_KEY_7"),
]
PERPLEXITY_KEYS = [k for k in PERPLEXITY_KEYS if k]  # Filter out None

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
MAX_WORKERS = len(PERPLEXITY_KEYS)

print(f"🔑 Loaded {len(PERPLEXITY_KEYS)} Perplexity API keys")
print(f"🚀 Max parallel workers: {MAX_WORKERS}")

# ═══════════════════════════════════════════════════════════════════════════
# AUDIT TASKS (8 tasks for 8 workers)
# ═══════════════════════════════════════════════════════════════════════════

AUDIT_TASKS = [
    {
        "name": "backend_services_analysis",
        "directory": "backend/services",
        "prompt_template": """Проанализируй backend services (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. Архитектурные паттерны (SOLID, DRY)
2. Error handling quality
3. Database query optimization
4. Type hints coverage
5. Docstring completeness

Формат: JSON с оценкой 1-10 и конкретными рекомендациями."""
    },
    {
        "name": "backend_tasks_analysis",
        "directory": "backend/tasks",
        "prompt_template": """Проанализируй Celery tasks (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. Async/await best practices
2. Task retry logic
3. Error handling
4. Performance optimization
5. Queue management

Формат: JSON с priority issues (HIGH/MEDIUM/LOW)."""
    },
    {
        "name": "backend_agents_analysis",
        "directory": "backend/agents",
        "prompt_template": """Проанализируй AI agents integration (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. API key management security
2. Rate limiting implementation
3. Fallback mechanisms
4. Error recovery
5. Caching strategies

Формат: JSON с security issues и recommendations."""
    },
    {
        "name": "tests_backend_analysis",
        "directory": "tests",
        "prompt_template": """Проанализируй test suite (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. Test coverage качество
2. Mocking strategy
3. Integration tests completeness
4. Performance tests наличие
5. CI/CD integration

Формат: JSON с gaps analysis."""
    },
    {
        "name": "frontend_components_analysis",
        "directory": "frontend/src/components",
        "prompt_template": """Проанализируй React components (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. TypeScript usage quality
2. React hooks best practices
3. Performance optimization (useMemo, useCallback)
4. Props validation
5. UI/UX consistency

Формат: JSON с priority recommendations."""
    },
    {
        "name": "database_models_analysis",
        "directory": "backend/models",
        "prompt_template": """Проанализируй database models (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. Schema design quality
2. Index optimization
3. Foreign key relationships
4. Migration strategy
5. Query performance

Formат: JSON с database optimization recommendations."""
    },
    {
        "name": "api_endpoints_analysis",
        "directory": "backend/api",
        "prompt_template": """Проанализируй API endpoints (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. RESTful design compliance
2. Input validation
3. Authentication/Authorization
4. Response formatting
5. Error handling

Формат: JSON с security и performance issues."""
    },
    {
        "name": "configuration_analysis",
        "directory": ".",
        "file_patterns": ["*.ini", "*.json", "*.yaml", ".env*", "requirements*.txt"],
        "prompt_template": """Проанализируй configuration files (найдено {file_count} файлов):

Ключевые файлы:
{key_files}

Проверь:
1. Security (exposed secrets)
2. Dependency versions
3. Configuration management
4. Environment separation
5. Best practices compliance

Формат: JSON с critical security issues."""
    }
]


# ═══════════════════════════════════════════════════════════════════════════
# API CLIENT
# ═══════════════════════════════════════════════════════════════════════════

def call_perplexity_with_key(api_key: str, prompt: str, max_tokens: int = 2000) -> str:
    """Call Perplexity API with specific key"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are an expert software architect and code analyst."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }
    
    with httpx.Client(timeout=60.0) as client:
        response = client.post(PERPLEXITY_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════════════
# DIRECTORY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def scan_directory(task: Dict) -> Dict:
    """Scan directory and prepare context for analysis"""
    directory = PROJECT_ROOT / task["directory"]
    
    if not directory.exists():
        return {
            "task_name": task["name"],
            "directory": str(directory),
            "exists": False,
            "file_count": 0,
            "key_files": []
        }
    
    # Find files
    if "file_patterns" in task:
        # Specific patterns
        files = []
        for pattern in task["file_patterns"]:
            files.extend(directory.glob(pattern))
    else:
        # Default: Python and TypeScript files
        files = list(directory.glob("**/*.py")) + list(directory.glob("**/*.ts")) + list(directory.glob("**/*.tsx"))
    
    files = [f for f in files if f.is_file()]
    
    # Get key files (largest or most important)
    key_files = sorted(files, key=lambda f: f.stat().st_size, reverse=True)[:10]
    key_files_str = "\n".join([f"- {f.relative_to(PROJECT_ROOT)} ({f.stat().st_size // 1024}KB)" for f in key_files])
    
    return {
        "task_name": task["name"],
        "directory": str(directory),
        "exists": True,
        "file_count": len(files),
        "key_files": key_files_str,
        "prompt": task["prompt_template"].format(
            file_count=len(files),
            key_files=key_files_str if key_files_str else "No files found"
        )
    }


def execute_analysis_task(task_index: int, task: Dict, api_key: str) -> Dict:
    """Execute single analysis task with specific API key"""
    start_time = time.time()
    
    try:
        # Scan directory
        context = scan_directory(task)
        
        if not context["exists"]:
            return {
                "task": task["name"],
                "status": "skipped",
                "reason": "Directory not found",
                "api_key_index": task_index,
                "duration": time.time() - start_time
            }
        
        if context["file_count"] == 0:
            return {
                "task": task["name"],
                "status": "skipped",
                "reason": "No files found",
                "api_key_index": task_index,
                "duration": time.time() - start_time
            }
        
        print(f"🔍 [{task_index+1}/{MAX_WORKERS}] Analyzing {task['name']} ({context['file_count']} files)...")
        
        # Call Perplexity
        result = call_perplexity_with_key(api_key, context["prompt"], max_tokens=2000)
        
        duration = time.time() - start_time
        print(f"✅ [{task_index+1}/{MAX_WORKERS}] Completed {task['name']} in {duration:.1f}s")
        
        return {
            "task": task["name"],
            "status": "success",
            "directory": context["directory"],
            "file_count": context["file_count"],
            "result": result,
            "api_key_index": task_index,
            "duration": duration
        }
        
    except Exception as e:
        print(f"❌ [{task_index+1}/{MAX_WORKERS}] Failed {task['name']}: {e}")
        return {
            "task": task["name"],
            "status": "error",
            "error": str(e),
            "api_key_index": task_index,
            "duration": time.time() - start_time
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main execution with ThreadPoolExecutor"""
    print("="*80)
    print("🔥 Multithreaded Perplexity Audit Engine")
    print("="*80)
    print()
    
    if len(PERPLEXITY_KEYS) == 0:
        print("❌ No Perplexity API keys found!")
        return
    
    print(f"✅ Using {len(PERPLEXITY_KEYS)} API keys")
    print(f"📊 Analyzing {len(AUDIT_TASKS)} directories in parallel")
    print()
    
    # Execute tasks in parallel
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = []
        for i, task in enumerate(AUDIT_TASKS):
            # Use API key based on index (round-robin)
            api_key = PERPLEXITY_KEYS[i % len(PERPLEXITY_KEYS)]
            future = executor.submit(execute_analysis_task, i, task, api_key)
            futures.append(future)
        
        # Collect results as they complete
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    total_duration = time.time() - start_time
    
    # Statistics
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    
    print()
    print("="*80)
    print("📊 Audit Statistics")
    print("="*80)
    print(f"✅ Successful: {successful}/{len(AUDIT_TASKS)}")
    print(f"❌ Failed: {failed}/{len(AUDIT_TASKS)}")
    print(f"⏭️  Skipped: {skipped}/{len(AUDIT_TASKS)}")
    print(f"⏱️  Total duration: {total_duration:.1f}s")
    print(f"🚀 Average speed: {total_duration/len(AUDIT_TASKS):.1f}s per task")
    print()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Full results JSON
    results_path = OUTPUT_DIR / f"multithreaded_audit_{timestamp}.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_keys_used": len(PERPLEXITY_KEYS),
            "tasks_total": len(AUDIT_TASKS),
            "duration_seconds": total_duration,
            "statistics": {
                "successful": successful,
                "failed": failed,
                "skipped": skipped
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Full results: {results_path}")
    
    # Summary markdown
    summary_path = OUTPUT_DIR / f"multithreaded_audit_summary_{timestamp}.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"# Multithreaded Perplexity Audit Summary\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Statistics\n\n")
        f.write(f"- API Keys Used: {len(PERPLEXITY_KEYS)}\n")
        f.write(f"- Total Tasks: {len(AUDIT_TASKS)}\n")
        f.write(f"- Successful: {successful}\n")
        f.write(f"- Failed: {failed}\n")
        f.write(f"- Skipped: {skipped}\n")
        f.write(f"- Total Duration: {total_duration:.1f}s\n")
        f.write(f"- Average Speed: {total_duration/len(AUDIT_TASKS):.1f}s per task\n\n")
        
        f.write(f"## Task Results\n\n")
        for result in sorted(results, key=lambda r: r.get("duration", 0), reverse=True):
            status_icon = "✅" if result["status"] == "success" else ("❌" if result["status"] == "error" else "⏭️")
            f.write(f"### {status_icon} {result['task']}\n\n")
            f.write(f"- **Status:** {result['status']}\n")
            f.write(f"- **API Key:** #{result['api_key_index'] + 1}\n")
            f.write(f"- **Duration:** {result.get('duration', 0):.1f}s\n")
            
            if result["status"] == "success":
                f.write(f"- **Files Analyzed:** {result.get('file_count', 0)}\n")
                f.write(f"- **Directory:** `{result.get('directory', 'N/A')}`\n\n")
                f.write(f"**Analysis Result:**\n\n")
                f.write(f"```\n{result.get('result', 'N/A')[:500]}...\n```\n\n")
            elif result["status"] == "error":
                f.write(f"- **Error:** {result.get('error', 'Unknown')}\n\n")
            else:
                f.write(f"- **Reason:** {result.get('reason', 'Unknown')}\n\n")
    
    print(f"📄 Summary: {summary_path}")
    
    print()
    print("="*80)
    print("✅ Audit complete!")
    print("="*80)


if __name__ == "__main__":
    main()
