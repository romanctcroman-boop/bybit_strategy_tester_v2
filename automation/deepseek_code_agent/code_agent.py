"""
DeepSeek Code Agent - AI-powered code generation, refactoring, and testing

Provides Copilot-like functionality using DeepSeek API:
- Code generation from natural language
- Code refactoring and optimization
- Bug fixing with error context
- Unit test generation

Author: AI Automation System
Date: 2025-11-08
"""

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.parallel_deepseek_client_v2 import (
    ParallelDeepSeekClientV2,
    DeepSeekTask,
    TaskPriority
)
from backend.api.deepseek_pool import get_deepseek_pool
from backend.security.key_manager import get_key_manager
from loguru import logger


@dataclass
class CodeGenerationRequest:
    """Request for code generation"""
    prompt: str
    language: str = "python"
    context: Optional[str] = None  # Existing code context
    style: str = "production"  # production, quick, experimental
    max_tokens: int = 2000


@dataclass
class CodeRefactorRequest:
    """Request for code refactoring"""
    code: str
    instructions: str
    language: str = "python"
    preserve_behavior: bool = True


@dataclass
class BugFixRequest:
    """Request for bug fixing"""
    code: str
    error_message: str
    traceback: Optional[str] = None
    language: str = "python"


@dataclass
class TestGenerationRequest:
    """Request for test generation"""
    code: str
    framework: str = "pytest"  # pytest, unittest, jest
    coverage_target: str = "comprehensive"  # basic, comprehensive, edge-cases
    language: str = "python"


