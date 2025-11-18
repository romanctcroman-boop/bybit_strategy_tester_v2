"""
DeepSeek Code Agent - Refactoring Pass 2

Request DeepSeek to review and refactor remaining components:
1. DeepSeekClientPool - check for improvements
2. Task Queue - optimize performance
3. Test files - check for missing coverage

Based on DeepSeek's first analysis, now focusing on specific improvements.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from automation.deepseek_code_agent.code_agent import DeepSeekCodeAgent, CodeGenerationRequest


async def refactor_remaining_components():
    """Request specific refactorings from DeepSeek"""
    
    print("="*60)
    print("DeepSeek Code Agent - Refactoring Pass 2")
    print("="*60)
    print()
    
    agent = DeepSeekCodeAgent()
    
    # Задачи для рефакторинга
    refactoring_tasks = [
        {
            "component": "DeepSeekClientPool",
            "file": "backend/api/deepseek_pool.py",
            "improvements": [
                "Add connection health checks",
                "Implement pool statistics caching",
                "Add graceful degradation if one pool fails",
                "Better error propagation to caller",
            ]
        },
        {
            "component": "Task Queue", 
            "file": "backend/api/task_queue.py",
            "improvements": [
                "Optimize dequeue with Redis pipeline",
                "Add batch enqueue support",
                "Implement queue size monitoring alerts",
                "Better dead letter queue handling",
            ]
        },
        {
            "component": "Test Coverage",
            "file": "tests/",
            "improvements": [
                "Add stress tests (1000+ concurrent)",
                "Add chaos engineering tests",
                "Test Redis connection failures",
                "Test API key exhaustion scenarios",
            ]
        }
    ]
    
    for task in refactoring_tasks:
        print(f"\n🔧 Refactoring: {task['component']}")
        print(f"   File: {task['file']}")
        print(f"   Improvements: {len(task['improvements'])}")
        print()
        
        # Read current implementation
        if task['file'].startswith('backend'):
            file_path = Path(__file__).parent / task['file']
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_code = f.read()
                
                # Ask DeepSeek to refactor
                refactor_prompt = f"""
Улучши код компонента {task['component']}.

Текущий код:
```python
{current_code[:15000]}  # First 15k chars
```

Требуемые улучшения:
{chr(10).join(f'- {imp}' for imp in task['improvements'])}

Создай улучшенную версию с:
1. Сохранением существующего API (backward compatible)
2. Добавлением новых фич
3. Улучшенной обработкой ошибок
4. Комментариями к изменениям
"""
                
                request = CodeGenerationRequest(
                    prompt=refactor_prompt,
                    language="python",
                    style="production",
                    max_tokens=3000,
                )
                
                result = await agent.generate_code(request)
                
                if result["success"]:
                    # Save refactored version
                    refactored_file = file_path.parent / f"{file_path.stem}_refactored{file_path.suffix}"
                    with open(refactored_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Refactored by DeepSeek Code Agent\n")
                        f.write(f"# Original: {file_path.name}\n")
                        f.write(f"# Date: November 8, 2025\n\n")
                        f.write(result.get("code", ""))
                    
                    print(f"   ✅ Refactored → {refactored_file.name}")
                else:
                    print(f"   ❌ Failed: {result.get('error')}")
    
    await agent.close()
    
    print()
    print("="*60)
    print("Refactoring Pass 2 Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(refactor_remaining_components())
