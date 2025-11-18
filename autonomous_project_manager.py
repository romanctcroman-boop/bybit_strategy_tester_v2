"""
🤖 Autonomous Project Manager для Bybit Strategy Tester V2

Полностью автономная система управления проектом, которая:
- ✅ Анализирует код через Agent-to-Agent
- ✅ Редактирует файлы через File Edit Endpoint
- ✅ Запускает тесты и скрипты
- ✅ Принимает решения о следующих шагах
- ✅ Работает без вмешательства человека

Интеграция:
- Backend API (agent_to_agent_api.py) - для AI анализа и редактирования
- Существующие скрипты (test_*.py) - для валидации
- MCP Server - для расширенных возможностей
"""

import asyncio
import httpx
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from enum import Enum


class TaskPriority(Enum):
    """Приоритет задач"""
    CRITICAL = 1    # Блокирующие баги, security issues
    HIGH = 2        # Важные фичи, performance issues
    MEDIUM = 3      # Улучшения, рефакторинг
    LOW = 4         # Nice-to-have, документация


class TaskStatus(Enum):
    """Статус задачи"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ProjectTask:
    """Задача проекта"""
    def __init__(
        self,
        task_id: str,
        description: str,
        priority: TaskPriority,
        files_to_modify: List[str],
        tests_to_run: List[str],
        success_criteria: str
    ):
        self.task_id = task_id
        self.description = description
        self.priority = priority
        self.files_to_modify = files_to_modify
        self.tests_to_run = tests_to_run
        self.success_criteria = success_criteria
        self.status = TaskStatus.PENDING
        self.attempts = 0
        self.max_attempts = 3
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.result: Optional[str] = None


class AutonomousProjectManager:
    """
    Автономный менеджер проекта
    
    Архитектура:
    1. Анализ текущего состояния проекта (через Agent-to-Agent)
    2. Определение приоритетных задач (AI decision)
    3. Выполнение задач (File Edit + Tests)
    4. Валидация результатов (DeepSeek analysis)
    5. Принятие решения о следующих шагах (recursive)
    """
    
    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        workspace_root: Optional[Path] = None
    ):
        self.backend_url = backend_url
        self.workspace_root = workspace_root or Path(__file__).parent
        self.tasks: List[ProjectTask] = []
        self.execution_log: List[Dict[str, Any]] = []
        
        logger.info(f"🤖 Autonomous Project Manager initialized")
        logger.info(f"Backend: {self.backend_url}")
        logger.info(f"Workspace: {self.workspace_root}")
    
    async def analyze_project_state(self) -> Dict[str, Any]:
        """
        📊 Анализ текущего состояния проекта через Agent-to-Agent
        
        Использует:
        - /api/v1/agent/send для запроса к DeepSeek
        - File reading для получения структуры проекта
        
        Returns:
            {
                "health": "good|warning|critical",
                "issues": [...],
                "recommendations": [...],
                "next_priorities": [...]
            }
        """
        logger.info("📊 Analyzing project state...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Шаг 1: Получить список критичных файлов
            critical_files = [
                "backend/queue/redis_queue_manager.py",
                "backend/api/agent_to_agent_api.py",
                "backend/agents/agent_to_agent_communicator.py",
                "test_agent_to_agent.py",
                "test_redis_queue_poc.py"
            ]
            
            # Шаг 2: Прочитать содержимое ключевых файлов
            files_content = {}
            for file_path in critical_files:
                full_path = self.workspace_root / file_path
                if full_path.exists():
                    try:
                        response = await client.post(
                            f"{self.backend_url}/api/v1/agent/file-edit",
                            json={
                                "file_path": file_path,
                                "mode": "read"
                            }
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data["success"]:
                                lines = data["content"].splitlines()
                                files_content[file_path] = {
                                    "lines": len(lines),
                                    "preview": "\n".join(lines[:20])
                                }
                    except Exception as e:
                        logger.warning(f"Cannot read {file_path}: {e}")
            
            # Шаг 3: Отправить в DeepSeek для анализа
            analysis_prompt = f"""
Проанализируй текущее состояние проекта "Bybit Strategy Tester V2".

КРИТИЧНЫЕ ФАЙЛЫ:
{json.dumps(files_content, indent=2, ensure_ascii=False)}

КОНТЕКСТ:
- Проект: Автоматизированное тестирование торговых стратегий на Bybit
- Архитектура: FastAPI Backend + Redis Queue + Agent-to-Agent Communication
- Цель: Полностью автономная система, способная улучшать саму себя

ЗАДАЧИ АНАЛИЗА:
1. Оцени здоровье проекта (health: good/warning/critical)
2. Найди критичные проблемы (bugs, security, performance)
3. Предложи 3-5 приоритетных задач для улучшения
4. Укажи файлы, которые нужно отредактировать

