#!/usr/bin/env python3
"""
Получение рекомендаций от DeepSeek и Perplexity агентов
Обход падающего MCP сервера через прямые API вызовы
"""

import os
import json
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


class AgentConsultant:
    """Прямая консультация с AI агентами"""
    
    def __init__(self):
        # DeepSeek API keys
        self.deepseek_keys = [
            os.getenv(f"DEEPSEEK_API_KEY_{i}") 
            for i in range(1, 9)
            if os.getenv(f"DEEPSEEK_API_KEY_{i}")
        ]
        
        # Perplexity API keys
        self.perplexity_keys = [
            os.getenv(f"PERPLEXITY_API_KEY_{i}") 
            for i in range(1, 5)
            if os.getenv(f"PERPLEXITY_API_KEY_{i}")
        ]
        
        self.deepseek_base_url = "https://api.deepseek.com/v1"
        self.perplexity_base_url = "https://api.perplexity.ai"
        
        self.current_deepseek_key_idx = 0
        self.current_perplexity_key_idx = 0
    
    def get_next_deepseek_key(self) -> str:
        """Ротация DeepSeek ключей"""
        if not self.deepseek_keys:
            raise ValueError("No DeepSeek API keys found!")
        
        key = self.deepseek_keys[self.current_deepseek_key_idx]
        self.current_deepseek_key_idx = (self.current_deepseek_key_idx + 1) % len(self.deepseek_keys)
        return key
    
    def get_next_perplexity_key(self) -> str:
        """Ротация Perplexity ключей"""
        if not self.perplexity_keys:
            raise ValueError("No Perplexity API keys found!")
        
        key = self.perplexity_keys[self.current_perplexity_key_idx]
        self.current_perplexity_key_idx = (self.current_perplexity_key_idx + 1) % len(self.perplexity_keys)
        return key
    
    async def ask_deepseek(self, question: str, retry_count: int = 3) -> str:
        """Консультация с DeepSeek Agent"""
        
        for attempt in range(retry_count):
            try:
                api_key = self.get_next_deepseek_key()
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.deepseek_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a senior reliability engineer consultant with expertise in distributed systems, circuit breakers, and API resilience patterns."
                                },
                                {
                                    "role": "user",
                                    "content": question
                                }
                            ],
                            "temperature": 0.7,
                            "max_tokens": 2000
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        print(f"⚠️ DeepSeek attempt {attempt + 1} failed: {response.status_code}")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
            except Exception as e:
                print(f"❌ DeepSeek error on attempt {attempt + 1}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return "⚠️ Failed to get response from DeepSeek after all retries"
    
    async def ask_perplexity(self, question: str, retry_count: int = 3) -> str:
        """Консультация с Perplexity Agent"""
        
        for attempt in range(retry_count):
            try:
                api_key = self.get_next_perplexity_key()
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.perplexity_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "sonar-pro",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a technical consultant specializing in API reliability, real-time search, and production best practices."
                                },
                                {
                                    "role": "user",
                                    "content": question
                                }
                            ]
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        print(f"⚠️ Perplexity attempt {attempt + 1} failed: {response.status_code}")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2 ** attempt)
                        
            except Exception as e:
                print(f"❌ Perplexity error on attempt {attempt + 1}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return "⚠️ Failed to get response from Perplexity after all retries"


async def main():
    """Основная функция"""
    
    print("=" * 80)
    print("🤖 КОНСУЛЬТАЦИЯ С AI АГЕНТАМИ: DeepSeek + Perplexity")
    print("=" * 80)
    print()
    
    consultant = AgentConsultant()
    
    # Вопросы для консультации
    questions = [
        {
            "agent": "DeepSeek",
            "topic": "Circuit Breaker Implementation",
            "question": """
How should we implement a production-ready Circuit Breaker pattern for our system with these requirements?
- Multiple API services (DeepSeek, Perplexity, MCP server)
- Target: 99.99% uptime
- Need auto-recovery in < 30 seconds
- Must prevent cascading failures

Please provide:
1. Best practices for circuit breaker states (CLOSED/OPEN/HALF_OPEN)
2. Optimal failure thresholds and timeouts
3. Testing strategies
4. Common pitfalls to avoid
"""
        },
        {
            "agent": "DeepSeek",
            "topic": "API Key Rotation Strategy",
            "question": """
We have 8 DeepSeek API keys and 4 Perplexity keys. How should we implement intelligent key rotation to:
- Avoid governor restrictions and rate limits
- Distribute load evenly
- Handle "Authentication Fails (governor)" errors
- Implement cooldown periods for blocked keys

What's the optimal rotation algorithm and monitoring approach?
"""
        },
        {
            "agent": "Perplexity",
            "topic": "MCP Server Auto-Recovery",
            "question": """
Our MCP (Model Context Protocol) server keeps crashing with:
- stdio/JSON-RPC conflicts
- KeyboardInterrupt handling issues
- No auto-restart mechanism

What are the best practices for:
1. Process supervision (systemd vs supervisord vs custom)
2. Graceful shutdown handling
3. Auto-restart rate limiting
4. Health monitoring
5. Log management without stdio conflicts
"""
        },
        {
            "agent": "Perplexity",
            "topic": "99.99% Uptime Architecture",
            "question": """
How do companies like Netflix, Google, and AWS achieve 99.99% uptime?

We need specific recommendations for:
1. Retry policies with exponential backoff
2. Service mesh considerations
3. Chaos engineering validation
4. MTBF and MTTR optimization
5. Zero manual intervention strategies

What are the proven patterns for production reliability?
"""
        }
    ]
    
    recommendations = []
    
    for i, q in enumerate(questions, 1):
        print(f"\n{'='*80}")
        print(f"📋 Question {i}/{len(questions)}: {q['topic']}")
        print(f"🤖 Agent: {q['agent']}")
        print(f"{'='*80}\n")
        
        if q['agent'] == "DeepSeek":
            response = await consultant.ask_deepseek(q['question'])
        else:
            response = await consultant.ask_perplexity(q['question'])
        
        recommendations.append({
            "agent": q['agent'],
            "topic": q['topic'],
            "question": q['question'],
            "response": response
        })
        
        print(f"✅ Response received ({len(response)} chars)")
        print(f"\n{response}\n")
        
        # Небольшая задержка между запросами
        if i < len(questions):
            await asyncio.sleep(2)
    
    # Сохранение результатов
    output_file = Path("AGENT_RECOMMENDATIONS.md")
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# 🤖 AI AGENTS RECOMMENDATIONS\n\n")
        f.write(f"**Date**: {asyncio.get_event_loop().time()}\n")
        f.write(f"**DeepSeek Keys**: {len(consultant.deepseek_keys)}\n")
        f.write(f"**Perplexity Keys**: {len(consultant.perplexity_keys)}\n\n")
        f.write("---\n\n")
        
        for rec in recommendations:
            f.write(f"## {rec['topic']}\n\n")
            f.write(f"**Agent**: {rec['agent']}\n\n")
            f.write(f"**Question**:\n```\n{rec['question']}\n```\n\n")
            f.write(f"**Response**:\n\n{rec['response']}\n\n")
            f.write("---\n\n")
    
    print(f"\n{'='*80}")
    print(f"✅ Recommendations saved to: {output_file}")
    print(f"📊 Total questions: {len(questions)}")
    print(f"💾 File size: {output_file.stat().st_size} bytes")
    print(f"{'='*80}")
    
    return recommendations


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        raise
