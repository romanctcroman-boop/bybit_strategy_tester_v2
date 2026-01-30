#!/usr/bin/env python3
"""
DeepSeek MCP Server - Model Context Protocol server for DeepSeek V3 API integration.

This server exposes DeepSeek AI capabilities to Cursor IDE via MCP protocol.
Supports code generation, analysis, chat, and specialized coding tasks.

Usage:
    python deepseek_mcp_server.py

Environment Variables:
    DEEPSEEK_API_KEY: Your DeepSeek API key (required)
    DEEPSEEK_API_KEY_2: Backup API key (optional, for failover)
    DEEPSEEK_MODEL: Model to use (default: deepseek-chat)
    DEEPSEEK_TEMPERATURE: Default temperature (default: 0.7)

Protocol:
    Communicates via stdin/stdout using JSON-RPC 2.0 (synchronous for Windows compatibility)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEFAULT_TEMPERATURE = float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.7"))
REQUEST_TIMEOUT = 120  # seconds


class DeepSeekMCPServer:
    """MCP Server for DeepSeek V3 API integration (synchronous version)."""
    
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.api_key_backup = os.environ.get("DEEPSEEK_API_KEY_2")
        self.current_api_key = self.api_key
        
        self.tools = {
            "deepseek_chat": self.deepseek_chat,
            "deepseek_code": self.deepseek_code,
            "deepseek_analyze": self.deepseek_analyze,
            "deepseek_refactor": self.deepseek_refactor,
            "deepseek_explain": self.deepseek_explain,
            "deepseek_test": self.deepseek_test,
            "deepseek_debug": self.deepseek_debug,
            "deepseek_document": self.deepseek_document,
        }
    
    def _call_deepseek_api(
        self,
        messages: list,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
        use_backup: bool = False
    ) -> dict:
        """Call DeepSeek API with automatic failover (synchronous)."""
        api_key = self.api_key_backup if use_backup else self.current_api_key
        
        if not api_key:
            return {"error": "No API key available", "success": False}
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model or DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                data=data,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {
                    "success": True,
                    "content": result["choices"][0]["message"]["content"],
                    "model": result.get("model", model),
                    "usage": result.get("usage", {}),
                    "finish_reason": result["choices"][0].get("finish_reason", "stop")
                }
                
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and not use_backup and self.api_key_backup:
                # Try backup key on auth failure
                return self._call_deepseek_api(
                    messages, model, temperature, max_tokens, use_backup=True
                )
            elif e.code == 429:
                return {
                    "error": "Rate limited. Please wait and try again.",
                    "success": False,
                    "status_code": 429
                }
            else:
                return {
                    "error": f"API error: {e.code} - {e.reason}",
                    "success": False,
                    "status_code": e.code
                }
        except urllib.error.URLError as e:
            return {"error": f"Network error: {e.reason}", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def handle_request(self, request: dict) -> dict:
        """Handle incoming MCP request (synchronous)."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return self._create_response(request_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "deepseek-mcp-server",
                    "version": "1.0.0"
                }
            })
        
        elif method == "tools/list":
            return self._create_response(request_id, {
                "tools": [
                    {
                        "name": "deepseek_chat",
                        "description": "General chat/conversation with DeepSeek V3. Use for questions, brainstorming, and general assistance.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string", "description": "Your message or question"},
                                "system_prompt": {"type": "string", "description": "Optional system prompt to guide behavior"},
                                "temperature": {"type": "number", "description": "Creativity (0.0-2.0)", "default": 0.7}
                            },
                            "required": ["message"]
                        }
                    },
                    {
                        "name": "deepseek_code",
                        "description": "Generate code with DeepSeek V3. Optimized for code generation tasks.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "Description of what code to generate"},
                                "language": {"type": "string", "description": "Programming language (python, javascript, etc.)"},
                                "context": {"type": "string", "description": "Optional existing code or context"},
                                "requirements": {"type": "array", "items": {"type": "string"}, "description": "Specific requirements or constraints"}
                            },
                            "required": ["task"]
                        }
                    },
                    {
                        "name": "deepseek_analyze",
                        "description": "Analyze code for issues, improvements, and best practices.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to analyze"},
                                "focus": {"type": "string", "description": "Analysis focus: performance, security, readability, all", "default": "all"},
                                "language": {"type": "string", "description": "Programming language"}
                            },
                            "required": ["code"]
                        }
                    },
                    {
                        "name": "deepseek_refactor",
                        "description": "Refactor code to improve quality, readability, or performance.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to refactor"},
                                "goal": {"type": "string", "description": "Refactoring goal: simplify, optimize, modernize, dry"},
                                "language": {"type": "string", "description": "Programming language"},
                                "preserve_interface": {"type": "boolean", "description": "Keep the same public API", "default": True}
                            },
                            "required": ["code"]
                        }
                    },
                    {
                        "name": "deepseek_explain",
                        "description": "Explain code in detail, suitable for learning or documentation.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to explain"},
                                "level": {"type": "string", "description": "Explanation level: beginner, intermediate, advanced", "default": "intermediate"},
                                "language": {"type": "string", "description": "Programming language"}
                            },
                            "required": ["code"]
                        }
                    },
                    {
                        "name": "deepseek_test",
                        "description": "Generate test cases for code using pytest, unittest, or other frameworks.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to test"},
                                "framework": {"type": "string", "description": "Test framework: pytest, unittest, jest, mocha", "default": "pytest"},
                                "coverage": {"type": "string", "description": "Coverage level: basic, comprehensive, edge_cases", "default": "comprehensive"}
                            },
                            "required": ["code"]
                        }
                    },
                    {
                        "name": "deepseek_debug",
                        "description": "Help debug code issues, errors, and unexpected behavior.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code with the bug"},
                                "error": {"type": "string", "description": "Error message or description of the issue"},
                                "expected": {"type": "string", "description": "Expected behavior"},
                                "actual": {"type": "string", "description": "Actual behavior"}
                            },
                            "required": ["code", "error"]
                        }
                    },
                    {
                        "name": "deepseek_document",
                        "description": "Generate documentation, docstrings, and comments for code.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "description": "Code to document"},
                                "style": {"type": "string", "description": "Documentation style: google, numpy, sphinx, jsdoc", "default": "google"},
                                "include_examples": {"type": "boolean", "description": "Include usage examples", "default": True}
                            },
                            "required": ["code"]
                        }
                    }
                ]
            })
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name](tool_args)
                    return self._create_response(request_id, {
                        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                    })
                except Exception as e:
                    return self._create_error(request_id, -32000, str(e))
            else:
                return self._create_error(request_id, -32601, f"Unknown tool: {tool_name}")
        
        return self._create_error(request_id, -32601, f"Unknown method: {method}")
    
    def _create_response(self, request_id: Any, result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    
    def _create_error(self, request_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    
    # === Tool Implementations (synchronous) ===
    
    def deepseek_chat(self, args: dict) -> dict:
        """General chat with DeepSeek."""
        message = args.get("message", "")
        system_prompt = args.get("system_prompt", "You are a helpful AI assistant.")
        temperature = args.get("temperature", DEFAULT_TEMPERATURE)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        return self._call_deepseek_api(messages, temperature=temperature)
    
    def deepseek_code(self, args: dict) -> dict:
        """Generate code with DeepSeek."""
        task = args.get("task", "")
        language = args.get("language", "python")
        context = args.get("context", "")
        requirements = args.get("requirements", [])
        
        system_prompt = f"""You are an expert {language} programmer. Generate clean, efficient, well-documented code.
Follow best practices and modern conventions for {language}.
Include necessary imports and type hints where applicable.
"""
        
        user_message = f"Task: {task}"
        if context:
            user_message += f"\n\nExisting context/code:\n```{language}\n{context}\n```"
        if requirements:
            user_message += f"\n\nRequirements:\n" + "\n".join(f"- {r}" for r in requirements)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)
    
    def deepseek_analyze(self, args: dict) -> dict:
        """Analyze code for issues and improvements."""
        code = args.get("code", "")
        focus = args.get("focus", "all")
        language = args.get("language", "python")
        
        focus_prompts = {
            "performance": "Focus on performance issues: inefficient algorithms, memory leaks, unnecessary operations.",
            "security": "Focus on security vulnerabilities: injection risks, data exposure, authentication issues.",
            "readability": "Focus on readability: naming, structure, comments, code organization.",
            "all": "Analyze for performance, security, readability, and best practices."
        }
        
        system_prompt = f"""You are an expert code reviewer specializing in {language}.
{focus_prompts.get(focus, focus_prompts['all'])}
Provide specific, actionable feedback with examples.
"""
        
        user_message = f"Analyze this {language} code:\n\n```{language}\n{code}\n```"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)
    
    def deepseek_refactor(self, args: dict) -> dict:
        """Refactor code to improve quality."""
        code = args.get("code", "")
        goal = args.get("goal", "simplify")
        language = args.get("language", "python")
        preserve_interface = args.get("preserve_interface", True)
        
        goal_prompts = {
            "simplify": "Simplify the code while maintaining functionality. Remove complexity.",
            "optimize": "Optimize for performance. Improve algorithmic efficiency.",
            "modernize": "Update to use modern language features and patterns.",
            "dry": "Apply DRY principle. Extract repeated code into reusable functions."
        }
        
        interface_note = "IMPORTANT: Preserve the existing public API and interfaces." if preserve_interface else ""
        
        system_prompt = f"""You are an expert {language} refactoring specialist.
{goal_prompts.get(goal, goal_prompts['simplify'])}
{interface_note}
Show the refactored code with explanations of changes.
"""
        
        user_message = f"Refactor this {language} code:\n\n```{language}\n{code}\n```"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)
    
    def deepseek_explain(self, args: dict) -> dict:
        """Explain code in detail."""
        code = args.get("code", "")
        level = args.get("level", "intermediate")
        language = args.get("language", "python")
        
        level_prompts = {
            "beginner": "Explain as if to someone new to programming. Define terms and concepts.",
            "intermediate": "Explain assuming familiarity with programming basics.",
            "advanced": "Provide technical depth, discuss trade-offs and alternatives."
        }
        
        system_prompt = f"""You are a patient {language} instructor.
{level_prompts.get(level, level_prompts['intermediate'])}
Break down the code step by step. Use clear examples.
"""
        
        user_message = f"Explain this {language} code:\n\n```{language}\n{code}\n```"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.5)
    
    def deepseek_test(self, args: dict) -> dict:
        """Generate test cases for code."""
        code = args.get("code", "")
        framework = args.get("framework", "pytest")
        coverage = args.get("coverage", "comprehensive")
        
        coverage_prompts = {
            "basic": "Generate basic happy-path tests.",
            "comprehensive": "Generate tests for normal cases, edge cases, and error handling.",
            "edge_cases": "Focus on edge cases, boundary conditions, and unusual inputs."
        }
        
        system_prompt = f"""You are a test engineering expert using {framework}.
{coverage_prompts.get(coverage, coverage_prompts['comprehensive'])}
Generate well-organized, readable tests with clear assertions.
Include appropriate fixtures, mocks, and parametrization where useful.
"""
        
        user_message = f"Generate {framework} tests for this code:\n\n```python\n{code}\n```"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)
    
    def deepseek_debug(self, args: dict) -> dict:
        """Help debug code issues."""
        code = args.get("code", "")
        error = args.get("error", "")
        expected = args.get("expected", "")
        actual = args.get("actual", "")
        
        system_prompt = """You are an expert debugger. Analyze the code and error carefully.
1. Identify the root cause of the issue
2. Explain why the error occurs
3. Provide a corrected version of the code
4. Suggest how to prevent similar issues
"""
        
        user_message = f"Debug this code:\n\n```python\n{code}\n```\n\nError: {error}"
        if expected:
            user_message += f"\n\nExpected behavior: {expected}"
        if actual:
            user_message += f"\n\nActual behavior: {actual}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)
    
    def deepseek_document(self, args: dict) -> dict:
        """Generate documentation for code."""
        code = args.get("code", "")
        style = args.get("style", "google")
        include_examples = args.get("include_examples", True)
        
        examples_note = "Include usage examples in the documentation." if include_examples else ""
        
        system_prompt = f"""You are a technical documentation expert.
Generate {style}-style docstrings and documentation.
{examples_note}
Be thorough but concise. Document parameters, return values, exceptions.
"""
        
        user_message = f"Add comprehensive documentation to this code:\n\n```python\n{code}\n```"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return self._call_deepseek_api(messages, temperature=0.3)


def main():
    """Main entry point for MCP server (synchronous stdin/stdout)."""
    server = DeepSeekMCPServer()
    
    # Read from stdin line by line (synchronous for Windows compatibility)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            
            # Skip notifications (requests without id) - don't send response
            request_id = request.get("id")
            if request_id is None:
                # This is a notification, process but don't respond
                try:
                    server.handle_request(request)
                except Exception:
                    pass
                continue
            
            response = server.handle_request(request)
            
            # Write response to stdout
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            # Invalid JSON - ignore silently
            continue
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