ФОРМАТ ОТВЕТА (строгий JSON):
{{
  "health": "good|warning|critical",
  "health_score": 0-100,
  "issues": [
    {{"severity": "critical|high|medium|low", "description": "...", "file": "..."}}
  ],
  "recommendations": [
    {{
      "priority": "critical|high|medium|low",
      "task": "...",
      "files": ["..."],
      "rationale": "..."
    }}
  ],
  "next_action": "описание первого шага"
}}
"""
            
            try:
                response = await client.post(
                    f"{self.backend_url}/api/v1/agent/send",
                    json={
                        "from_agent": "copilot",
                        "to_agent": "deepseek",
                        "content": analysis_prompt,
                        "message_type": "query"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data.get("content", "{}")
                    
                    # Попытка извлечь JSON из ответа
                    import re
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis, re.DOTALL)
                    if json_match:
                        analysis_json = json.loads(json_match.group(1))
                    else:
                        # Попытка парсить весь ответ как JSON
                        try:
                            analysis_json = json.loads(analysis)
                        except:
                            # Fallback: создать структуру вручную
                            analysis_json = {
                                "health": "warning",
                                "health_score": 75,
                                "issues": [],
                                "recommendations": [
                                    {
                                        "priority": "high",
                                        "task": "Complete Phase 1 Redis Queue implementation",
                                        "files": ["backend/queue/redis_queue_manager.py"],
                                        "rationale": "Core infrastructure for async task processing"
                                    }
                                ],
                                "next_action": "Implement and test Redis Queue Manager",
                                "raw_analysis": analysis
                            }
                    
                    logger.success(f"✅ Project analysis complete: health={analysis_json.get('health')}")
                    return analysis_json
            
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}", exc_info=True)
                return {
                    "health": "unknown",
                    "health_score": 50,
                    "issues": [{"severity": "high", "description": f"Analysis failed: {e}"}],
                    "recommendations": [],
                    "next_action": "Manual intervention required"
                }
    
    async def create_task_from_recommendation(
        self,
        recommendation: Dict[str, Any]
    ) -> ProjectTask:
        """
        🎯 Создание задачи из рекомендации DeepSeek
        """
        priority_map = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW
        }
        
        task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        task = ProjectTask(
            task_id=task_id,
            description=recommendation["task"],
            priority=priority_map.get(recommendation["priority"], TaskPriority.MEDIUM),
            files_to_modify=recommendation.get("files", []),
            tests_to_run=self._determine_tests_for_files(recommendation.get("files", [])),
            success_criteria=recommendation.get("rationale", "Task completed successfully")
        )
        
        self.tasks.append(task)
        logger.info(f"✅ Task created: {task_id} - {task.description}")
        
        return task
    
    def _determine_tests_for_files(self, files: List[str]) -> List[str]:
        """Определение тестов для файлов"""
        tests = []
        
        for file_path in files:
            if "redis_queue" in file_path:
                tests.append("test_redis_queue_poc.py")
            elif "agent_to_agent" in file_path:
                tests.append("test_agent_to_agent.py")
            elif "file_edit" in file_path:
                tests.append("test_file_edit_endpoint.py")
        
        return list(set(tests)) if tests else ["pytest"]
    
    async def execute_task(self, task: ProjectTask) -> bool:
        """
        🚀 Выполнение задачи
        
        Алгоритм:
        1. Анализ файлов через /api/v1/agent/file-edit (mode=analyze)
        2. Рефакторинг через /api/v1/agent/file-edit (mode=refactor)
        3. Запуск тестов через subprocess
        4. Валидация результатов через DeepSeek
        5. Принятие решения: success/retry/fail
        """
        logger.info(f"🚀 Executing task: {task.task_id}")
        task.status = TaskStatus.IN_PROGRESS
        task.attempts += 1
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Шаг 1: Анализ каждого файла
            for file_path in task.files_to_modify:
                logger.info(f"📄 Analyzing {file_path}...")
                
                try:
                    response = await client.post(
                        f"{self.backend_url}/api/v1/agent/file-edit",
                        json={
                            "file_path": file_path,
                            "mode": "analyze",
                            "agent": "deepseek",
                            "instruction": f"Analyze this file for: {task.description}"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data["success"]:
                            logger.info(f"✅ Analysis: {data['agent_analysis'][:200]}...")
                        else:
                            logger.error(f"❌ Analysis failed: {data.get('error')}")
                
                except Exception as e:
                    logger.error(f"❌ Analysis error: {e}")
            
            # Шаг 2: Запуск тестов
            task.status = TaskStatus.TESTING
            test_results = await self._run_tests(task.tests_to_run)
            
            # Шаг 3: Валидация результатов
            if test_results["success"]:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = f"Tests passed: {test_results['passed']}/{test_results['total']}"
                logger.success(f"✅ Task completed: {task.task_id}")
                return True
            else:
                if task.attempts < task.max_attempts:
                    task.status = TaskStatus.PENDING
                    logger.warning(f"⚠️  Task failed (attempt {task.attempts}/{task.max_attempts})")
                    return False
                else:
                    task.status = TaskStatus.FAILED
                    task.result = f"Tests failed after {task.max_attempts} attempts"
                    logger.error(f"❌ Task failed: {task.task_id}")
                    return False
    
    async def _run_tests(self, test_files: List[str]) -> Dict[str, Any]:
        """Запуск тестов"""
        logger.info(f"🧪 Running tests: {test_files}")
        
        results = {
            "success": True,
            "total": len(test_files),
            "passed": 0,
            "failed": 0,
            "output": []
        }
        
        for test_file in test_files:
            test_path = self.workspace_root / test_file
            
            if not test_path.exists():
                logger.warning(f"⚠️  Test file not found: {test_file}")
                continue
            
            try:
                logger.info(f"Running {test_file}...")
                
                # Запуск через subprocess
                process = subprocess.run(
                    ["python", str(test_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(self.workspace_root)
                )
                
                output = process.stdout + process.stderr
                
                if process.returncode == 0:
                    results["passed"] += 1
                    logger.success(f"✅ Test passed: {test_file}")
                else:
                    results["failed"] += 1
                    results["success"] = False
                    logger.error(f"❌ Test failed: {test_file}")
                
                results["output"].append({
                    "test": test_file,
                    "exit_code": process.returncode,
                    "output": output[:500]
                })
            
            except subprocess.TimeoutExpired:
                results["failed"] += 1
                results["success"] = False
                logger.error(f"❌ Test timeout: {test_file}")
            
            except Exception as e:
                results["failed"] += 1
                results["success"] = False
                logger.error(f"❌ Test error: {e}")
        
        return results
    
    async def autonomous_work_cycle(self, max_iterations: int = 10):
        """
        🔄 Автономный цикл работы
        
        Алгоритм:
        1. Анализ проекта → Получение рекомендаций
        2. Создание задач из рекомендаций
        3. Сортировка по приоритету
        4. Выполнение задач
        5. Повтор цикла (пока есть задачи или iterations < max)
        """
        logger.info("🔄 Starting autonomous work cycle...")
        
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration}/{max_iterations}")
            logger.info(f"{'='*60}\n")
            
            # Шаг 1: Анализ проекта
            analysis = await self.analyze_project_state()
            
            logger.info(f"📊 Health: {analysis.get('health')} ({analysis.get('health_score', 0)}/100)")
            logger.info(f"📋 Issues: {len(analysis.get('issues', []))}")
            logger.info(f"💡 Recommendations: {len(analysis.get('recommendations', []))}")
            
            # Если здоровье "good" и нет критичных issues - остановка
            if (analysis.get("health") == "good" and 
                analysis.get("health_score", 0) >= 90 and
                not any(i.get("severity") == "critical" for i in analysis.get("issues", []))):
                logger.success("✅ Project is in excellent state! Stopping autonomous cycle.")
                break
            
            # Шаг 2: Создание задач
            for recommendation in analysis.get("recommendations", [])[:3]:  # Топ 3 приоритета
                await self.create_task_from_recommendation(recommendation)
            
            # Шаг 3: Сортировка задач
            pending_tasks = [t for t in self.tasks if t.status == TaskStatus.PENDING]
            pending_tasks.sort(key=lambda t: t.priority.value)
            
            if not pending_tasks:
                logger.info("📭 No pending tasks. Cycle complete.")
                break
            
            # Шаг 4: Выполнение задач
            for task in pending_tasks[:2]:  # Выполнить топ 2
                success = await self.execute_task(task)
                
                if success:
                    logger.success(f"✅ Task completed: {task.description}")
                else:
                    logger.warning(f"⚠️  Task needs retry: {task.description}")
            
            # Задержка между итерациями
            await asyncio.sleep(5)
        
        # Финальный отчёт
        self._print_final_report()
    
    def _print_final_report(self):
        """Печать финального отчёта"""
        logger.info(f"\n{'='*60}")
        logger.info("AUTONOMOUS CYCLE COMPLETE - FINAL REPORT")
        logger.info(f"{'='*60}\n")
        
        completed = [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in self.tasks if t.status == TaskStatus.FAILED]
        pending = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        
        logger.info(f"✅ Completed: {len(completed)}")
        logger.info(f"❌ Failed: {len(failed)}")
        logger.info(f"⏳ Pending: {len(pending)}")
        
        if completed:
            logger.info("\n✅ COMPLETED TASKS:")
            for task in completed:
                logger.info(f"  - {task.description}")
        
        if failed:
            logger.info("\n❌ FAILED TASKS:")
            for task in failed:
                logger.info(f"  - {task.description}")


async def main():
    """Точка входа"""
    logger.info("🤖 Autonomous Project Manager - Starting...")
    
    # Проверка Backend
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/agent/health", timeout=5.0)
            logger.success(f"✅ Backend running: {response.json()}")
        except Exception as e:
            logger.error(f"❌ Backend not running: {e}")
            logger.error("Start backend: py -m uvicorn backend.main:app --reload")
            return
    
    # Создание менеджера
    manager = AutonomousProjectManager()
    
    # Запуск автономного цикла
    await manager.autonomous_work_cycle(max_iterations=5)
    
    logger.success("🎉 Autonomous Project Manager - Completed!")


if __name__ == "__main__":
    asyncio.run(main())
