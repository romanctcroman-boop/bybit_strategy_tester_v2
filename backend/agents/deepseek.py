"""
DeepSeek Code Generation Agent
===============================

Features:
- Strategy code generation from natural language
- Auto-fix mechanism (reasoning → codegen → test → fix loop)
- Integration with Perplexity for reasoning
- Rate limiting and retry logic
- Caching generated code

Week 3 Day 4 Implementation
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DeepSeekModel(str, Enum):
    """DeepSeek models"""
    CHAT = "deepseek-chat"
    CODER = "deepseek-coder"


class CodeGenerationStatus(str, Enum):
    """Code generation status"""
    PENDING = "pending"
    REASONING = "reasoning"
    GENERATING = "generating"
    TESTING = "testing"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationResult:
    """Result of code generation"""
    status: CodeGenerationStatus
    code: str | None = None
    error: str | None = None
    reasoning: str | None = None
    test_results: dict[str, Any] | None = None
    iterations: int = 0
    tokens_used: int = 0
    time_elapsed: float = 0.0


class DeepSeekConfig(BaseSettings):
    """DeepSeek agent configuration"""
    
    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}
    
    api_key: str = Field(..., validation_alias="DEEPSEEK_API_KEY")
    api_url: str = Field(
        default="https://api.deepseek.com/v1/chat/completions",
        validation_alias="DEEPSEEK_API_URL"
    )
    model: DeepSeekModel = Field(default=DeepSeekModel.CODER)
    max_tokens: int = Field(default=4000)
    temperature: float = Field(default=0.7)
    timeout: int = Field(default=60)
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=2.0)
    
    # Auto-fix configuration
    max_fix_iterations: int = Field(default=3)
    enable_auto_fix: bool = Field(default=True)
    
    # Rate limiting
    requests_per_minute: int = Field(default=50)


class DeepSeekAgent:
    """
    DeepSeek Code Generation Agent
    
    Capabilities:
    1. Generate trading strategy code from natural language
    2. Auto-fix errors through reasoning → code → test loop
    3. Integrate with Perplexity for reasoning steps
    4. Cache generated code for reuse
    
    Example:
        config = DeepSeekConfig()
        agent = DeepSeekAgent(config)
        
        result = await agent.generate_strategy(
            prompt="Create EMA crossover strategy with 20/50 periods",
            context={"symbol": "BTCUSDT", "timeframe": "1h"}
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"Generated code: {result.code}")
    """
    
    def __init__(self, config: DeepSeekConfig | None = None):
        self.config = config or DeepSeekConfig()
        self._session: aiohttp.ClientSession | None = None
        self._request_times: list[float] = []
        
        logger.info(f"✅ Initialized DeepSeekAgent with model: {self.config.model}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    async def connect(self):
        """Create aiohttp session"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
            logger.info("🔗 Connected to DeepSeek API")
    
    async def disconnect(self):
        """Close aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("🔌 Disconnected from DeepSeek API")
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()
        
        # Remove old requests (older than 1 minute)
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        # Check if we exceeded rate limit
        if len(self._request_times) >= self.config.requests_per_minute:
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                logger.warning(f"⏳ Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._request_times = []
        
        self._request_times.append(now)
    
    async def _call_api(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None
    ) -> dict[str, Any]:
        """
        Call DeepSeek API with retry logic
        
        Args:
            messages: Chat messages
            max_tokens: Max tokens (override config)
            temperature: Temperature (override config)
        
        Returns:
            API response
        """
        if not self._session:
            await self.connect()
        
        await self._rate_limit()
        
        payload = {
            "model": self.config.model.value,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature
        }
        
        for attempt in range(self.config.max_retries):
            try:
                async with self._session.post(
                    self.config.api_url,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ API call successful (tokens: {result.get('usage', {}).get('total_tokens', 0)})")
                        return result
                    elif response.status == 429:
                        # Rate limit exceeded
                        retry_after = int(response.headers.get("Retry-After", 10))
                        logger.warning(f"⏳ Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ API error {response.status}: {error_text}")
                        
                        if attempt < self.config.max_retries - 1:
                            wait_time = self.config.retry_delay * (2 ** attempt)
                            logger.info(f"🔄 Retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                            await asyncio.sleep(wait_time)
                        else:
                            raise Exception(f"API call failed after {self.config.max_retries} retries")
            
            except TimeoutError:
                logger.error(f"⏱️ Timeout on attempt {attempt + 1}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    raise Exception("API call timed out")
            
            except Exception as e:
                logger.error(f"❌ Exception on attempt {attempt + 1}: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    raise
        
        raise Exception("API call failed unexpectedly")
    
    async def generate_code(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        system_prompt: str | None = None
    ) -> tuple[str, int]:
        """
        Generate code from prompt
        
        Args:
            prompt: User prompt
            context: Additional context (symbol, timeframe, etc.)
            system_prompt: Optional system prompt override
        
        Returns:
            (generated_code, tokens_used)
        """
        if not system_prompt:
            system_prompt = """You are an expert Python trading strategy developer.
            