class DeepSeekCodeAgent:
    """
    AI-powered code agent using DeepSeek
    
    Features:
    - Code generation from natural language descriptions
    - Code refactoring with specific instructions
    - Bug fixing with error context
    - Unit test generation
    - Code review and suggestions
    
    Uses ParallelDeepSeekClientV2 for efficient API usage with:
    - Circuit breaker protection
    - Automatic key rotation
    - Rate limit handling
    - Prometheus metrics
    """
    
    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        model: str = "deepseek-coder",  # Best model for code
        max_concurrent: int = 3,  # Lower than main app (secondary priority)
        use_pool: bool = True  # NEW: Use DeepSeekClientPool by default
    ):
        """
        Initialize DeepSeek Code Agent
        
        Args:
            api_keys: List of DeepSeek API keys (or None to use pool)
            model: DeepSeek model to use (deepseek-coder recommended for code)
            max_concurrent: Max concurrent requests (ignored if use_pool=True)
            use_pool: Use DeepSeekClientPool (prevents deadlock, default=True)
        """
        self.model = model
        self.use_pool = use_pool
        
        # NEW: Use pool if enabled and no manual keys
        if use_pool and api_keys is None:
            logger.info("🎯 Using DeepSeekClientPool (deadlock prevention ACTIVE)")
            pool = get_deepseek_pool()
            self.client = pool.get_user_client()
            self._is_pool_client = True
            logger.info(f"✅ DeepSeek Code Agent with USER pool, model={model}")
            return
        
        # LEGACY: Load API keys from KeyManager if not provided
        if api_keys is None:
            key_manager = get_key_manager()
            api_keys = []
            
            # Try to load DEEPSEEK_API_KEY (base key)
            try:
                base_key = key_manager.get_decrypted_key("DEEPSEEK_API_KEY")
                api_keys.append(base_key)
            except ValueError:
                pass
            
            # Try to load numbered keys (DEEPSEEK_API_KEY_2, _3, _4, etc.)
            for i in range(2, 10):  # Support up to 10 keys
                try:
                    numbered_key = key_manager.get_decrypted_key(f"DEEPSEEK_API_KEY_{i}")
                    api_keys.append(numbered_key)
                except ValueError:
                    # Stop when we hit the first missing numbered key
                    break
            
            if not api_keys:
                logger.warning("No DEEPSEEK_API_KEY found in KeyManager!")
                logger.info("Add keys to backend/config/encrypted_secrets.json")
                
                # Try to load from environment as fallback
                import os
                env_key = os.getenv("DEEPSEEK_API_KEY")
                if env_key:
                    api_keys = [env_key]
                    logger.info("Using DEEPSEEK_API_KEY from environment variable")
                else:
                    raise ValueError(
                        "No DeepSeek API keys available! "
                        "Add keys to encrypted_secrets.json or set DEEPSEEK_API_KEY environment variable."
                    )
            else:
                logger.info(f"Loaded {len(api_keys)} DeepSeek API keys from KeyManager")
        
        self.model = model
        self.use_pool = False  # Legacy mode
        self._is_pool_client = False
        
        # Initialize DeepSeek client
        self.client = ParallelDeepSeekClientV2(
            api_keys=api_keys,
            max_concurrent=max_concurrent
        )
        
        logger.info(
            f"DeepSeekCodeAgent initialized (LEGACY mode) with model={model}, "
            f"keys={len(api_keys)}, max_concurrent={max_concurrent}"
        )
    
    async def generate_code(
        self,
        request: CodeGenerationRequest
    ) -> Dict[str, Any]:
        """
        Generate code from natural language description
        
        Args:
            request: Code generation request
            
        Returns:
            Dict with keys:
            - code: Generated code
            - explanation: Explanation of the code
            - suggestions: Additional suggestions
            - language: Programming language
        """
        logger.info(f"Generating {request.language} code: {request.prompt[:100]}...")
        
        # Build system prompt based on style
        system_prompts = {
            "production": (
                "You are an expert software engineer. Generate clean, well-documented, "
                "production-ready code following best practices. Include error handling, "
                "type hints, and comprehensive docstrings."
            ),
            "quick": (
                "You are a pragmatic developer. Generate working code quickly. "
                "Focus on functionality over perfection."
            ),
            "experimental": (
                "You are an innovative developer. Generate creative, experimental code "
                "exploring new approaches and patterns."
            )
        }
        
        system_prompt = system_prompts.get(request.style, system_prompts["production"])
        
        # Build user prompt
        user_prompt = f"""Generate {request.language} code for the following requirement:

{request.prompt}
"""
        
        if request.context:
            user_prompt += f"""

Existing code context:
```{request.language}
{request.context}
```
"""
        
        user_prompt += """

Provide:
1. Complete, working code
2. Brief explanation of the approach
3. Any important considerations or suggestions

Format your response as:
```python
# Your code here
```

Explanation: ...
Suggestions: ...
"""
        
        # Execute request (combine system + user prompts)
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        task = DeepSeekTask(
            task_id=f"generate_{hash(request.prompt) % 10000}",
            prompt=combined_prompt,
            model=self.model,
            max_tokens=request.max_tokens,
            temperature=0.2 if request.style == "production" else 0.4,
            priority=TaskPriority.MEDIUM
        )
        
        results = await self.client.process_batch([task], show_progress=False); result = results[0]
        
        if not result.success:
            logger.error(f"Code generation failed: {result.error}")
            return {
                "success": False,
                "error": result.error,
                "code": None
            }
        
        # Parse response
        response_text = result.response
        parsed = self._parse_code_response(response_text, request.language)
        
        logger.success(f"Code generated successfully ({len(parsed['code'])} chars)")
        return {
            "success": True,
            "code": parsed["code"],
            "explanation": parsed["explanation"],
            "suggestions": parsed["suggestions"],
            "language": request.language,
            "tokens_used": result.tokens_used, "processing_time": result.processing_time
        }
    
    async def refactor_code(
        self,
        request: CodeRefactorRequest
    ) -> Dict[str, Any]:
        """
        Refactor existing code with specific instructions
        
        Args:
            request: Refactoring request
            
        Returns:
            Dict with keys:
            - refactored_code: Refactored code
            - changes: List of changes made
            - explanation: Explanation of refactoring
        """
        logger.info(f"Refactoring {request.language} code: {request.instructions[:100]}...")
        
        system_prompt = (
            "You are an expert code refactoring specialist. Refactor code to improve "
            "quality, maintainability, and performance while preserving behavior."
        )
        
        if not request.preserve_behavior:
            system_prompt += " You may change behavior if it improves the design."
        
        user_prompt = f"""Refactor the following {request.language} code:

```{request.language}
{request.code}
```

Refactoring instructions: {request.instructions}

Provide:
1. Refactored code
2. List of changes made
3. Explanation of why each change improves the code

Format:
```python
# Refactored code here
```

Changes:
- Change 1: ...
- Change 2: ...

Explanation: ...
"""
        
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        task = DeepSeekTask(
            task_id=f"refactor_{hash(request.code) % 10000}",
            prompt=combined_prompt,
            model=self.model,
            max_tokens=2500,
            temperature=0.2,
            priority=TaskPriority.MEDIUM
        )
        
        results = await self.client.process_batch([task], show_progress=False); result = results[0]
        
        if not result.success:
            logger.error(f"Refactoring failed: {result.error}")
            return {
                "success": False,
                "error": result.error,
                "refactored_code": None
            }
        
        parsed = self._parse_refactor_response(result.response, request.language)
        
        logger.success("Code refactored successfully")
        return {
            "success": True,
            "refactored_code": parsed["code"],
            "changes": parsed["changes"],
            "explanation": parsed["explanation"],
            "tokens_used": result.tokens_used, "processing_time": result.processing_time
        }
    
    async def fix_errors(
        self,
        request: BugFixRequest
    ) -> Dict[str, Any]:
        """
        Fix errors in code with error context
        
        Args:
            request: Bug fix request
            
        Returns:
            Dict with keys:
            - fixed_code: Fixed code
            - root_cause: Root cause analysis
            - fix_explanation: Explanation of the fix
        """
        logger.info(f"Fixing error: {request.error_message[:100]}...")
        
        system_prompt = (
            "You are an expert debugger. Analyze errors, identify root causes, "
            "and provide correct fixes with explanations."
        )
        
        user_prompt = f"""Fix the following error in {request.language} code:

**Code:**
```{request.language}
{request.code}
```

**Error Message:**
```
{request.error_message}
```
"""
        
        if request.traceback:
            user_prompt += f"""
**Traceback:**
```
{request.traceback}
```
"""
        
        user_prompt += """

Provide:
1. Fixed code
2. Root cause analysis
3. Explanation of the fix
4. Suggestions to prevent similar errors

Format:
```python
# Fixed code here
```

Root Cause: ...
Fix Explanation: ...
Prevention: ...
"""
        
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        task = DeepSeekTask(
            task_id=f"fix_{hash(request.error_message) % 10000}",
            prompt=combined_prompt,
            model=self.model,
            max_tokens=2000,
            temperature=0.1,  # Lower temp for bug fixing
            priority=TaskPriority.HIGH  # Bug fixes are high priority
        )
        
        results = await self.client.process_batch([task], show_progress=False); result = results[0]
        
        if not result.success:
            logger.error(f"Bug fix failed: {result.error}")
            return {
                "success": False,
                "error": result.error,
                "fixed_code": None
            }
        
        parsed = self._parse_bug_fix_response(result.response, request.language)
        
        logger.success("Bug fixed successfully")
        return {
            "success": True,
            "fixed_code": parsed["code"],
            "root_cause": parsed["root_cause"],
            "fix_explanation": parsed["explanation"],
            "prevention": parsed["prevention"],
            "tokens_used": result.tokens_used, "processing_time": result.processing_time
        }
    
    async def generate_tests(
        self,
        request: TestGenerationRequest
    ) -> Dict[str, Any]:
        """
        Generate unit tests for code
        
        Args:
            request: Test generation request
            
        Returns:
            Dict with keys:
            - test_code: Generated test code
            - test_cases: List of test cases
            - coverage_notes: Notes on test coverage
        """
        logger.info(f"Generating {request.framework} tests...")
        
        system_prompt = (
            f"You are an expert in writing {request.framework} tests. Generate comprehensive, "
            "well-structured tests that cover normal cases, edge cases, and error conditions."
        )
        
        coverage_descriptions = {
            "basic": "Cover main functionality and happy paths",
            "comprehensive": "Cover normal cases, edge cases, and error conditions",
            "edge-cases": "Focus on edge cases, boundary conditions, and error handling"
        }
        
        user_prompt = f"""Generate {request.framework} tests for the following {request.language} code:

```{request.language}
{request.code}
```

Test coverage: {coverage_descriptions.get(request.coverage_target, coverage_descriptions['comprehensive'])}

Provide:
1. Complete test code with {request.framework}
2. List of test cases covered
3. Notes on test coverage and any gaps

Format:
```python
# Test code here
```

Test Cases:
- Test 1: ...
- Test 2: ...

Coverage Notes: ...
"""
        
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        task = DeepSeekTask(
            task_id=f"test_{hash(request.code) % 10000}",
            prompt=combined_prompt,
            model=self.model,
            max_tokens=2500,
            temperature=0.2,
            priority=TaskPriority.MEDIUM
        )
        
        results = await self.client.process_batch([task], show_progress=False); result = results[0]
        
        if not result.success:
            logger.error(f"Test generation failed: {result.error}")
            return {
                "success": False,
                "error": result.error,
                "test_code": None
            }
        
        parsed = self._parse_test_response(result.response, request.language)
        
        logger.success("Tests generated successfully")
        return {
            "success": True,
            "test_code": parsed["code"],
            "test_cases": parsed["test_cases"],
            "coverage_notes": parsed["coverage_notes"],
            "tokens_used": result.tokens_used, "processing_time": result.processing_time
        }
    
    # ============================================================================
    # RESPONSE PARSING HELPERS
    # ============================================================================
    
    def _parse_code_response(
        self,
        response: str,
        language: str
    ) -> Dict[str, str]:
        """Parse code generation response"""
        # Extract code block
        code_pattern = rf"```{language}\n(.*?)```"
        code_match = re.search(code_pattern, response, re.DOTALL)
        code = code_match.group(1).strip() if code_match else ""
        
        # Extract explanation
        expl_pattern = r"Explanation:\s*(.*?)(?:Suggestions:|$)"
        expl_match = re.search(expl_pattern, response, re.DOTALL | re.IGNORECASE)
        explanation = expl_match.group(1).strip() if expl_match else ""
        
        # Extract suggestions
        sugg_pattern = r"Suggestions:\s*(.*?)$"
        sugg_match = re.search(sugg_pattern, response, re.DOTALL | re.IGNORECASE)
        suggestions = sugg_match.group(1).strip() if sugg_match else ""
        
        return {
            "code": code or response,  # Fallback to full response if no code block
            "explanation": explanation,
            "suggestions": suggestions
        }
    
    def _parse_refactor_response(
        self,
        response: str,
        language: str
    ) -> Dict[str, Any]:
        """Parse refactoring response"""
        # Extract code
        code_pattern = rf"```{language}\n(.*?)```"
        code_match = re.search(code_pattern, response, re.DOTALL)
        code = code_match.group(1).strip() if code_match else ""
        
        # Extract changes (list items)
        changes_pattern = r"Changes:\s*(.*?)(?:Explanation:|$)"
        changes_match = re.search(changes_pattern, response, re.DOTALL | re.IGNORECASE)
        changes_text = changes_match.group(1).strip() if changes_match else ""
        changes = [
            line.strip("- ").strip()
            for line in changes_text.split("\n")
            if line.strip().startswith("-")
        ]
        
        # Extract explanation
        expl_pattern = r"Explanation:\s*(.*?)$"
        expl_match = re.search(expl_pattern, response, re.DOTALL | re.IGNORECASE)
        explanation = expl_match.group(1).strip() if expl_match else ""
        
        return {
            "code": code or response,
            "changes": changes,
            "explanation": explanation
        }
    
    def _parse_bug_fix_response(
        self,
        response: str,
        language: str
    ) -> Dict[str, str]:
        """Parse bug fix response"""
        # Extract code
        code_pattern = rf"```{language}\n(.*?)```"
        code_match = re.search(code_pattern, response, re.DOTALL)
        code = code_match.group(1).strip() if code_match else ""
        
        # Extract root cause
        root_pattern = r"Root Cause:\s*(.*?)(?:Fix Explanation:|$)"
        root_match = re.search(root_pattern, response, re.DOTALL | re.IGNORECASE)
        root_cause = root_match.group(1).strip() if root_match else ""
        
        # Extract explanation
        expl_pattern = r"Fix Explanation:\s*(.*?)(?:Prevention:|$)"
        expl_match = re.search(expl_pattern, response, re.DOTALL | re.IGNORECASE)
        explanation = expl_match.group(1).strip() if expl_match else ""
        
        # Extract prevention
        prev_pattern = r"Prevention:\s*(.*?)$"
        prev_match = re.search(prev_pattern, response, re.DOTALL | re.IGNORECASE)
        prevention = prev_match.group(1).strip() if prev_match else ""
        
        return {
            "code": code or response,
            "root_cause": root_cause,
            "explanation": explanation,
            "prevention": prevention
        }
    
    def _parse_test_response(
        self,
        response: str,
        language: str
    ) -> Dict[str, Any]:
        """Parse test generation response"""
        # Extract code
        code_pattern = rf"```{language}\n(.*?)```"
        code_match = re.search(code_pattern, response, re.DOTALL)
        code = code_match.group(1).strip() if code_match else ""
        
        # Extract test cases
        cases_pattern = r"Test Cases:\s*(.*?)(?:Coverage Notes:|$)"
        cases_match = re.search(cases_pattern, response, re.DOTALL | re.IGNORECASE)
        cases_text = cases_match.group(1).strip() if cases_match else ""
        test_cases = [
            line.strip("- ").strip()
            for line in cases_text.split("\n")
            if line.strip().startswith("-")
        ]
        
        # Extract coverage notes
        notes_pattern = r"Coverage Notes:\s*(.*?)$"
        notes_match = re.search(notes_pattern, response, re.DOTALL | re.IGNORECASE)
        coverage_notes = notes_match.group(1).strip() if notes_match else ""
        
        return {
            "code": code or response,
            "test_cases": test_cases,
            "coverage_notes": coverage_notes
        }
    
    async def close(self):
        """Close the agent and cleanup resources"""
        # ParallelDeepSeekClientV2 doesn't need explicit cleanup
        # but this method is here for API consistency
        logger.info("DeepSeekCodeAgent closed")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example_usage():
    """Example usage of DeepSeekCodeAgent"""
    
    # Initialize agent
    agent = DeepSeekCodeAgent()
    
    # Example 1: Generate code
    print("\n=== Example 1: Code Generation ===")
    gen_result = await agent.generate_code(
        CodeGenerationRequest(
            prompt="Create a function to calculate Fibonacci sequence using memoization",
            language="python",
            style="production"
        )
    )
    print(f"Generated code:\n{gen_result['code']}\n")
    print(f"Explanation: {gen_result['explanation']}\n")
    
    # Example 2: Refactor code
    print("\n=== Example 2: Code Refactoring ===")
    old_code = """
def calc(a, b, op):
    if op == 'add':
        return a + b
    elif op == 'sub':
        return a - b
    elif op == 'mul':
        return a * b
    elif op == 'div':
        return a / b
"""
    
    refactor_result = await agent.refactor_code(
        CodeRefactorRequest(
            code=old_code,
            instructions="Use strategy pattern and add type hints",
            language="python"
        )
    )
    print(f"Refactored code:\n{refactor_result['refactored_code']}\n")
    print(f"Changes: {refactor_result['changes']}\n")
    
    # Example 3: Fix bug
    print("\n=== Example 3: Bug Fixing ===")
    buggy_code = """
def divide_numbers(a, b):
    return a / b
"""
    
    fix_result = await agent.fix_errors(
        BugFixRequest(
            code=buggy_code,
            error_message="ZeroDivisionError: division by zero",
            language="python"
        )
    )
    print(f"Fixed code:\n{fix_result['fixed_code']}\n")
    print(f"Root cause: {fix_result['root_cause']}\n")
    
    # Example 4: Generate tests
    print("\n=== Example 4: Test Generation ===")
    test_result = await agent.generate_tests(
        TestGenerationRequest(
            code=gen_result['code'],  # Test the generated Fibonacci function
            framework="pytest",
            coverage_target="comprehensive"
        )
    )
    print(f"Test code:\n{test_result['test_code']}\n")
    print(f"Test cases: {test_result['test_cases']}\n")
    
    await agent.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
