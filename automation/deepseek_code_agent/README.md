# DeepSeek Code Agent 🤖

AI-powered code assistant using DeepSeek API for code generation, refactoring, bug fixing, and test generation.

## Features

- ✅ **Code Generation** - Generate code from natural language descriptions
- ✅ **Code Refactoring** - Refactor existing code with specific instructions
- ✅ **Bug Fixing** - Fix errors with error context and explanations
- ✅ **Test Generation** - Generate comprehensive unit tests
- ✅ **Circuit Breaker Protection** - Automatic failover on API errors
- ✅ **Prometheus Metrics** - Monitor usage via `code_agent_*` metrics

## Quick Start

```python
from automation.deepseek_code_agent.code_agent import (
    DeepSeekCodeAgent,
    CodeGenerationRequest,
    CodeRefactorRequest,
    BugFixRequest,
    TestGenerationRequest
)

# Initialize agent (loads keys from KeyManager)
agent = DeepSeekCodeAgent()

# Generate code
result = await agent.generate_code(
    CodeGenerationRequest(
        prompt="Create a function to calculate factorial recursively",
        language="python",
        style="production"
    )
)
print(result['code'])
```

## Usage Examples

### 1. Code Generation

```python
gen_result = await agent.generate_code(
    CodeGenerationRequest(
        prompt="Create an async HTTP client with retry logic",
        language="python",
        context="Using httpx library",  # Optional context
        style="production"  # production, quick, experimental
    )
)

print(f"Code:\n{gen_result['code']}")
print(f"Explanation: {gen_result['explanation']}")
print(f"Suggestions: {gen_result['suggestions']}")
```

### 2. Code Refactoring

```python
old_code = """
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
"""

refactor_result = await agent.refactor_code(
    CodeRefactorRequest(
        code=old_code,
        instructions="Use list comprehension and add type hints",
        language="python",
        preserve_behavior=True
    )
)

print(f"Refactored:\n{refactor_result['refactored_code']}")
print(f"Changes: {refactor_result['changes']}")
```

### 3. Bug Fixing

```python
buggy_code = """
def calculate_average(numbers):
    return sum(numbers) / len(numbers)
"""

fix_result = await agent.fix_errors(
    BugFixRequest(
        code=buggy_code,
        error_message="ZeroDivisionError: division by zero",
        traceback="Traceback (most recent call last):\n  ...",  # Optional
        language="python"
    )
)

print(f"Fixed:\n{fix_result['fixed_code']}")
print(f"Root Cause: {fix_result['root_cause']}")
print(f"Prevention: {fix_result['prevention']}")
```

### 4. Test Generation

```python
test_result = await agent.generate_tests(
    TestGenerationRequest(
        code=my_function_code,
        framework="pytest",  # pytest, unittest, jest
        coverage_target="comprehensive",  # basic, comprehensive, edge-cases
        language="python"
    )
)

print(f"Tests:\n{test_result['test_code']}")
print(f"Test Cases: {test_result['test_cases']}")
print(f"Coverage Notes: {test_result['coverage_notes']}")
```

## Configuration

### Custom API Keys

```python
agent = DeepSeekCodeAgent(
    api_keys=["key1", "key2", "key3"],  # Custom keys
    model="deepseek-coder",  # Best for code
    max_concurrent=5  # Max parallel requests
)
```

### Using KeyManager (Recommended)

```python
# Automatically loads keys from encrypted storage
agent = DeepSeekCodeAgent()  # No keys needed!
```

## Architecture

### Integration with ParallelDeepSeekClientV2

```
DeepSeekCodeAgent
    ↓
ParallelDeepSeekClientV2 (key_id_prefix="code_agent")
    ↓
Circuit Breaker V2 (per-key protection)
    ↓
DeepSeek API (deepseek-coder model)
```

### Metrics Namespace

All metrics use `key_id_prefix="code_agent"` for isolation:

```
circuit_breaker_state{key_id="code_agent_abc123", provider="deepseek"} 0
deepseek_api_calls_total{key_id="code_agent_abc123", status="success"} 42
```

## API Reference

### DeepSeekCodeAgent

#### `__init__(api_keys=None, model="deepseek-coder", max_concurrent=3)`

Initialize the code agent.

**Parameters:**
- `api_keys` (List[str], optional): DeepSeek API keys (loads from KeyManager if None)
- `model` (str): DeepSeek model ("deepseek-coder" recommended)
- `max_concurrent` (int): Max parallel requests

#### `async generate_code(request: CodeGenerationRequest) -> Dict`

Generate code from natural language.

**Returns:**
```python
{
    "success": True,
    "code": "generated code",
    "explanation": "explanation text",
    "suggestions": "additional suggestions",
    "language": "python",
    "usage": {"prompt_tokens": 100, "completion_tokens": 200}
}
```

#### `async refactor_code(request: CodeRefactorRequest) -> Dict`

Refactor existing code.

**Returns:**
```python
{
    "success": True,
    "refactored_code": "refactored code",
    "changes": ["change 1", "change 2"],
    "explanation": "explanation text",
    "usage": {...}
}
```

#### `async fix_errors(request: BugFixRequest) -> Dict`

Fix bugs with error context.

**Returns:**
```python
{
    "success": True,
    "fixed_code": "fixed code",
    "root_cause": "root cause analysis",
    "fix_explanation": "fix explanation",
    "prevention": "prevention tips",
    "usage": {...}
}
```

#### `async generate_tests(request: TestGenerationRequest) -> Dict`

Generate unit tests.

**Returns:**
```python
{
    "success": True,
    "test_code": "test code",
    "test_cases": ["test case 1", "test case 2"],
    "coverage_notes": "coverage notes",
    "usage": {...}
}
```

## Performance

- **Latency:** ~1-3 seconds per request (network dependent)
- **Throughput:** Up to 5 requests/second with 5 API keys
- **Circuit Breaker:** Automatic failover on errors
- **Rate Limits:** Handled automatically with key rotation

## Comparison with GitHub Copilot

| Feature | GitHub Copilot | DeepSeek Code Agent |
|---------|----------------|---------------------|
| IDE Integration | ✅ Native | ⚠️ Via API |
| Real-time Autocomplete | ✅ Yes | ❌ No |
| Code Generation | ✅ Yes | ✅ Yes |
| Refactoring | ✅ Yes | ✅ Yes |
| Bug Fixing | ✅ Yes | ✅ Yes |
| Test Generation | ✅ Yes | ✅ Yes |
| Customizable Prompts | ⚠️ Limited | ✅ Full control |
| Self-hosted | ❌ No | ✅ Yes |
| Cost | $10/month | ~$0.01/1000 tokens |

## Troubleshooting

### "No API keys available"

```bash
# Add keys via KeyManager
python automation/task2_key_manager/key_manager.py add deepseek YOUR_KEY
```

### "All providers failed"

Check circuit breaker state:
```bash
curl http://localhost:9090/api/v1/query?query=circuit_breaker_state{key_id=~"code_agent_.*"}
```

### "Rate limit exceeded"

Add more API keys or reduce `max_concurrent`:
```python
agent = DeepSeekCodeAgent(max_concurrent=2)
```

## Examples

See `code_agent.py` for complete examples:
```bash
python automation/deepseek_code_agent/code_agent.py
```

## License

Part of Bybit Strategy Tester v2 project.