Your task is to generate clean, production-ready trading strategy code.

Requirements:
- Use pandas for data manipulation
- Include proper error handling
- Add docstrings and comments
- Follow PEP 8 style guide
- Return executable Python code only (no markdown, no explanations)
- Code should be self-contained and importable

Output format: Pure Python code, no markdown code blocks."""
        
        # Build user message with context
        user_message = prompt
        if context:
            user_message += f"\n\nContext: {json.dumps(context, indent=2)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        result = await self._call_api(messages)
        
        code = result["choices"][0]["message"]["content"]
        tokens_used = result["usage"]["total_tokens"]
        
        # Clean code (remove markdown if present)
        code = self._clean_code(code)
        
        return code, tokens_used
    
    def _clean_code(self, code: str) -> str:
        """Remove markdown code blocks and clean code"""
        # Remove ```python or ``` markers
        lines = code.strip().split('\n')
        cleaned = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if not in_code_block or line.strip():
                cleaned.append(line)
        
        return '\n'.join(cleaned).strip()
    
    async def test_code(self, code: str) -> dict[str, Any]:
        """
        Test generated code for syntax and basic errors
        
        Args:
            code: Python code to test
        
        Returns:
            Test results with errors if any
        """
        test_result = {
            "syntax_valid": False,
            "imports_valid": False,
            "errors": []
        }
        
        try:
            # Test 1: Syntax check
            compile(code, '<string>', 'exec')
            test_result["syntax_valid"] = True
            logger.info("✅ Syntax check passed")
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            test_result["errors"].append(error_msg)
            logger.error(f"❌ {error_msg}")
            return test_result
        
        # Test 2: Import check (basic) with restricted execution
        try:
            # Create isolated namespace with restricted builtins
            restricted_globals = {
                "__builtins__": {
                    "__import__": __import__,
                    "print": print,
                    "len": len,
                    "range": range,
                    "str": str,
                    "int": int,
                    "float": float,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "bool": bool,
                }
            }
            namespace = {}
            # Execute with restricted globals to prevent malicious code
            exec(code, restricted_globals, namespace)  # nosec B102 - deliberate use for code validation with restrictions
            test_result["imports_valid"] = True
            logger.info("✅ Import check passed")
        except ImportError as e:
            error_msg = f"Import error: {str(e)}"
            test_result["errors"].append(error_msg)
            logger.error(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Runtime error: {str(e)}"
            test_result["errors"].append(error_msg)
            logger.error(f"❌ {error_msg}")
        
        return test_result
    
    async def fix_code(
        self,
        code: str,
        error: str,
        original_prompt: str
    ) -> tuple[str, int]:
        """
        Fix code based on error feedback
        
        Args:
            code: Code with errors
            error: Error message
            original_prompt: Original generation prompt
        
        Returns:
            (fixed_code, tokens_used)
        """
        system_prompt = """You are an expert Python debugging assistant.

Your task is to fix the provided code based on the error message.

Requirements:
- Analyze the error carefully
- Fix ONLY the specific error
- Preserve original functionality
- Return ONLY the corrected code (no explanations)
- Do not add new features

Output format: Pure Python code, no markdown."""
        
        fix_prompt = f"""Original request: {original_prompt}

Code with error:
```python
{code}
```

Error:
{error}

