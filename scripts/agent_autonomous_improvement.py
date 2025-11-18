"""
Autonomous Agent Self-Improvement Task
Автономное самосовершенствование агентов через консенсус

Цикл: Анализ → Консенсус → Работа → Анализ → Консенсус → Работа
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any


class AgentSelfImprovementOrchestrator:
    """Оркестратор самосовершенствования агентов"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.conversation_history: List[Dict[str, Any]] = []
        self.cycle_results: List[Dict[str, Any]] = []
        
    async def send_message(self, from_agent: str, to_agent: str, content: str, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Отправить сообщение между агентами"""
        
        payload = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "content": content,
            "context": context or {"use_file_access": True}
        }
        
        # Increased timeout for file_access and complex analysis
        timeout_config = httpx.Timeout(600.0, connect=10.0, read=600.0)
        
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/send",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                self.conversation_history.append({
                    "from": from_agent,
                    "to": to_agent,
                    "content": content[:100] + "...",
                    "response": result.get("content", "")[:200] + "...",
                    "iteration": result.get("iteration"),
                    "timestamp": datetime.now().isoformat()
                })
                return result
            else:
                raise Exception(f"API Error: {response.status_code}")
    
    async def get_consensus(self, question: str, agents: List[str]) -> Dict[str, Any]:
        """Получить консенсусное решение от нескольких агентов"""
        
        payload = {
            "question": question,
            "agents": agents,
            "context": {"use_file_access": True}
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/consensus",
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Consensus API Error: {response.status_code}")
    
    async def run_improvement_cycle(self, cycle_number: int) -> Dict[str, Any]:
        """Выполнить один цикл улучшения"""
        
        print(f"\n{'='*80}")
        print(f"ЦИКЛ {cycle_number}: АВТОНОМНОЕ САМОСОВЕРШЕНСТВОВАНИЕ")
        print(f"{'='*80}\n")
        
        cycle_start = datetime.now()
        
        # ============================================================
        # ШАГ 1: DeepSeek - Анализ текущего состояния
        # ============================================================
        print(f"[Цикл {cycle_number}] Шаг 1: DeepSeek анализирует текущее состояние агентов...")
        
        analysis_task = f"""
Цикл самосовершенствования #{cycle_number}

ЗАДАЧА: Проанализируй текущее состояние агентской системы и определи области для улучшения.

ИСПОЛЬЗУЙ MCP TOOLS:
1. mcp_read_project_file для чтения ключевых файлов:
   - backend/agents/unified_agent_interface.py
   - backend/agents/agent_to_agent_communicator.py
   - backend/api/agent_to_agent_api.py

2. mcp_analyze_code_quality для проверки качества кода

АНАЛИЗИРУЙ:
- Текущие возможности агентов
- Качество кода и архитектуру
- Потенциальные улучшения
- Проблемы и узкие места

РЕЗУЛЬТАТ: Структурированный отчет с конкретными рекомендациями.
"""
        
        deepseek_analysis = await self.send_message(
            "copilot", "deepseek", analysis_task,
            {"use_file_access": True, "task_type": "self_improvement_analysis", "cycle": cycle_number}
        )
        
        print(f"✓ DeepSeek завершил анализ (iteration: {deepseek_analysis.get('iteration')})")
        print(f"  Ответ: {deepseek_analysis.get('content', '')[:300]}...\n")
        
        # ============================================================
        # ШАГ 2: Perplexity - Экспертная оценка и альтернативы
        # ============================================================
        print(f"[Цикл {cycle_number}] Шаг 2: Perplexity оценивает анализ DeepSeek...")
        
        perplexity_review = f"""
Экспертная оценка анализа DeepSeek (Цикл #{cycle_number})

АНАЛИЗ ОТ DEEPSEEK:
{deepseek_analysis.get('content', '')[:1000]}

ТВОЯ ЗАДАЧА:
1. Оцени качество и полноту анализа DeepSeek
2. Предложи альтернативные подходы
3. Выяви упущенные аспекты
4. Предложи дополнительные улучшения

ВАЖНО: Используй свой опыт и знания best practices для AI систем.
"""
        
        perplexity_response = await self.send_message(
            "copilot", "perplexity", perplexity_review,
            {"task_type": "expert_review", "cycle": cycle_number}
        )
        
        print(f"✓ Perplexity завершил оценку (iteration: {perplexity_response.get('iteration')})")
        print(f"  Ответ: {perplexity_response.get('content', '')[:300]}...\n")
        
        # ============================================================
        # ШАГ 3: Консенсус - Совместное решение
        # ============================================================
        print(f"[Цикл {cycle_number}] Шаг 3: Получение консенсусного решения...")
        
        consensus_question = f"""
На основе анализа (Цикл #{cycle_number}), какие ТРИ наиболее приоритетных улучшения 
следует внести в агентскую систему?

Анализ DeepSeek (краткая выжимка):
{deepseek_analysis.get('content', '')[:500]}

Оценка Perplexity (краткая выжимка):
{perplexity_response.get('content', '')[:500]}

Требуется: Конкретный список из 3 улучшений с обоснованием.
"""
        
        consensus = await self.get_consensus(
            consensus_question,
            ["deepseek", "perplexity"]
        )
        
        print(f"✓ Консенсус достигнут")
        print(f"  Результат: {str(consensus)[:400]}...\n")
        
        # ============================================================
        # ШАГ 4: DeepSeek - Разработка плана улучшений
        # ============================================================
        print(f"[Цикл {cycle_number}] Шаг 4: DeepSeek разрабатывает план реализации...")
        
        implementation_plan = f"""
Разработка плана улучшений (Цикл #{cycle_number})

КОНСЕНСУСНОЕ РЕШЕНИЕ:
{json.dumps(consensus, indent=2, ensure_ascii=False)[:800]}

ТВОЯ ЗАДАЧА:
1. Прочитай текущий код используя mcp_read_project_file
2. Разработай детальный план реализации улучшений
3. Определи конкретные файлы и функции для изменения
4. Укажи номера строк и точные изменения
5. Оцени риски и зависимости

ФОРМАТ: Пошаговый план с конкретным кодом и обоснованием.
"""
        
        plan_response = await self.send_message(
            "copilot", "deepseek", implementation_plan,
            {"use_file_access": True, "task_type": "implementation_planning", "cycle": cycle_number}
        )
        
        print(f"✓ DeepSeek разработал план (iteration: {plan_response.get('iteration')})")
        print(f"  План: {plan_response.get('content', '')[:300]}...\n")
        
        # ============================================================
        # ШАГ 5: Perplexity - Валидация плана
        # ============================================================
        print(f"[Цикл {cycle_number}] Шаг 5: Perplexity валидирует план...")
        
        validation_task = f"""
Валидация плана реализации (Цикл #{cycle_number})

ПЛАН ОТ DEEPSEEK:
{plan_response.get('content', '')[:1000]}

ТВОЯ ЗАДАЧА:
1. Оцени безопасность предложенных изменений
2. Проверь, не нарушат ли изменения существующую функциональность
3. Выяви потенциальные проблемы
4. Предложи корректировки если нужно

ВЫВОД: ОДОБРЕН / ТРЕБУЮТСЯ ИЗМЕНЕНИЯ / ОТКЛОНЕН (с обоснованием)
"""
        
        validation_response = await self.send_message(
            "copilot", "perplexity", validation_task,
            {"task_type": "plan_validation", "cycle": cycle_number}
        )
        
        print(f"✓ Perplexity завершил валидацию (iteration: {validation_response.get('iteration')})")
        print(f"  Статус: {validation_response.get('content', '')[:300]}...\n")
        
        # ============================================================
        # ШАГ 6: DeepSeek - Финальная реализация (если одобрено)
        # ============================================================
        validation_text = validation_response.get('content', '').lower()
        
        if "одобрен" in validation_text or "approved" in validation_text:
            print(f"[Цикл {cycle_number}] Шаг 6: DeepSeek реализует утвержденные улучшения...")
            
            implementation_task = f"""
Реализация улучшений (Цикл #{cycle_number})

УТВЕРЖДЕННЫЙ ПЛАН:
{plan_response.get('content', '')[:800]}

ВАЛИДАЦИЯ PERPLEXITY:
{validation_response.get('content', '')[:500]}

ЗАДАЧА: Предоставь точный код для реализации улучшений.

ВАЖНО:
- Используй mcp_read_project_file для чтения текущего кода
- Предоставь ПОЛНЫЙ код изменений (не псевдокод)
- Укажи точные файлы и расположение
- Объясни каждое изменение

ФОРМАТ:
```python
# Файл: path/to/file.py
# Строки: X-Y
# Изменение: описание

<полный код>
```
"""
            
            implementation_response = await self.send_message(
                "copilot", "deepseek", implementation_task,
                {"use_file_access": True, "task_type": "implementation", "cycle": cycle_number}
            )
            
            print(f"✓ DeepSeek предоставил реализацию (iteration: {implementation_response.get('iteration')})")
            print(f"  Код: {implementation_response.get('content', '')[:500]}...\n")
            
        else:
            print(f"⚠ План требует доработки или отклонен\n")
            implementation_response = {"content": "Plan rejected or requires changes", "iteration": 0}
        
        # ============================================================
        # Сохранение результатов цикла
        # ============================================================
        cycle_result = {
            "cycle": cycle_number,
            "timestamp": cycle_start.isoformat(),
            "duration_seconds": (datetime.now() - cycle_start).total_seconds(),
            "steps": {
                "1_analysis": {
                    "agent": "deepseek",
                    "iteration": deepseek_analysis.get("iteration"),
                    "summary": deepseek_analysis.get("content", "")[:500]
                },
                "2_review": {
                    "agent": "perplexity",
                    "iteration": perplexity_response.get("iteration"),
                    "summary": perplexity_response.get("content", "")[:500]
                },
                "3_consensus": {
                    "agents": ["deepseek", "perplexity"],
                    "result": consensus
                },
                "4_planning": {
                    "agent": "deepseek",
                    "iteration": plan_response.get("iteration"),
                    "summary": plan_response.get("content", "")[:500]
                },
                "5_validation": {
                    "agent": "perplexity",
                    "iteration": validation_response.get("iteration"),
                    "approved": "одобрен" in validation_text or "approved" in validation_text,
                    "summary": validation_response.get("content", "")[:500]
                },
                "6_implementation": {
                    "agent": "deepseek",
                    "iteration": implementation_response.get("iteration"),
                    "summary": implementation_response.get("content", "")[:500]
                }
            }
        }
        
        self.cycle_results.append(cycle_result)
        
        return cycle_result
    
    async def run_multi_cycle_improvement(self, num_cycles: int = 3):
        """Запустить несколько циклов самосовершенствования"""
        
        print("\n" + "="*80)
        print("🤖 АВТОНОМНОЕ САМОСОВЕРШЕНСТВОВАНИЕ АГЕНТОВ")
        print("="*80)
        print(f"\nЗапуск {num_cycles} циклов улучшений...")
        print(f"Паттерн: DeepSeek → Perplexity → Consensus → DeepSeek → Perplexity → DeepSeek\n")
        
        # Проверка backend
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/v1/health")
                if response.status_code != 200:
                    print(f"❌ Backend недоступен: {response.status_code}")
                    return
                print("✓ Backend работает\n")
        except Exception as e:
            print(f"❌ Ошибка подключения к backend: {e}")
            return
        
        # Выполнение циклов
        for cycle_num in range(1, num_cycles + 1):
            try:
                result = await self.run_improvement_cycle(cycle_num)
                
                print(f"\n{'='*80}")
                print(f"✅ ЦИКЛ {cycle_num} ЗАВЕРШЕН")
                print(f"{'='*80}")
                print(f"Длительность: {result['duration_seconds']:.1f}с")
                print(f"Итераций DeepSeek: {result['steps']['1_analysis']['iteration']}")
                print(f"План одобрен: {'Да' if result['steps']['5_validation']['approved'] else 'Нет'}")
                print()
                
                # Пауза между циклами
                if cycle_num < num_cycles:
                    print(f"⏳ Пауза 5 секунд перед следующим циклом...\n")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                print(f"❌ Ошибка в цикле {cycle_num}: {e}")
                import traceback
                traceback.print_exc()
                break
        
        # ============================================================
        # Финальный отчет
        # ============================================================
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНЫЙ ОТЧЕТ")
        print("="*80)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"AGENT_SELF_IMPROVEMENT_REPORT_{timestamp}.json"
        
        final_report = {
            "summary": {
                "total_cycles": len(self.cycle_results),
                "total_duration": sum(r["duration_seconds"] for r in self.cycle_results),
                "approved_plans": sum(1 for r in self.cycle_results if r["steps"]["5_validation"]["approved"]),
                "timestamp": datetime.now().isoformat()
            },
            "cycles": self.cycle_results,
            "conversation_history": self.conversation_history
        }
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Отчет сохранен: {report_file}")
        print(f"\nВсего циклов: {final_report['summary']['total_cycles']}")
        print(f"Одобренных планов: {final_report['summary']['approved_plans']}")
        print(f"Общее время: {final_report['summary']['total_duration']:.1f}с")
        print(f"Сообщений между агентами: {len(self.conversation_history)}")
        
        print("\n" + "="*80)
        print("🎉 АВТОНОМНОЕ САМОСОВЕРШЕНСТВОВАНИЕ ЗАВЕРШЕНО")
        print("="*80 + "\n")


async def main():
    """Главная функция"""
    orchestrator = AgentSelfImprovementOrchestrator()
    await orchestrator.run_multi_cycle_improvement(num_cycles=3)


if __name__ == "__main__":
    asyncio.run(main())
