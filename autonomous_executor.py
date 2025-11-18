"""
🎮 Autonomous Command Executor для Bybit Strategy Tester V2

Обёртка над существующими скриптами проекта, которая позволяет:
- Запускать любой скрипт через простую команду
- Получать результаты в структурированном виде
- Передавать результаты в Agent-to-Agent для анализа
- Принимать решения о следующих действиях

Примеры использования:
    python autonomous_executor.py test_agent_to_agent.py
    python autonomous_executor.py test_redis_queue_poc.py --analyze
    python autonomous_executor.py verify_system.py --auto-fix
"""

import sys
import asyncio
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from loguru import logger


class AutonomousExecutor:
    """
    Автономный исполнитель команд
    
    Интеграция:
    - Запускает существующие скрипты проекта
    - Анализирует результаты через Agent-to-Agent
    - Предлагает исправления через File Edit Endpoint
    - Применяет исправления автоматически (если --auto-fix)
    """
    
    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        workspace_root: Optional[Path] = None
    ):
        self.backend_url = backend_url
        self.workspace_root = workspace_root or Path(__file__).parent
        self.execution_history: List[Dict[str, Any]] = []
    
    async def execute_script(
        self,
        script_path: str,
        args: List[str] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        🚀 Выполнение скрипта
        
        Args:
            script_path: Путь к скрипту (относительно workspace)
            args: Дополнительные аргументы
            timeout: Таймаут в секундах
        
        Returns:
            {
                "success": bool,
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "duration": float
            }
        """
        full_path = self.workspace_root / script_path
        
        if not full_path.exists():
            logger.error(f"❌ Script not found: {script_path}")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Script not found: {script_path}",
                "duration": 0
            }
        
        logger.info(f"🚀 Executing: {script_path}")
        start_time = datetime.now()
        
        try:
            cmd = ["python", str(full_path)]
            if args:
                cmd.extend(args)
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_root)
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "duration": duration,
                "script": script_path,
                "timestamp": datetime.now().isoformat()
            }
            
            self.execution_history.append(result)
            
            if result["success"]:
                logger.success(f"✅ Script completed in {duration:.2f}s")
            else:
                logger.error(f"❌ Script failed with exit code {process.returncode}")
            
            return result
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Script timeout after {timeout}s")
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "duration": timeout,
                "script": script_path
            }
        
        except Exception as e:
            logger.error(f"❌ Execution error: {e}", exc_info=True)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": 0,
                "script": script_path
            }
    
    async def analyze_execution_result(
        self,
        result: Dict[str, Any],
        agent: str = "deepseek"
    ) -> Dict[str, Any]:
        """
        📊 Анализ результатов выполнения через Agent-to-Agent
        
        Returns:
            {
                "analysis": str,
                "issues_found": List[str],
                "recommended_fixes": List[Dict],
                "next_action": str
            }
        """
        logger.info(f"📊 Analyzing execution result via {agent}...")
        
        analysis_prompt = f"""
Проанализируй результаты выполнения скрипта в проекте Bybit Strategy Tester V2.

СКРИПТ: {result['script']}
EXIT CODE: {result['exit_code']}
DURATION: {result['duration']}s
SUCCESS: {result['success']}

STDOUT (первые 2000 символов):
```
{result['stdout'][:2000]}
```

STDERR:
```
{result['stderr'][:2000]}
```

ЗАДАЧИ АНАЛИЗА:
1. Определи причину ошибки (если есть)
2. Найди файлы, которые нужно исправить
3. Предложи конкретные изменения кода
4. Укажи следующий шаг

ФОРМАТ ОТВЕТА (строгий JSON):
{{
  "status": "success|warning|error",
  "issues_found": [
    {{"severity": "critical|high|medium|low", "description": "...", "file": "...", "line": null}}
  ],
  "recommended_fixes": [
    {{
      "file": "путь к файлу",
      "action": "edit|create|delete",
      "description": "что нужно исправить",
      "code_snippet": "предложенный код (если нужен)"
    }}
  ],
  "next_action": "описание следующего шага",
  "confidence": 0.0-1.0
}}
"""
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.backend_url}/api/v1/agent/send",
                    json={
                        "from_agent": "copilot",
                        "to_agent": agent,
                        "content": analysis_prompt,
                        "message_type": "query"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data.get("content", "{}")
                    
                    # Извлечь JSON из ответа
                    import re
                    import json
                    
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis, re.DOTALL)
                    if json_match:
                        analysis_json = json.loads(json_match.group(1))
                    else:
                        try:
                            analysis_json = json.loads(analysis)
                        except:
                            analysis_json = {
                                "status": "warning",
                                "issues_found": [],
                                "recommended_fixes": [],
                                "next_action": "Manual review required",
                                "confidence": 0.5,
                                "raw_analysis": analysis
                            }
                    
                    logger.success(f"✅ Analysis complete: status={analysis_json.get('status')}")
                    return analysis_json
            
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}", exc_info=True)
                return {
                    "status": "error",
                    "issues_found": [{"severity": "high", "description": f"Analysis failed: {e}"}],
                    "recommended_fixes": [],
                    "next_action": "Retry or manual intervention"
                }
    
    async def auto_fix_issues(
        self,
        analysis: Dict[str, Any]
    ) -> bool:
        """
        🔧 Автоматическое исправление проблем через File Edit Endpoint
        
        Returns:
            True если все исправления применены успешно
        """
        logger.info("🔧 Applying automatic fixes...")
        
        fixes = analysis.get("recommended_fixes", [])
        
        if not fixes:
            logger.info("✅ No fixes needed")
            return True
        
        success_count = 0
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for fix in fixes:
                file_path = fix.get("file")
                action = fix.get("action", "edit")
                description = fix.get("description")
                
                logger.info(f"🔧 Fixing {file_path}: {description}")
                
                try:
                    if action == "edit":
                        # Использовать refactor mode для автоматического применения
                        response = await client.post(
                            f"{self.backend_url}/api/v1/agent/file-edit",
                            json={
                                "file_path": file_path,
                                "mode": "refactor",
                                "agent": "deepseek",
                                "instruction": description
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"] and data.get("changes_applied"):
                                logger.success(f"✅ Fixed: {file_path}")
                                success_count += 1
                            else:
                                logger.warning(f"⚠️  Fix not applied: {data.get('error', 'Unknown')}")
                        else:
                            logger.error(f"❌ Fix request failed: {response.status_code}")
                    
                    elif action == "create":
                        # Создать новый файл
                        code = fix.get("code_snippet", "# TODO: Implement")
                        response = await client.post(
                            f"{self.backend_url}/api/v1/agent/file-edit",
                            json={
                                "file_path": file_path,
                                "mode": "write",
                                "content": code
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"]:
                                logger.success(f"✅ Created: {file_path}")
                                success_count += 1
                
                except Exception as e:
                    logger.error(f"❌ Fix error: {e}")
        
        logger.info(f"🔧 Applied {success_count}/{len(fixes)} fixes")
        return success_count == len(fixes)
    
    async def autonomous_run(
        self,
        script_path: str,
        max_retries: int = 3,
        auto_fix: bool = False
    ) -> Dict[str, Any]:
        """
        🤖 Автономный запуск с анализом и исправлением
        
        Алгоритм:
        1. Запустить скрипт
        2. Если ошибка → Анализ через Agent-to-Agent
        3. Если auto_fix → Применить исправления
        4. Повторить (до max_retries)
        
        Returns:
            Финальный результат выполнения
        """
        logger.info(f"🤖 Autonomous execution: {script_path}")
        logger.info(f"Max retries: {max_retries}, Auto-fix: {auto_fix}")
        
        attempt = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"ATTEMPT {attempt}/{max_retries}")
            logger.info(f"{'='*60}\n")
            
            # Шаг 1: Выполнение
            result = await self.execute_script(script_path)
            
            # Если успех → выход
            if result["success"]:
                logger.success(f"✅ Script succeeded on attempt {attempt}")
                return result
            
            # Если последняя попытка → выход
            if attempt >= max_retries:
                logger.error(f"❌ Script failed after {max_retries} attempts")
                return result
            
            # Шаг 2: Анализ
            analysis = await self.analyze_execution_result(result)
            
            logger.info(f"📊 Analysis: {analysis.get('next_action')}")
            logger.info(f"🔍 Issues found: {len(analysis.get('issues_found', []))}")
            logger.info(f"🔧 Fixes recommended: {len(analysis.get('recommended_fixes', []))}")
            
            # Шаг 3: Автоисправление
            if auto_fix and analysis.get("recommended_fixes"):
                logger.info("🔧 Applying automatic fixes...")
                fix_success = await self.auto_fix_issues(analysis)
                
                if not fix_success:
                    logger.warning("⚠️  Some fixes failed to apply")
            else:
                logger.info("⏭️  Skipping auto-fix (disabled or no fixes needed)")
                break
            
            # Задержка перед retry
            await asyncio.sleep(2)
        
        return result


async def main():
    """CLI точка входа"""
    parser = argparse.ArgumentParser(
        description="Autonomous Command Executor для Bybit Strategy Tester V2"
    )
    parser.add_argument(
        "script",
        help="Путь к скрипту для выполнения"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Анализировать результат через Agent-to-Agent"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Автоматически исправлять проблемы"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Максимум попыток (default: 3)"
    )
    
    args = parser.parse_args()
    
    # Проверка Backend
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/agent/health", timeout=5.0)
            logger.success(f"✅ Backend running")
        except Exception as e:
            logger.error(f"❌ Backend not running: {e}")
            logger.error("Start backend: py -m uvicorn backend.main:app --reload")
            return
    
    # Создание executor
    executor = AutonomousExecutor()
    
    # Запуск
    if args.analyze or args.auto_fix:
        # Автономный режим
        result = await executor.autonomous_run(
            args.script,
            max_retries=args.max_retries,
            auto_fix=args.auto_fix
        )
    else:
        # Простое выполнение
        result = await executor.execute_script(args.script)
    
    # Вывод результата
    logger.info(f"\n{'='*60}")
    logger.info("EXECUTION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Script: {result['script']}")
    logger.info(f"Success: {result['success']}")
    logger.info(f"Exit Code: {result['exit_code']}")
    logger.info(f"Duration: {result['duration']:.2f}s")
    
    if not result['success']:
        logger.error(f"\nERROR OUTPUT:")
        logger.error(result['stderr'][:500])
    
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    asyncio.run(main())
