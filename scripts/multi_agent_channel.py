#!/usr/bin/env python3
"""
Multi-Agent Communication Channel: DeepSeek ↔ Perplexity
Быстрый канал связи для совместной работы AI агентов
"""

import sys
import requests
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# API Keys через безопасный KeyManager (зашифрованное хранилище)
from backend.security.key_manager import get_decrypted_key

PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")

class MultiAgentChannel:
    """Канал связи между DeepSeek и Perplexity"""
    
    def __init__(self):
        self.conversation_history = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def deepseek_call(self, prompt: str, context: Optional[str] = None) -> Dict:
        """Вызов DeepSeek с контекстом"""
        messages = [
            {
                "role": "system",
                "content": "Ты технический эксперт по архитектуре и кодогенерации. Работаешь в команде с Perplexity AI."
            }
        ]
        
        if context:
            messages.append({
                "role": "user",
                "content": f"КОНТЕКСТ от Perplexity:\n{context}\n\n---\n\n"
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return {
                "success": True,
                "content": content,
                "agent": "DeepSeek",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"DeepSeek error {response.status_code}: {response.text}",
                "agent": "DeepSeek"
            }
    
    def perplexity_call(self, prompt: str, context: Optional[str] = None) -> Dict:
        """Вызов Perplexity с контекстом"""
        messages = [
            {
                "role": "system",
                "content": "Ты стратегический эксперт по бизнес-анализу и приоритизации. Работаешь в команде с DeepSeek."
            }
        ]
        
        if context:
            messages.append({
                "role": "user",
                "content": f"КОНТЕКСТ от DeepSeek:\n{context}\n\n---\n\n"
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": "sonar-pro",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            citations = result.get('citations', [])
            return {
                "success": True,
                "content": content,
                "citations": citations,
                "agent": "Perplexity",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"Perplexity error {response.status_code}: {response.text}",
                "agent": "Perplexity"
            }
    
    def collaborative_analysis(
        self,
        topic: str,
        deepseek_task: str,
        perplexity_task: str,
        iterations: int = 2
    ) -> List[Dict]:
        """
        Совместный анализ с обменом контекстом
        
        Args:
            topic: Тема анализа
            deepseek_task: Задача для DeepSeek
            perplexity_task: Задача для Perplexity
            iterations: Количество итераций обмена
        """
        results = []
        
        print("=" * 80)
        print(f"COLLABORATIVE ANALYSIS: {topic}")
        print("=" * 80)
        print()
        
        # Итерация 1: Параллельный анализ
        print("🔄 ITERATION 1: Параллельный анализ")
        print()
        
        print("📤 DeepSeek: Технический анализ...")
        deepseek_result = self.deepseek_call(deepseek_task)
        results.append(deepseek_result)
        
        if deepseek_result["success"]:
            print(f"✅ DeepSeek готов ({len(deepseek_result['content'])} chars)")
        else:
            print(f"❌ DeepSeek failed: {deepseek_result['error']}")
            return results
        
        print()
        print("📤 Perplexity: Стратегический анализ...")
        perplexity_result = self.perplexity_call(perplexity_task)
        results.append(perplexity_result)
        
        if perplexity_result["success"]:
            print(f"✅ Perplexity готов ({len(perplexity_result['content'])} chars)")
            print(f"📚 Citations: {len(perplexity_result.get('citations', []))}")
        else:
            print(f"❌ Perplexity failed: {perplexity_result['error']}")
            return results
        
        # Итерация 2+: Обмен контекстом
        for i in range(2, iterations + 1):
            print()
            print(f"🔄 ITERATION {i}: Обмен контекстом и уточнения")
            print()
            
            # DeepSeek анализирует выводы Perplexity
            deepseek_followup = f"""Проанализируй стратегические рекомендации Perplexity и дай технические уточнения:

ЗАДАЧА: {deepseek_task}

Что добавить/изменить в техническом плане на основе стратегии?"""
            
            print("📤 DeepSeek: Технические уточнения на основе стратегии Perplexity...")
            deepseek_result = self.deepseek_call(
                deepseek_followup,
                context=perplexity_result["content"][:2000]  # Первые 2000 символов
            )
            results.append(deepseek_result)
            
            if deepseek_result["success"]:
                print(f"✅ DeepSeek готов ({len(deepseek_result['content'])} chars)")
            else:
                print(f"❌ DeepSeek failed")
                break
            
            print()
            
            # Perplexity анализирует технические детали DeepSeek
            perplexity_followup = f"""На основе технического анализа DeepSeek дай стратегические рекомендации:

ЗАДАЧА: {perplexity_task}

Как приоритизировать реализацию? Какие риски?"""
            
            print("📤 Perplexity: Стратегические уточнения на основе технического анализа...")
            perplexity_result = self.perplexity_call(
                perplexity_followup,
                context=deepseek_result["content"][:2000]
            )
            results.append(perplexity_result)
            
            if perplexity_result["success"]:
                print(f"✅ Perplexity готов ({len(perplexity_result['content'])} chars)")
            else:
                print(f"❌ Perplexity failed")
                break
        
        return results
    
    def save_session(self, results: List[Dict], filename: str):
        """Сохранение сессии совместной работы"""
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        output_path = Path(filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # Создаём также markdown версию
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Multi-Agent Collaboration Session\n\n")
            f.write(f"**Session ID:** {self.session_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            for i, result in enumerate(results, 1):
                if not result.get("success"):
                    continue
                    
                agent = result.get("agent", "Unknown")
                content = result.get("content", "")
                timestamp = result.get("timestamp", "")
                
                f.write(f"## {i}. {agent} ({timestamp})\n\n")
                f.write(content)
                f.write("\n\n")
                
                if "citations" in result and result["citations"]:
                    f.write("### Citations\n\n")
                    for j, citation in enumerate(result["citations"], 1):
                        f.write(f"{j}. {citation}\n")
                    f.write("\n")
                
                f.write("---\n\n")
        
        return md_path


def main():
    """Тестирование канала связи"""
    
    print("=" * 80)
    print("MULTI-AGENT COMMUNICATION CHANNEL TEST")
    print("=" * 80)
    print()
    
    channel = MultiAgentChannel()
    
    # Тестовая задача
    results = channel.collaborative_analysis(
        topic="Quick Wins Prioritization",
        deepseek_task="""Дай технический анализ:
- Сложность реализации Knowledge Base vs Sandbox
- Технические зависимости между компонентами
- Оценка времени разработки (реалистичная)""",
        perplexity_task="""Дай стратегические рекомендации:
- Приоритизация Quick Win #1 vs #2
- Business value каждого компонента
- Риски и митигации""",
        iterations=2
    )
    
    print()
    print("=" * 80)
    print("СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    print()
    
    md_path = channel.save_session(results, "multi_agent_session.json")
    print(f"✅ JSON сохранён: multi_agent_session.json")
    print(f"✅ Markdown сохранён: {md_path}")
    print()
    
    # Статистика
    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(results)
    
    print("=" * 80)
    print("СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего запросов: {total_count}")
    print(f"Успешных: {success_count}")
    print(f"Провалено: {total_count - success_count}")
    print(f"Success Rate: {success_count / total_count * 100:.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
