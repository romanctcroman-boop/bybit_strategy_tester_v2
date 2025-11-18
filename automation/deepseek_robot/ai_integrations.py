"""
🤝 AI Integrations для DeepSeek Robot

Интеграция с:
- DeepSeek API (глубокий анализ кода)
- Perplexity API (исследования, best practices)
- Copilot (через файлы, валидация)

Author: AI Collaboration System
Date: 2025-11-08
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AIResponse:
    """Ответ от AI системы"""
    success: bool
    content: str
    model: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    error: Optional[str] = None


class DeepSeekClient:
    """
    DeepSeek API Client для анализа кода
    
    Модели:
    - deepseek-coder: лучшая для кода
    - deepseek-chat: универсальная
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-coder",
        temperature: float = 0.1
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found")
        
        self.model = model
        self.temperature = temperature
        self.base_url = "https://api.deepseek.com/v1"
    
    async def analyze_code(
        self,
        code: str,
        instruction: str,
        context: Optional[str] = None
    ) -> AIResponse:
        """
        Анализ кода через DeepSeek
        
        Args:
            code: Код для анализа
            instruction: Инструкция (что найти/исправить)
            context: Дополнительный контекст
        
        Returns:
            Ответ от DeepSeek
        """
        prompt = f"""{instruction}

Code:
```python
{code}
```
"""
        
        if context:
            prompt += f"\n\nContext: {context}"
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert code analyzer. Provide structured analysis in JSON format when possible."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": self.temperature,
                        "max_tokens": 4000
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                return AIResponse(
                    success=True,
                    content=content,
                    model=self.model,
                    tokens_used=tokens
                )
        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                model=self.model,
                error=str(e)
            )
    
    async def generate_fix(
        self,
        problem_description: str,
        original_code: str,
        file_context: Optional[str] = None
    ) -> AIResponse:
        """
        Генерация исправления для проблемы
        
        Args:
            problem_description: Описание проблемы
            original_code: Исходный код
            file_context: Контекст файла
        
        Returns:
            Исправленный код
        """
        instruction = f"""Fix the following problem:

Problem: {problem_description}

Original code:
```python
{original_code}
```

Provide ONLY the fixed code, without explanations or markdown blocks.
Start directly with the code."""
        
        response = await self.analyze_code(
            code=original_code,
            instruction=instruction,
            context=file_context
        )
        
        return response
    
    async def refactor_code(
        self,
        code: str,
        improvements: str
    ) -> AIResponse:
        """
        Рефакторинг кода
        
        Args:
            code: Исходный код
            improvements: Какие улучшения нужны
        
        Returns:
            Улучшенный код
        """
        instruction = f"""Refactor the following code with these improvements: {improvements}

Provide:
1. Refactored code
2. Brief explanation of changes

Format:
```python
# Refactored code
```

Changes made:
- Change 1
- Change 2
"""
        
        return await self.analyze_code(code, instruction)


class PerplexityClient:
    """
    Perplexity API Client для исследований
    
    Модели:
    - sonar: быстрая модель с интернет-поиском
    - sonar-pro: мощная модель с интернет-поиском
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "sonar-pro"
    ):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not found")
        
        self.model = model
        self.base_url = "https://api.perplexity.ai"
    
    async def search(
        self,
        query: str,
        focus: Optional[str] = None
    ) -> AIResponse:
        """
        Поиск информации через Perplexity
        
        Args:
            query: Поисковый запрос
            focus: Фокус поиска (writing, internet, etc.)
        
        Returns:
            Результаты поиска
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": query
                        }
                    ]
                }
                
                if focus:
                    payload["search_recency_filter"] = focus
                
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                return AIResponse(
                    success=True,
                    content=content,
                    model=self.model,
                    tokens_used=tokens
                )
        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                model=self.model,
                error=str(e)
            )
    
    async def research_best_practices(
        self,
        topic: str,
        language: str = "python"
    ) -> AIResponse:
        """
        Исследование best practices
        
        Args:
            topic: Тема исследования
            language: Язык программирования
        
        Returns:
            Best practices
        """
        query = f"Best practices for {topic} in {language} programming. Latest 2025 recommendations."
        return await self.search(query)
    
    async def find_solution(
        self,
        problem: str,
        context: Optional[str] = None
    ) -> AIResponse:
        """
        Поиск решения проблемы
        
        Args:
            problem: Описание проблемы
            context: Контекст (версии, окружение)
        
        Returns:
            Решение проблемы
        """
        query = f"How to solve: {problem}"
        if context:
            query += f"\n\nContext: {context}"
        
        return await self.search(query)


