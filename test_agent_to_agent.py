"""
Тестирование Agent-to-Agent Communication System
С автоматической отправкой результатов DeepSeek Agent для анализа
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.agent_to_agent_communicator import (
    AgentToAgentCommunicator,
    AgentMessage,
    AgentType,
    MessageType,
    CommunicationPattern,
    get_communicator
)
from backend.agents.unified_agent_interface import (
    get_agent_interface,
    AgentRequest,
    AgentType as UnifiedAgentType
)
from loguru import logger


class AgentToAgentTester:
    """Тестирование Agent-to-Agent системы с DeepSeek validation"""
    
    def __init__(self):
        self.communicator = get_communicator()
        self.agent_interface = get_agent_interface()
        self.test_results = []
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        logger.info("🚀 Starting Agent-to-Agent Communication System tests...")
        logger.info("=" * 80)
        
        tests = [
            ("Basic Message Routing", self.test_basic_routing),
            ("DeepSeek ⇄ Perplexity Collaboration", self.test_collaborative_pattern),
            ("Multi-Agent Consensus", self.test_parallel_consensus),
            ("Iterative Improvement", self.test_iterative_improvement),
            ("Multi-Turn Conversation", self.test_multi_turn_conversation),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n📝 Test: {test_name}")
            logger.info("-" * 80)
            
            try:
                start_time = datetime.now()
                result = await test_func()
                duration = (datetime.now() - start_time).total_seconds()
                
                self.test_results.append({
                    "test_name": test_name,
                    "success": True,
                    "duration_seconds": duration,
                    "result": result
                })
                
                logger.success(f"✅ {test_name} PASSED ({duration:.2f}s)")
                
            except Exception as e:
                logger.error(f"❌ {test_name} FAILED: {e}")
                self.test_results.append({
                    "test_name": test_name,
                    "success": False,
                    "error": str(e)
                })
        
        # Отправить результаты DeepSeek для анализа
        await self.send_results_to_deepseek()
    
    async def test_basic_routing(self) -> Dict:
        """Тест базовой маршрутизации сообщений"""
        logger.info("Testing: Copilot → DeepSeek → Copilot")
        
        message = AgentMessage(
            message_id="test-001",
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="Объясни концепцию Agent-to-Agent communication в 2-3 предложениях",
            context={"test": "basic_routing"},
            conversation_id="conv-test-001"
        )
        
        response = await self.communicator.route_message(message)
        
        assert response.from_agent == AgentType.DEEPSEEK
        assert response.message_type == MessageType.RESPONSE
        assert len(response.content) > 50, "Response too short"
        
        logger.info(f"Response from DeepSeek: {response.content[:200]}...")
        
        return {
            "message_id": response.message_id,
            "content_length": len(response.content),
            "latency_ms": response.metadata.get("latency_ms", 0),
            "confidence": response.confidence_score
        }
    
    async def test_collaborative_pattern(self) -> Dict:
        """Тест коллаборативного паттерна: DeepSeek ⇄ Perplexity"""
        logger.info("Testing: DeepSeek ⇄ Perplexity collaboration")
        
        initial_message = AgentMessage(
            message_id="test-002",
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="Какие последние тренды в AI agent architecture? (DeepSeek → Perplexity для поиска → DeepSeek для анализа)",
            context={"test": "collaborative"},
            conversation_id="conv-test-002",
            max_iterations=3
        )
        
        history = await self.communicator.multi_turn_conversation(
            initial_message=initial_message,
            max_turns=3,
            pattern=CommunicationPattern.COLLABORATIVE
        )
        
        assert len(history) >= 2, "Conversation too short"
        
        logger.info(f"Conversation length: {len(history)} messages")
        for msg in history:
            logger.info(f"  {msg.from_agent.value} → {msg.to_agent.value}: {msg.content[:100]}...")
        
        return {
            "messages_count": len(history),
            "participants": list(set([msg.from_agent.value for msg in history])),
            "completed": history[-1].message_type == MessageType.COMPLETION
        }
    
    async def test_parallel_consensus(self) -> Dict:
        """Тест параллельного консенсуса от DeepSeek и Perplexity"""
        logger.info("Testing: Parallel consensus from multiple agents")
        
        result = await self.communicator.parallel_consensus(
            question="Какие основные преимущества Agent-to-Agent communication over MCP tools?",
            agents=[AgentType.DEEPSEEK, AgentType.PERPLEXITY]
        )
        
        assert "consensus" in result
        assert len(result["individual_responses"]) == 2
        
        logger.info(f"Consensus confidence: {result['confidence_score']:.2f}")
        logger.info(f"Consensus: {result['consensus'][:200]}...")
        
        return {
            "consensus_confidence": result["confidence_score"],
            "agents_count": len(result["individual_responses"]),
            "consensus_length": len(result["consensus"])
        }
    
    async def test_iterative_improvement(self) -> Dict:
        """Тест итеративного улучшения с валидацией"""
        logger.info("Testing: Iterative improvement with validation")
        
        initial_code = """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