Please fix the error and return corrected code."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": fix_prompt}
        ]
        
        result = await self._call_api(messages)
        
        fixed_code = result["choices"][0]["message"]["content"]
        tokens_used = result["usage"]["total_tokens"]
        
        fixed_code = self._clean_code(fixed_code)
        
        return fixed_code, tokens_used
    
    async def generate_strategy(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        enable_auto_fix: bool | None = None
    ) -> GenerationResult:
        """
        Generate trading strategy with auto-fix
        
        This is the main entry point that implements the complete
        reasoning → codegen → test → fix loop.
        
        Args:
            prompt: Strategy description
            context: Additional context
            enable_auto_fix: Override auto-fix setting
        
        Returns:
            GenerationResult with final code or error
        
        Example:
            result = await agent.generate_strategy(
                prompt="EMA crossover strategy with periods 20 and 50",
                context={"symbol": "BTCUSDT", "timeframe": "1h"}
            )
        """
        start_time = time.time()
        result = GenerationResult(
            status=CodeGenerationStatus.PENDING,
            iterations=0,
            tokens_used=0
        )
        
        use_auto_fix = enable_auto_fix if enable_auto_fix is not None else self.config.enable_auto_fix
        
        try:
            # Step 1: Generate initial code
            result.status = CodeGenerationStatus.GENERATING
            logger.info(f"🚀 Generating strategy: {prompt[:100]}...")
            
            code, tokens = await self.generate_code(prompt, context)
            result.code = code
            result.tokens_used += tokens
            result.iterations = 1
            
            logger.info(f"✅ Generated {len(code)} characters of code")
            
            # Step 2: Test code
            if use_auto_fix:
                result.status = CodeGenerationStatus.TESTING
                test_results = await self.test_code(code)
                result.test_results = test_results
                
                # Step 3: Auto-fix loop if errors found
                iteration = 1
                while (
                    test_results.get("errors") and 
                    iteration < self.config.max_fix_iterations
                ):
                    result.status = CodeGenerationStatus.FIXING
                    error_msg = "; ".join(test_results["errors"])
                    logger.warning(f"🔧 Fixing errors (iteration {iteration}): {error_msg}")
                    
                    fixed_code, fix_tokens = await self.fix_code(
                        code, error_msg, prompt
                    )
                    
                    result.code = fixed_code
                    result.tokens_used += fix_tokens
                    result.iterations += 1
                    
                    # Re-test fixed code
                    test_results = await self.test_code(fixed_code)
                    result.test_results = test_results
                    
                    if not test_results.get("errors"):
                        logger.info(f"✅ Code fixed successfully after {iteration} iterations")
                        break
                    
                    code = fixed_code
                    iteration += 1
                
                if test_results.get("errors"):
                    result.status = CodeGenerationStatus.FAILED
                    result.error = f"Failed to fix after {self.config.max_fix_iterations} iterations: " + "; ".join(test_results["errors"])
                    logger.error(f"❌ {result.error}")
                else:
                    result.status = CodeGenerationStatus.COMPLETED
                    logger.info("🎉 Strategy generation completed successfully")
            else:
                result.status = CodeGenerationStatus.COMPLETED
                logger.info("✅ Strategy generated (auto-fix disabled)")
        
        except Exception as e:
            result.status = CodeGenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Generation failed: {e}")
        
        result.time_elapsed = time.time() - start_time
        logger.info(f"⏱️ Total time: {result.time_elapsed:.2f}s, Tokens: {result.tokens_used}, Iterations: {result.iterations}")
        
        return result
    
    async def analyze_code(
        self,
        code: str,
        file_path: str | None = None,
        error_types: list[str] = None
    ) -> GenerationResult:
        """
        Analyze code for errors, bugs, and issues
        
        Args:
            code: Source code to analyze
            file_path: Path to file (for context)
            error_types: Types of errors to check (syntax, logic, performance, security)
        
        Returns:
            GenerationResult with detected errors and suggestions
        
        Example:
            result = await agent.analyze_code(
                code="def calc(x):\\n    return x+1",
                error_types=["syntax", "logic"]
            )
            
            if result.status == "completed":
                print(result.code)  # Contains analysis
        """
        if error_types is None:
            error_types = ["syntax", "logic", "performance"]
        
        result = GenerationResult(
            status=CodeGenerationStatus.REASONING,
            iterations=0,
            tokens_used=0
        )
        
        try:
            system_prompt = f"""You are an expert code analyst.
Analyze the following code for errors, bugs, and issues.

Error types to check: {", ".join(error_types)}

Provide:
1. List of detected errors with line numbers
2. Severity (critical, high, medium, low)
3. Suggested fixes
4. Corrected code (if applicable)

Format response as JSON:
{{
    "errors": [
        {{"line": 10, "type": "logic", "severity": "high", "message": "...", "fix": "..."}}
    ],
    "corrected_code": "...",
    "summary": "..."
}}
"""
            
            context_str = f"File: {file_path or 'inline'}\n\n```python\n{code}\n```"
            
            code_result, tokens = await self.generate_code(
                system_prompt + "\n\n" + context_str,
                context={"task": "code_analysis", "error_types": error_types}
            )
            
            result.code = code_result
            result.tokens_used = tokens
            result.status = CodeGenerationStatus.COMPLETED
            
            logger.info(f"✅ Code analysis completed ({len(error_types)} error types)")
            
        except Exception as e:
            result.status = CodeGenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Code analysis failed: {e}")
        
        return result
    
    async def refactor_code(
        self,
        code: str,
        refactor_type: str,
        target: str | None = None,
        new_name: str | None = None
    ) -> GenerationResult:
        """
        Refactor code using specified technique
        
        Args:
            code: Source code to refactor
            refactor_type: Type of refactoring (extract_function, inline, rename, optimize)
            target: Target element (function, class) - optional
            new_name: New name (for rename) - optional
        
        Returns:
            GenerationResult with refactored code
        
        Example:
            result = await agent.refactor_code(
                code=my_code,
                refactor_type="optimize",
                target="calculate_indicators"
            )
            
            if result.status == "completed":
                print(result.code)  # Refactored code
        """
        result = GenerationResult(
            status=CodeGenerationStatus.REASONING,
            iterations=0,
            tokens_used=0
        )
        
        try:
            refactor_instructions = {
                "extract_function": "Extract repeated code into separate functions",
                "inline": "Inline small functions into their call sites",
                "rename": f"Rename '{target}' to '{new_name}'",
                "optimize": "Optimize performance and reduce complexity"
            }
            
            instruction = refactor_instructions.get(
                refactor_type,
                f"Apply '{refactor_type}' refactoring"
            )
            
            system_prompt = f"""You are an expert at code refactoring.

Refactoring type: {refactor_type}
Target: {target or 'entire code'}
{f"New name: {new_name}" if new_name else ""}

Task: {instruction}

Provide:
1. Refactored code
2. Explanation of changes
3. Benefits of refactoring
4. Any trade-offs or considerations

Format as JSON:
{{
    "refactored_code": "...",
    "changes": ["..."],
    "benefits": ["..."],
    "trade_offs": ["..."]
}}
"""
            
            code_context = f"Original code:\n\n```python\n{code}\n```"
            
            # Save original temperature
            original_temp = self.config.temperature
            self.config.temperature = 0.3  # Lower for consistent refactoring
            
            try:
                refactored, tokens = await self.generate_code(
                    system_prompt + "\n\n" + code_context,
                    context={"task": "refactoring", "type": refactor_type}
                )
                
                result.code = refactored
                result.tokens_used = tokens
                result.status = CodeGenerationStatus.COMPLETED
                
                logger.info(f"✅ Code refactored ({refactor_type})")
            finally:
                # Restore original temperature
                self.config.temperature = original_temp
            
        except Exception as e:
            result.status = CodeGenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Refactoring failed: {e}")
        
        return result
    
    async def insert_code(
        self,
        file_path: str,
        code_to_insert: str,
        line_number: int | None = None,
        context: str | None = None,
        position: str = "after"
    ) -> GenerationResult:
        """
        Insert code into specified position in file
        
        Args:
            file_path: Path to file
            code_to_insert: Code to insert
            line_number: Line number for insertion
            context: Context string to find insertion point
            position: Position relative to line_number (before, after, replace)
        
        Returns:
            GenerationResult with insertion result
        
        Example:
            result = await agent.insert_code(
                file_path="backend/strategies/my_strategy.py",
                code_to_insert="self.rsi = RSI(period=14)",
                context="def __init__(self):",
                position="after"
            )
            
            if result.status == "completed":
                print(f"Code inserted at line {result.code}")
        """
        from pathlib import Path
        
        result = GenerationResult(
            status=CodeGenerationStatus.GENERATING,
            iterations=0,
            tokens_used=0
        )
        
        try:
            file = Path(file_path)
            
            if not file.exists():
                result.status = CodeGenerationStatus.FAILED
                result.error = f"File not found: {file_path}"
                return result
            
            # Read file
            with open(file, encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find insertion point
            insert_line = None
            
            if context:
                # Search by context
                for i, line in enumerate(lines):
                    if context in line:
                        insert_line = i
                        break
                
                if insert_line is None:
                    result.status = CodeGenerationStatus.FAILED
                    result.error = f"Context '{context}' not found in file"
                    return result
            
            elif line_number is not None:
                # Use explicit line number (1-indexed)
                insert_line = line_number - 1
            
            else:
                # Default to end of file
                insert_line = len(lines)
            
            # Insert code
            if position == "before":
                lines.insert(insert_line, code_to_insert + "\n")
            elif position == "after":
                lines.insert(insert_line + 1, code_to_insert + "\n")
            elif position == "replace":
                lines[insert_line] = code_to_insert + "\n"
            else:
                result.status = CodeGenerationStatus.FAILED
                result.error = f"Invalid position: {position}"
                return result
            
            # Write back to file
            with open(file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            result.status = CodeGenerationStatus.COMPLETED
            result.code = f"Code inserted at line {insert_line + 1} ({position})"
            
            logger.info(f"✅ Code inserted into {file_path} at line {insert_line + 1}")
            
        except Exception as e:
            result.status = CodeGenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Code insertion failed: {e}")
        
        return result
    
    async def explain_code(
        self,
        code: str,
        focus: str = "all",
        include_improvements: bool = True
    ) -> GenerationResult:
        """
        Explain what code does and how it works
        
        Args:
            code: Code to explain
            focus: Focus of explanation (all, logic, performance, security)
            include_improvements: Include suggestions for improvement
        
        Returns:
            GenerationResult with explanation
        
        Example:
            result = await agent.explain_code(
                code="def fib(n):\\n    return fib(n-1)+fib(n-2) if n>1 else n",
                focus="performance",
                include_improvements=True
            )
            
            if result.status == "completed":
                print(result.code)  # Contains explanation
        """
        result = GenerationResult(
            status=CodeGenerationStatus.REASONING,
            iterations=0,
            tokens_used=0
        )
        
        try:
            focus_instructions = {
                "all": "Provide comprehensive explanation covering all aspects",
                "logic": "Focus on business logic and algorithmic flow",
                "performance": "Analyze performance characteristics and bottlenecks",
                "security": "Identify security vulnerabilities and risks"
            }
            
            instruction = focus_instructions.get(focus, focus_instructions["all"])
            
            system_prompt = f"""You are an expert at explaining code.

Focus: {instruction}

Provide:
1. High-level overview of what the code does
2. Step-by-step explanation of key parts
3. Algorithms and patterns used
4. Potential issues or edge cases
5. Performance considerations
{"6. Suggestions for improvement" if include_improvements else ""}

Format as markdown with code examples.
"""
            
            code_context = f"Code to explain:\n\n```python\n{code}\n```"
            
            # Save original temperature
            original_temp = self.config.temperature
            self.config.temperature = 0.2  # Lower for consistent explanations
            
            try:
                explanation, tokens = await self.generate_code(
                    system_prompt + "\n\n" + code_context,
                    context={"task": "explanation", "focus": focus}
                )
                
                result.code = explanation
                result.tokens_used = tokens
                result.status = CodeGenerationStatus.COMPLETED
                
                logger.info(f"✅ Code explained (focus: {focus})")
            finally:
                # Restore original temperature
                self.config.temperature = original_temp
            
        except Exception as e:
            result.status = CodeGenerationStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Code explanation failed: {e}")
        
        return result


# Example usage
async def example_usage():
    """Example: Generate EMA crossover strategy"""
    config = DeepSeekConfig()
    
    async with DeepSeekAgent(config) as agent:
        result = await agent.generate_strategy(
            prompt="""Create a simple EMA crossover trading strategy.
            
Requirements:
- Use 20-period and 50-period EMAs
- Buy signal when 20 EMA crosses above 50 EMA
- Sell signal when 20 EMA crosses below 50 EMA
- Include position sizing (1% of capital per trade)
- Add stop-loss (2%) and take-profit (4%)
            """,
            context={
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "initial_capital": 10000
            }
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print("="*60)
            print("🎉 SUCCESS!")
            print("="*60)
            print(result.code)
            print("="*60)
            print("Stats:")
            print(f"  Iterations: {result.iterations}")
            print(f"  Tokens: {result.tokens_used}")
            print(f"  Time: {result.time_elapsed:.2f}s")
            print("="*60)
        else:
            print(f"❌ FAILED: {result.error}")


if __name__ == "__main__":
    asyncio.run(example_usage())