class CopilotIntegration:
    """
    Интеграция с GitHub Copilot
    
    Copilot доступен через:
    1. VS Code API (если работаем в расширении)
    2. Файловую систему (создаём файлы с контекстом)
    3. Комментарии в коде (Copilot подсказывает)
    
    Для автономного робота используем подход через файлы:
    - Создаём .copilot/ директорию
    - Сохраняем контекст в JSON
    - Copilot читает и предлагает улучшения
    """
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.copilot_dir = self.project_root / ".copilot"
        self.copilot_dir.mkdir(exist_ok=True)
    
    async def request_validation(
        self,
        original_code: str,
        fixed_code: str,
        problem_description: str
    ) -> Dict[str, Any]:
        """
        Запрос на валидацию исправления от Copilot
        
        Args:
            original_code: Исходный код
            fixed_code: Исправленный код
            problem_description: Описание проблемы
        
        Returns:
            Запрос для Copilot
        """
        request_file = self.copilot_dir / "validation_request.json"
        
        request = {
            "type": "validation_request",
            "problem": problem_description,
            "original": original_code,
            "fixed": fixed_code,
            "questions": [
                "Is the fix correct?",
                "Are there any issues with the fixed code?",
                "Can this be improved further?"
            ]
        }
        
        request_file.write_text(json.dumps(request, indent=2), encoding='utf-8')
        
        print(f"💬 Copilot validation request saved: {request_file}")
        print("   Please review in VS Code and provide feedback.")
        
        return request
    
    async def request_refactoring_ideas(
        self,
        code: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Запрос идей по рефакторингу от Copilot
        
        Args:
            code: Код для рефакторинга
            context: Контекст (что улучшить)
        
        Returns:
            Запрос для Copilot
        """
        request_file = self.copilot_dir / "refactoring_request.json"
        
        request = {
            "type": "refactoring_request",
            "code": code,
            "context": context,
            "questions": [
                "How can this code be improved?",
                "What refactoring patterns apply here?",
                "Are there any performance improvements?"
            ]
        }
        
        request_file.write_text(json.dumps(request, indent=2), encoding='utf-8')
        
        print(f"💬 Copilot refactoring request saved: {request_file}")
        
        return request


class AICollaborationOrchestrator:
    """
    Orchestrator для совместной работы AI систем
    
    Workflow:
    1. DeepSeek: Глубокий анализ кода, генерация исправлений
    2. Perplexity: Исследование best practices, поиск решений
    3. Copilot: Валидация исправлений, дополнительные улучшения
    
    Результат: консенсус от всех систем
    """
    
    def __init__(self, project_root: Path):
        self.deepseek = DeepSeekClient()
        self.perplexity = PerplexityClient()
        self.copilot = CopilotIntegration(project_root)
    
    async def collaborative_analysis(
        self,
        code: str,
        problem: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Совместный анализ проблемы всеми AI
        
        Args:
            code: Код для анализа
            problem: Описание проблемы
            context: Дополнительный контекст
        
        Returns:
            Консолидированный результат
        """
        print("\n🤝 Collaborative AI Analysis")
        print("=" * 80)
        
        results = {}
        
        # 1. DeepSeek: Анализ и генерация fix
        print("\n1️⃣ DeepSeek: Analyzing code...")
        deepseek_result = await self.deepseek.analyze_code(
            code=code,
            instruction=f"Analyze and fix: {problem}",
            context=context
        )
        results["deepseek"] = {
            "success": deepseek_result.success,
            "content": deepseek_result.content[:200] + "..." if len(deepseek_result.content) > 200 else deepseek_result.content
        }
        print(f"   {'✅ Success' if deepseek_result.success else '❌ Failed'}")
        
        # 2. Perplexity: Исследование best practices
        print("\n2️⃣ Perplexity: Researching best practices...")
        perplexity_result = await self.perplexity.find_solution(problem, context)
        results["perplexity"] = {
            "success": perplexity_result.success,
            "content": perplexity_result.content[:200] + "..." if len(perplexity_result.content) > 200 else perplexity_result.content
        }
        print(f"   {'✅ Success' if perplexity_result.success else '❌ Failed'}")
        
        # 3. Copilot: Запрос на валидацию
        print("\n3️⃣ Copilot: Validation request created")
        copilot_request = await self.copilot.request_validation(
            original_code=code,
            fixed_code=deepseek_result.content if deepseek_result.success else code,
            problem_description=problem
        )
        results["copilot"] = {
            "request_file": str(copilot_request)
        }
        print("   ✅ Request saved for manual review")
        
        print("\n" + "=" * 80)
        
        return {
            "collaborative_result": results,
            "deepseek_fix": deepseek_result.content if deepseek_result.success else None,
            "perplexity_insights": perplexity_result.content if perplexity_result.success else None,
            "copilot_validation_pending": True
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example_usage():
    """Пример использования AI интеграций"""
    
    # 1. DeepSeek: Analyze code
    print("=" * 80)
    print("Example 1: DeepSeek Code Analysis")
    print("=" * 80)
    
    deepseek = DeepSeekClient()
    
    buggy_code = """
def divide(a, b):
    return a / b
"""
    
    result = await deepseek.generate_fix(
        problem_description="ZeroDivisionError when b=0",
        original_code=buggy_code
    )
    
    print(f"\nDeepSeek fix:\n{result.content}")
    
    # 2. Perplexity: Research
    print("\n" + "=" * 80)
    print("Example 2: Perplexity Research")
    print("=" * 80)
    
    perplexity = PerplexityClient()
    
    research = await perplexity.research_best_practices(
        topic="async Python testing",
        language="python"
    )
    
    print(f"\nBest practices:\n{research.content[:500]}...")
    
    # 3. Collaborative analysis
    print("\n" + "=" * 80)
    print("Example 3: Collaborative Analysis")
    print("=" * 80)
    
    orchestrator = AICollaborationOrchestrator(Path.cwd())
    
    collab_result = await orchestrator.collaborative_analysis(
        code=buggy_code,
        problem="Handle division by zero safely",
        context="Python 3.13, production code"
    )
    
    print(f"\nCollaborative result:")
    print(json.dumps(collab_result, indent=2))


if __name__ == "__main__":
    asyncio.run(example_usage())
