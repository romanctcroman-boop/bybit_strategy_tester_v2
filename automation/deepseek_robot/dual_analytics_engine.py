"""
🤝 DeepSeek ↔ Perplexity Dual Analytics Engine

Двойная аналитика где:
- DeepSeek: Глубокий анализ кода, генерация fixes, технические решения
- Perplexity: Real-time research, best practices, актуальные решения из интернета
- Cross-validation: Взаимная проверка и дополнение результатов

Workflow:
1. DeepSeek находит проблемы
2. Perplexity исследует best practices
3. DeepSeek генерирует fix на основе research
4. Perplexity валидирует решение
5. Применяем fix с двойной проверкой
"""

import asyncio
import json
import re
from pathlib import Path
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel
from automation.deepseek_robot.api_clients import PerplexityClient, DeepSeekClient

# ML imports for semantic similarity
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("⚠️ sklearn not available, using fallback similarity")


class DualAnalyticsEngine:
    """
    Движок двойной аналитики DeepSeek + Perplexity
    """
    
    def __init__(self, deepseek_keys: List[str], perplexity_key: str):
        self.deepseek_clients = [DeepSeekClient(key) for key in deepseek_keys]
        self.perplexity_client = PerplexityClient(perplexity_key)
        self.current_deepseek_idx = 0
        
        # Statistics
        self.deepseek_analyses = 0
        self.perplexity_researches = 0
        self.cross_validations = 0
        self.agreements = 0  # Когда оба согласны
        self.disagreements = 0  # Когда мнения расходятся
        
    def _get_next_deepseek(self) -> DeepSeekClient:
        """Round-robin DeepSeek clients"""
        client = self.deepseek_clients[self.current_deepseek_idx]
        self.current_deepseek_idx = (self.current_deepseek_idx + 1) % len(self.deepseek_clients)
        return client
    
    async def deepseek_analyze(self, code: str, filename: str) -> Dict[str, Any]:
        """
        DeepSeek анализ кода
        
        Сильные стороны:
        - Глубокое понимание кода
        - Syntax и logic анализ
        - Генерация корректных fixes
        """
        self.deepseek_analyses += 1
        
        client = self._get_next_deepseek()
        
        result = await client.chat_completion(
            messages=[{
                "role": "user",
                "content": f"""Deep code analysis of {filename}:

{code[:2000]}

Analyze for:
1. Syntax errors
2. Type errors
3. Logic issues
4. Performance bottlenecks
5. Security vulnerabilities

Return JSON:
{{
    "severity": "critical/high/medium/low",
    "issues": [{{"type": "...", "line": 0, "description": "...", "impact": "..."}}],
    "overall_quality": 0-100,
    "recommendation": "..."
}}
"""
            }],
            model="deepseek-coder",
            temperature=0.1,
            max_tokens=1500
        )
        
        if result.get("success"):
            return {
                "source": "deepseek",
                "success": True,
                "analysis": result.get("response"),
                "tokens": result.get("usage", {}).get("total_tokens", 0)
            }
        else:
            return {
                "source": "deepseek",
                "success": False,
                "error": result.get("error")
            }
    
    async def perplexity_research(self, problem_description: str, context: str = "") -> Dict[str, Any]:
        """
        Perplexity research best practices
        
        Сильные стороны:
        - Real-time web search
        - Актуальные best practices
        - Новые решения и подходы
        - Ссылки на документацию
        """
        self.perplexity_researches += 1
        
        query = f"""Research best practices for this coding problem:

Problem: {problem_description}
Context: {context}

Find:
1. Current best practices (2024-2025)
2. Common solutions
3. Potential pitfalls
4. Recommended approaches
5. Security considerations

Provide concrete examples and links to documentation.
"""
        
        result = await self.perplexity_client.search(query, model="sonar-pro")
        
        if result.get("success"):
            return {
                "source": "perplexity",
                "success": True,
                "research": result.get("response"),
                "sources": result.get("sources", []),
                "model": result.get("model")
            }
        else:
            return {
                "source": "perplexity",
                "success": False,
                "error": result.get("error")
            }
    
    async def dual_analyze(
        self,
        code: str,
        filename: str,
        problem_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Двойной анализ: DeepSeek + Perplexity параллельно
        
        Returns:
            {
                "deepseek_result": {...},
                "perplexity_result": {...},
                "combined_insights": {...},
                "agreement_score": 0-100
            }
        """
        print(f"   🔬 Dual Analysis: {filename}")
        
        # Параллельный запуск
        start = time.time()
        
        deepseek_task = self.deepseek_analyze(code, filename)
        
        # Если есть hint, используем для research
        if problem_hint:
            perplexity_task = self.perplexity_research(problem_hint, f"Python file: {filename}")
        else:
            perplexity_task = self.perplexity_research(
                f"Python code quality analysis for {filename}",
                "General code review"
            )
        
        # Ждём оба результата
        deepseek_result, perplexity_result = await asyncio.gather(
            deepseek_task,
            perplexity_task,
            return_exceptions=True
        )
        
        duration = time.time() - start
        
        # Handle exceptions
        if isinstance(deepseek_result, Exception):
            deepseek_result = {"source": "deepseek", "success": False, "error": str(deepseek_result)}
        if isinstance(perplexity_result, Exception):
            perplexity_result = {"source": "perplexity", "success": False, "error": str(perplexity_result)}
        
        # Combine insights
        combined = self._combine_insights(deepseek_result, perplexity_result)
        
        print(f"      ✅ Completed in {duration:.2f}s")
        print(f"      • DeepSeek: {'✅' if deepseek_result.get('success') else '❌'}")
        print(f"      • Perplexity: {'✅' if perplexity_result.get('success') else '❌'}")
        print(f"      • Agreement: {combined['agreement_score']:.0f}%")
        
        return {
            "deepseek_result": deepseek_result,
            "perplexity_result": perplexity_result,
            "combined_insights": combined,
            "duration": duration
        }
    
    def _combine_insights(
        self,
        deepseek_result: Dict,
        perplexity_result: Dict
    ) -> Dict[str, Any]:
        """
        Объединение и cross-validation результатов
        
        ОПТИМИЗАЦИЯ: TF-IDF semantic similarity вместо keyword overlap
        """
        self.cross_validations += 1
        
        combined = {
            "issues": [],
            "recommendations": [],
            "agreement_score": 0,
            "confidence": "unknown"
        }
        
        # Если оба успешны - ищем согласия и расхождения
        if deepseek_result.get("success") and perplexity_result.get("success"):
            deepseek_analysis = deepseek_result.get("analysis", "")
            perplexity_research = perplexity_result.get("research", "")
            
            # НОВАЯ ЛОГИКА: TF-IDF semantic similarity
            deepseek_text = self._extract_text_from_response(deepseek_analysis)
            perplexity_text = self._extract_text_from_response(perplexity_research)
            
            # Calculate semantic similarity
            agreement = self._calculate_semantic_similarity(deepseek_text, perplexity_text)
            combined["agreement_score"] = agreement * 100
            
            # Thresholds остаются те же
            if agreement > 0.7:
                self.agreements += 1
                combined["confidence"] = "high"
            elif agreement > 0.4:
                combined["confidence"] = "medium"
            else:
                self.disagreements += 1
                combined["confidence"] = "low"
            
            # Комбинированные рекомендации
            combined["recommendations"].append({
                "source": "deepseek",
                "text": deepseek_analysis[:200] + "..."
            })
            
            combined["recommendations"].append({
                "source": "perplexity",
                "text": perplexity_research[:200] + "...",
                "sources": perplexity_result.get("sources", [])
            })
            
        elif deepseek_result.get("success"):
            # Только DeepSeek
            combined["confidence"] = "medium"
            combined["agreement_score"] = 50
            combined["recommendations"].append({
                "source": "deepseek",
                "text": deepseek_result.get("analysis", "")[:200] + "..."
            })
            
        elif perplexity_result.get("success"):
            # Только Perplexity
            combined["confidence"] = "medium"
            combined["agreement_score"] = 50
            combined["recommendations"].append({
                "source": "perplexity",
                "text": perplexity_result.get("research", "")[:200] + "..."
            })
        
        return combined
    
    def _extract_text_from_response(self, response: str) -> str:
        """
        Extract meaningful text from response (JSON or plain text)
        
        Args:
            response: DeepSeek/Perplexity response
            
        Returns:
            Clean text for similarity analysis
        """
        try:
            # Try parse as JSON
            data = json.loads(response)
            # Extract all text fields recursively
            texts = self._extract_json_text(data)
            return " ".join(texts)
        except (json.JSONDecodeError, TypeError):
            # Return as plain text, clean up
            # Remove code blocks, special chars
            clean = re.sub(r'```.*?```', '', response, flags=re.DOTALL)
            clean = re.sub(r'[{}\[\]":,]', ' ', clean)
            return clean
    
    def _extract_json_text(self, obj: Any) -> List[str]:
        """Recursively extract text from JSON object"""
        texts = []
        
        if isinstance(obj, dict):
            for value in obj.values():
                texts.extend(self._extract_json_text(value))
        elif isinstance(obj, list):
            for item in obj:
                texts.extend(self._extract_json_text(item))
        elif isinstance(obj, str):
            texts.append(obj)
        
        return texts
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity using TF-IDF + cosine similarity
        
        Args:
            text1: First text (DeepSeek)
            text2: Second text (Perplexity)
            
        Returns:
            Similarity score 0-1
        """
        if not ML_AVAILABLE:
            # Fallback: simple word overlap
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            overlap = len(words1 & words2)
            total = len(words1 | words2)
            return overlap / total if total > 0 else 0.0
        
        try:
            # TF-IDF vectorization
            vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=100,
                ngram_range=(1, 2)  # Unigrams + bigrams
            )
            
            # Fit and transform
            vectors = vectorizer.fit_transform([text1, text2])
            
            # Cosine similarity
            similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            
            return float(similarity)
            
        except Exception as e:
            print(f"⚠️ Semantic similarity calculation failed: {e}")
            # Fallback to simple overlap
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            overlap = len(words1 & words2)
            total = len(words1 | words2)
            return overlap / total if total > 0 else 0.0
    
    async def dual_analyze_fast(
        self,
        code: str,
        filename: str,
        timeout: float = 15.0,
        problem_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        🚀 FAST MODE: Возвращает результат первого завершившегося AI
        
        Оптимизация для скорости: используем первый полученный результат,
        не ждём оба AI. Speedup: 2x (22.5s → 12-15s)
        
        Args:
            code: Source code
            filename: Filename
            timeout: Max wait time (default 15s)
            problem_hint: Optional problem hint for Perplexity
            
        Returns:
            Result from fastest AI
        """
        print(f"   ⚡ Fast Dual Analysis: {filename}")
        
        start = time.time()
        
        # Create tasks
        deepseek_task = asyncio.create_task(self.deepseek_analyze(code, filename))
        
        if problem_hint:
            perplexity_task = asyncio.create_task(
                self.perplexity_research(problem_hint, f"Python file: {filename}")
            )
        else:
            perplexity_task = asyncio.create_task(
                self.perplexity_research(
                    f"Python code quality analysis for {filename}",
                    "General code review"
                )
            )
        
        # Wait for FIRST completion
        done, pending = await asyncio.wait(
            [deepseek_task, perplexity_task],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        duration = time.time() - start
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
        
        # Get first result with quality check
        if done:
            result = next(iter(done)).result()
            
            # 🚀 QUICK WIN 2: Quality filtering - minimum response length
            MIN_RESPONSE_LENGTH = 50  # Минимум 50 символов для quality
            
            response_text = ""
            if result.get("source") == "deepseek":
                response_text = result.get("analysis", "")
            else:
                response_text = result.get("research", "")
            
            # Check if response is too short (low quality)
            if len(response_text) < MIN_RESPONSE_LENGTH:
                print(f"      ⚠️ First response too short ({len(response_text)} chars), waiting for second...")
                
                # Wait for second AI if first was too short
                if pending:
                    try:
                        second_done, _ = await asyncio.wait(
                            pending,
                            timeout=timeout - duration  # Remaining time
                        )
                        if second_done:
                            result = next(iter(second_done)).result()
                            if result.get("source") == "deepseek":
                                response_text = result.get("analysis", "")
                            else:
                                response_text = result.get("research", "")
                    except:
                        pass  # Use first result even if short
            
            # Determine which AI finished first
            if result.get("source") == "deepseek":
                fastest = "DeepSeek"
            else:
                fastest = "Perplexity"
            
            print(f"      ⚡ Completed in {duration:.2f}s (fastest: {fastest})")
            print(f"      ✅ Response length: {len(response_text)} chars")
            
            return {
                "fastest_result": result,
                "fastest_ai": fastest,
                "duration": duration,
                "mode": "fast",
                "response_length": len(response_text),
                "quality_check_passed": len(response_text) >= MIN_RESPONSE_LENGTH
            }
        else:
            # Timeout
            print(f"      ⏱️ Timeout after {timeout}s")
            return {
                "fastest_result": None,
                "fastest_ai": None,
                "duration": duration,
                "mode": "fast",
                "timeout": True
            }
    
    async def generate_fix_with_research(
        self,
        problem: Dict[str, Any],
        code: str
    ) -> Dict[str, Any]:
        """
        Генерация fix с использованием обоих источников:
        1. Perplexity исследует best practices
        2. DeepSeek генерирует fix на основе research
        """
        print(f"\n   🔧 Generating fix with dual research...")
        
        # Step 1: Perplexity research
        print(f"      1️⃣ Perplexity: Researching best practices...")
        research = await self.perplexity_research(
            problem.get("description", ""),
            f"Python code fix for: {problem.get('file', 'unknown')}"
        )
        
        # Step 2: DeepSeek генерирует fix с учётом research
        print(f"      2️⃣ DeepSeek: Generating fix based on research...")
        
        research_summary = ""
        if research.get("success"):
            research_summary = f"\nBest practices from research:\n{research.get('research', '')[:500]}"
        
        client = self._get_next_deepseek()
        
        fix_result = await client.chat_completion(
            messages=[{
                "role": "user",
                "content": f"""Generate fix for this issue:

File: {problem.get('file', 'unknown')}
Problem: {problem.get('description', '')}
Severity: {problem.get('severity', 'medium')}

Current code:
{code[:1500]}

{research_summary}

Generate EXACT fix with:
1. old_code (exact code to replace)
2. new_code (fixed version)
3. explanation
4. risk_level (low/medium/high)

Return JSON format.
"""
            }],
            model="deepseek-coder",
            temperature=0.1,
            max_tokens=2000
        )
        
        if fix_result.get("success"):
            print(f"      ✅ Fix generated successfully")
            
            return {
                "success": True,
                "fix": fix_result.get("response"),
                "research": research.get("research", "") if research.get("success") else None,
                "sources": research.get("sources", []) if research.get("success") else [],
                "confidence": "high" if research.get("success") else "medium"
            }
        else:
            return {
                "success": False,
                "error": fix_result.get("error")
            }
    
    async def validate_fix_dual(
        self,
        original_code: str,
        fixed_code: str,
        fix_description: str
    ) -> Dict[str, Any]:
        """
        Двойная валидация fix через оба AI:
        1. DeepSeek проверяет корректность кода
        2. Perplexity проверяет соответствие best practices
        """
        self.cross_validations += 1
        
        print(f"   ✔️  Dual validation of fix...")
        
        # Параллельная валидация
        deepseek_task = asyncio.create_task(
            self._get_next_deepseek().chat_completion(
                messages=[{
                    "role": "user",
                    "content": f"""Validate this code fix:

Original:
{original_code[:800]}

Fixed:
{fixed_code[:800]}

Fix description: {fix_description}

Check:
1. Syntax correctness
2. Logic correctness
3. No breaking changes
4. Performance impact

Return JSON: {{"valid": true/false, "issues": [...], "score": 0-100}}
"""
                }],
                model="deepseek-coder",
                temperature=0.1,
                max_tokens=800
            )
        )
        
        perplexity_task = asyncio.create_task(
            self.perplexity_client.search(
                f"""Validate if this code change follows best practices:

Change: {fix_description}

Check against:
1. Current Python best practices
2. Security guidelines
3. Performance standards
4. Industry recommendations
""",
                model="sonar-pro"
            )
        )
        
        deepseek_validation, perplexity_validation = await asyncio.gather(
            deepseek_task,
            perplexity_task,
            return_exceptions=True
        )
        
        # Process results
        deepseek_valid = False
        perplexity_valid = False
        
        if isinstance(deepseek_validation, dict) and deepseek_validation.get("success"):
            response = deepseek_validation.get("response", "")
            deepseek_valid = "valid" in response.lower() and "true" in response.lower()
            print(f"      • DeepSeek: {'✅ Valid' if deepseek_valid else '❌ Invalid'}")
        
        if isinstance(perplexity_validation, dict) and perplexity_validation.get("success"):
            response = perplexity_validation.get("response", "")
            # Perplexity обычно описательный, проверяем на негативные слова
            negative_words = ["avoid", "don't", "incorrect", "wrong", "bad practice"]
            perplexity_valid = not any(word in response.lower() for word in negative_words)
            print(f"      • Perplexity: {'✅ Follows best practices' if perplexity_valid else '⚠️  Has concerns'}")
        
        # Итоговое решение
        both_agree = deepseek_valid and perplexity_valid
        
        if both_agree:
            self.agreements += 1
            confidence = "high"
        elif deepseek_valid or perplexity_valid:
            confidence = "medium"
        else:
            self.disagreements += 1
            confidence = "low"
        
        return {
            "valid": both_agree,
            "deepseek_valid": deepseek_valid,
            "perplexity_valid": perplexity_valid,
            "confidence": confidence,
            "recommendation": "apply" if both_agree else ("review" if confidence == "medium" else "reject")
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика работы двойной аналитики"""
        total = self.agreements + self.disagreements
        agreement_rate = self.agreements / total if total > 0 else 0
        
        return {
            "deepseek_analyses": self.deepseek_analyses,
            "perplexity_researches": self.perplexity_researches,
            "cross_validations": self.cross_validations,
            "agreements": self.agreements,
            "disagreements": self.disagreements,
            "agreement_rate": f"{agreement_rate*100:.1f}%",
            "total_dual_operations": total
        }


class DualAnalyticsAgent:
    """
    Автономный агент с двойной аналитикой
    """
    
    def __init__(self, project_root: Path, deepseek_keys: List[str], perplexity_key: str):
        self.robot = DeepSeekRobot(
            project_root=project_root,
            autonomy_level=AutonomyLevel.FULL_AUTO
        )
        self.dual_engine = DualAnalyticsEngine(deepseek_keys, perplexity_key)
        self.project_root = project_root
        
    async def analyze_project_dual(self, max_files: int = 10) -> Dict[str, Any]:
        """
        Анализ проекта с двойной аналитикой
        """
        print("\n" + "=" * 80)
        print("🤝 DUAL ANALYTICS: DeepSeek ↔ Perplexity")
        print("=" * 80)
        
        # Get files
        python_files = list(self.project_root.glob("**/*.py"))
        python_files = [
            f for f in python_files
            if "__pycache__" not in str(f) and ".venv" not in str(f)
        ][:max_files]
        
        print(f"\n📁 Analyzing {len(python_files)} files with dual AI...")
        
        results = []
        
        for i, file in enumerate(python_files, 1):
            print(f"\n{'='*80}")
            print(f"File {i}/{len(python_files)}: {file.name}")
            print(f"{'='*80}")
            
            try:
                code = file.read_text(encoding="utf-8")
                
                # Dual analysis
                result = await self.dual_engine.dual_analyze(
                    code=code,
                    filename=file.name
                )
                
                result["file"] = str(file)
                results.append(result)
                
                # Display combined insights
                combined = result["combined_insights"]
                
                print(f"\n   📊 Combined Insights:")
                print(f"      • Confidence: {combined['confidence']}")
                print(f"      • Agreement: {combined['agreement_score']:.0f}%")
                
                if combined["recommendations"]:
                    print(f"\n   💡 Recommendations:")
                    for rec in combined["recommendations"]:
                        print(f"      [{rec['source'].upper()}] {rec['text'][:100]}...")
                        if rec.get("sources"):
                            print(f"         Sources: {len(rec['sources'])} references")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Final statistics
        print(f"\n" + "=" * 80)
        print("📊 DUAL ANALYTICS STATISTICS")
        print("=" * 80)
        
        stats = self.dual_engine.get_statistics()
        
        print(f"\n🔬 Analysis Operations:")
        print(f"   • DeepSeek analyses: {stats['deepseek_analyses']}")
        print(f"   • Perplexity researches: {stats['perplexity_researches']}")
        print(f"   • Cross-validations: {stats['cross_validations']}")
        
        print(f"\n🤝 Agreement Metrics:")
        print(f"   • Agreements: {stats['agreements']}")
        print(f"   • Disagreements: {stats['disagreements']}")
        print(f"   • Agreement rate: {stats['agreement_rate']}")
        
        print("=" * 80)
        
        return {
            "results": results,
            "statistics": stats
        }


async def demo_dual_analytics():
    """
    Демонстрация двойной аналитики
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Load API keys
    deepseek_keys = []
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            deepseek_keys.append(key)
    
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    
    if not deepseek_keys or not perplexity_key:
        print("❌ API keys not found in .env")
        return
    
    print(f"✅ Loaded {len(deepseek_keys)} DeepSeek keys")
    print(f"✅ Loaded Perplexity key")
    
    # Create agent
    project_root = Path("d:/bybit_strategy_tester_v2")
    agent = DualAnalyticsAgent(project_root, deepseek_keys, perplexity_key)
    
    # Run dual analysis
    report = await agent.analyze_project_dual(max_files=5)  # Start with 5 files
    
    # Save report
    report_path = project_root / "dual_analytics_report.json"
    with open(report_path, "w") as f:
        # Convert results to serializable format
        serializable_report = {
            "statistics": report["statistics"],
            "file_count": len(report["results"]),
            "timestamp": datetime.now().isoformat()
        }
        json.dump(serializable_report, f, indent=2)
    
    print(f"\n📄 Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(demo_dual_analytics())