"""
        
        result = await self.communicator.iterative_improvement(
            initial_task=f"Оптимизируй этот код:\n{initial_code}",
            validator_agent=AgentType.PERPLEXITY,
            improver_agent=AgentType.DEEPSEEK,
            max_iterations=2,
            min_confidence=0.7
        )
        
        assert "final_content" in result
        assert len(result["iterations"]) <= 2
        
        logger.info(f"Iterations: {len(result['iterations'])}")
        logger.info(f"Final confidence: {result['final_confidence']:.2f}")
        logger.info(f"Success: {result['success']}")
        
        return {
            "iterations_count": len(result["iterations"]),
            "final_confidence": result["final_confidence"],
            "success": result["success"]
        }
    
    async def test_multi_turn_conversation(self) -> Dict:
        """Тест multi-turn разговора с разными паттернами"""
        logger.info("Testing: Multi-turn conversation (sequential pattern)")
        
        initial_message = AgentMessage(
            message_id="test-005",
            from_agent=AgentType.COPILOT,
            to_agent=AgentType.DEEPSEEK,
            message_type=MessageType.QUERY,
            content="Начнём обсуждение: как оптимизировать latency в Agent-to-Agent системе?",
            context={"test": "multi_turn"},
            conversation_id="conv-test-005",
            max_iterations=4
        )
        
        history = await self.communicator.multi_turn_conversation(
            initial_message=initial_message,
            max_turns=4,
            pattern=CommunicationPattern.SEQUENTIAL
        )
        
        logger.info(f"Conversation history: {len(history)} messages")
        
        return {
            "messages_count": len(history),
            "max_iterations_reached": history[-1].iteration >= 4,
            "completion_type": history[-1].message_type.value
        }
    
    async def send_results_to_deepseek(self):
        """Отправить результаты тестов DeepSeek Agent для анализа"""
        logger.info("\n" + "=" * 80)
        logger.info("📤 Sending test results to DeepSeek Agent for analysis...")
        logger.info("=" * 80)
        
        # Форматирование результатов
        results_summary = self._format_results_summary()
        
        prompt = f"""
# АНАЛИЗ РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ AGENT-TO-AGENT COMMUNICATION SYSTEM

## Результаты тестов

{results_summary}

## Задачи для анализа

1. **Оценка качества**: Проанализируй результаты каждого теста
2. **Выявление проблем**: Есть ли failed тесты или низкие показатели?
3. **Performance анализ**: Оцени latency и throughput
4. **Рекомендации**: Что нужно улучшить в первую очередь?
5. **Next Steps**: Предложи конкретные шаги для оптимизации

Пожалуйста, дай краткий actionable анализ (5-7 ключевых пунктов).
"""
        
        request = AgentRequest(
            agent_type=UnifiedAgentType.DEEPSEEK,
            task_type="test_results_analysis",
            prompt=prompt,
            context={"test_results": self.test_results}
        )
        
        response = await self.agent_interface.send_request(request)
        
        if response.success:
            logger.success(f"✅ DeepSeek analysis completed ({response.latency_ms}ms)")
            logger.info("=" * 80)
            logger.info("📊 DEEPSEEK ANALYSIS:")
            logger.info("=" * 80)
            print(response.content)
            logger.info("=" * 80)
            
            # Сохранить анализ
            output_file = Path(__file__).parent / "AGENT_TO_AGENT_TEST_ANALYSIS.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("# Agent-to-Agent Communication System - Test Analysis\n\n")
                f.write(f"**Test Date**: {datetime.now().isoformat()}\n\n")
                f.write("## Test Results Summary\n\n")
                f.write(results_summary)
                f.write("\n\n## DeepSeek Analysis\n\n")
                f.write(response.content)
            
            logger.success(f"💾 Analysis saved to: {output_file}")
        else:
            logger.error(f"❌ DeepSeek analysis failed: {response.error}")
    
    def _format_results_summary(self) -> str:
        """Форматирование результатов для отправки DeepSeek"""
        lines = []
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        
        lines.append(f"**Total Tests**: {total_tests}")
        lines.append(f"**Passed**: {passed_tests} ✅")
        lines.append(f"**Failed**: {failed_tests} ❌")
        lines.append("")
        
        for result in self.test_results:
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            lines.append(f"### {result['test_name']} - {status}")
            
            if result["success"]:
                duration = result.get("duration_seconds", 0)
                lines.append(f"- Duration: {duration:.2f}s")
                
                # Детали результата
                test_result = result.get("result", {})
                for key, value in test_result.items():
                    lines.append(f"- {key}: {value}")
            else:
                lines.append(f"- Error: {result.get('error', 'Unknown error')}")
            
            lines.append("")
        
        return "\n".join(lines)


async def main():
    """Main test runner"""
    logger.info("🧪 Agent-to-Agent Communication System Test Suite")
    logger.info("=" * 80)
    logger.info("Features:")
    logger.info("  ✅ Basic message routing")
    logger.info("  ✅ Collaborative patterns (DeepSeek ⇄ Perplexity)")
    logger.info("  ✅ Parallel consensus")
    logger.info("  ✅ Iterative improvement with validation")
    logger.info("  ✅ Multi-turn conversations")
    logger.info("  ✅ Automatic DeepSeek analysis of results")
    logger.info("=" * 80)
    logger.info("")
    
    tester = AgentToAgentTester()
    await tester.run_all_tests()
    
    # Итоговая сводка
    logger.info("\n" + "=" * 80)
    logger.info("📊 FINAL SUMMARY")
    logger.info("=" * 80)
    
    total = len(tester.test_results)
    passed = sum(1 for r in tester.test_results if r["success"])
    failed = total - passed
    
    logger.info(f"Total tests: {total}")
    logger.success(f"Passed: {passed} ✅")
    if failed > 0:
        logger.error(f"Failed: {failed} ❌")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    logger.info(f"Success rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        logger.success("🎉 ALL TESTS PASSED! Agent-to-Agent system working perfectly!")
    elif success_rate >= 80:
        logger.warning("⚠️ Most tests passed, but some issues detected. Check analysis.")
    else:
        logger.error("❌ Multiple test failures. System needs fixes.")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
