# Sandbox Executor - Quick Win #2

**Secure code execution environment for AI-generated trading strategies**

---

## 🎯 Quick Start

### Build Docker Image

```powershell
# Automatic build (recommended)
.\scripts\build_sandbox.ps1

# With options
.\scripts\build_sandbox.ps1 -NoBuildCache -Verbose

# Manual build
docker build -f docker/Dockerfile.sandbox -t bybit-sandbox:latest .
```

### Run Tests

```powershell
# Integration tests
pytest tests/integration/test_sandbox_executor.py -v

# Manual test script
python scripts/test_sandbox.py
```

### Execute Code

```python
from backend.services.sandbox_executor import execute_code_in_sandbox

code = """
import numpy as np
prices = np.array([100, 102, 101, 105, 103])
returns = np.diff(prices) / prices[:-1]
print(f"Mean Return: {np.mean(returns):.4f}")
"""

result = await execute_code_in_sandbox(code, timeout=30)

if result.success:
    print(result.stdout)  # "Mean Return: 0.0098"
else:
    print(f"Error: {result.error}")
```

---

## 🏗️ Architecture

### 3-Layer Security

```
┌─────────────────────────────────────────┐
│  Layer 1: Code Validation (AST)        │
│  - Blacklist dangerous modules/builtins │
│  - Risk scoring (0-100+ points)         │
│  - Reject HIGH/CRITICAL risk code       │
└─────────────────────────────────────────┘
            ↓ (if passed)
┌─────────────────────────────────────────┐
│  Layer 2: Docker Isolation              │
│  - Network isolation (--network=none)   │
│  - Read-only filesystem                 │
│  - Resource limits (CPU/RAM/time)       │
│  - Non-root user execution              │
└─────────────────────────────────────────┘
            ↓ (if passed)
┌─────────────────────────────────────────┐
│  Layer 3: Minimal Runtime               │
│  - Pre-installed packages only          │
│  - No pip, no network tools             │
│  - No build tools                       │
└─────────────────────────────────────────┘
```

---

## 📦 Components

### 1. Docker Sandbox Image

**File**: `docker/Dockerfile.sandbox`

**Base Image**: `python:3.11-slim`

**Security Features**:
- Non-root user (sandboxuser, UID 1000)
- Pre-installed packages only (no pip at runtime)
- Health checks every 30s
- Minimal attack surface

**Runtime Flags**:
```bash
docker run \
  --network=none \           # No network
  --read-only \              # Read-only FS
  --cpus=2 \                 # CPU limit
  --memory=4g \              # RAM limit
  --cap-drop=ALL \           # Drop capabilities
  --user=sandboxuser \       # Non-root
  bybit-sandbox:latest
```

### 2. Minimal Dependencies

**File**: `docker/sandbox-requirements.txt`

**Allowed Packages**:
- numpy==1.26.2
- pandas==2.1.3
- ta-lib==0.4.28
- orjson==3.9.10
- python-dateutil==2.8.2
- pytz==2023.3
- scipy==1.11.4

**Blocked Packages**:
- ❌ requests, httpx, aiohttp (network)
- ❌ sqlalchemy, psycopg2 (database)
- ❌ fastapi, flask (web frameworks)

### 3. Code Validator

**File**: `backend/core/code_validator.py`

**Features**:
- AST-based analysis (~450 lines)
- Blacklist: 16 modules, 9 builtins, 8 attributes
- Whitelist: 25 allowed modules
- Risk scoring with thresholds

**Example**:
```python
from backend.core.code_validator import CodeValidator

validator = CodeValidator()
result = validator.validate(code)

print(f"Valid: {result.is_valid}")
print(f"Risk Score: {result.risk_score}")
print(f"Risk Level: {result.risk_level}")

for violation in result.violations:
    print(f"  - {violation['message']}")
```

### 4. Sandbox Executor

**File**: `backend/services/sandbox_executor.py`

**Features**:
- Docker orchestration (~450 lines)
- Pre-execution validation
- Resource monitoring (CPU/RAM)
- Timeout enforcement
- Automatic cleanup

**Example**:
```python
from backend.services.sandbox_executor import SandboxExecutor

executor = SandboxExecutor(
    timeout=300,
    cpu_limit=2.0,
    mem_limit="4g",
    validate_code=True,
    max_risk_score=30  # LOW risk only
)

try:
    result = await executor.execute(code, timeout=120)
    
    if result.success:
        print(f"✅ Success")
        print(f"Output:\n{result.stdout}")
        print(f"Memory: {result.resource_usage['memory_usage_mb']:.0f} MB")
    else:
        print(f"❌ Failed: {result.error}")
finally:
    executor.cleanup()
```

### 5. Test Suite

**File**: `tests/integration/test_sandbox_executor.py`

**Test Cases** (20+):
- ✅ Safe code execution
- ✅ Dangerous code blocked
- ✅ Timeout enforcement
- ✅ Resource monitoring
- ✅ Network isolation
- ✅ Filesystem isolation
- ✅ Edge cases

---

## 🔒 Security Guarantees

### What is BLOCKED ✅

- ✅ Network access (socket, requests, HTTP)
- ✅ Filesystem access (read-only except /output)
- ✅ System access (os, sys, subprocess)
- ✅ Dangerous code (eval, exec, compile)
- ✅ Privilege escalation (non-root, no-new-privileges)
- ✅ Resource abuse (CPU/RAM limits, timeout)
- ✅ Infinite loops (timeout enforcement)

### What is ALLOWED ✅

- ✅ Numerical computing (numpy, pandas, scipy)
- ✅ Technical analysis (ta-lib)
- ✅ Data manipulation (JSON, datetime)
- ✅ Math operations (math, statistics)
- ✅ Type safety (typing, dataclasses)

---

## 📊 Risk Scoring

### Thresholds

| Risk Level | Score | Auto Action |
|-----------|-------|-------------|
| **LOW** | < 30 | ✅ Auto-approve |
| **MEDIUM** | 30-70 | ⚠️ Manual review |
| **HIGH** | 70-90 | ❌ Auto-reject |
| **CRITICAL** | > 90 | 🚫 Hard reject |

### Point System

| Violation | Points |
|-----------|--------|
| Blacklisted module (os, sys, socket) | +30 |
| Dangerous builtin (eval, exec, open) | +30 |
| File I/O operation | +30 |
| Lambda with exec/eval | +25 |
| Dangerous attribute (__globals__, __dict__) | +20 |
| Reflection (getattr/setattr) | +15 |
| Builtin override (eval = lambda x: x) | +10 |
| Infinite loop (while True) | +5 |
| Unknown module | +1 |

---

## 🧪 Testing

### Integration Tests

```powershell
# Run all tests
pytest tests/integration/test_sandbox_executor.py -v

# Run specific test
pytest tests/integration/test_sandbox_executor.py::test_execute_safe_code -v

# Run with coverage
pytest tests/integration/test_sandbox_executor.py --cov=backend.services.sandbox_executor
```

### Manual Testing

```powershell
# Run test script
python scripts/test_sandbox.py

# Output:
# ================================================================================
# TEST: Code Validation
# ================================================================================
# --- Safe code ---
# Valid: True
# Risk Score: 5
# Risk Level: low
# 
# --- Dangerous code (os) ---
# Valid: False
# Risk Score: 60
# Risk Level: medium
# ...
```

---

## 🔗 Integration Examples

### MCP Server Tool

```python
# mcp-server/server.py

from backend.services.sandbox_executor import execute_code_in_sandbox

@server.tool("execute_strategy_code")
async def execute_strategy_code(code: str, timeout: int = 300) -> dict:
    """Execute AI-generated strategy code in sandbox"""
    result = await execute_code_in_sandbox(code, timeout=timeout)
    return result.to_dict()
```

### Multi-Agent Pipeline

```python
from mcp_server.multi_agent_router import multi_agent_route
from backend.services.sandbox_executor import execute_code_in_sandbox

# Generate code (DeepSeek)
code_result = await multi_agent_route(
    task_type="code-generation",
    prompt="Create EMA crossover strategy"
)

# Execute in sandbox
execution_result = await execute_code_in_sandbox(
    code=code_result["response"],
    timeout=120
)

# Review results (Perplexity)
if execution_result.success:
    review = await multi_agent_route(
        task_type="audit",
        query=f"Review: {execution_result.stdout}"
    )
```

---

## 🐛 Troubleshooting

### Docker Not Running

**Error**: `DockerException: Error while fetching server API version`

**Solution**:
```powershell
# Start Docker Desktop
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
Start-Sleep -Seconds 10

# Test Docker
docker ps
```

### Image Not Found

**Error**: `ImageNotFound: bybit-sandbox:latest`

**Solution**:
```powershell
# Build image
.\scripts\build_sandbox.ps1
```

### Code Validation Too Strict

**Error**: `ValidationError: Risk score 35 exceeds maximum 30`

**Solution**:
```python
# Increase threshold
executor = SandboxExecutor(max_risk_score=50)

# Or disable validation
executor = SandboxExecutor(validate_code=False)
```

### Container Timeout

**Error**: `Container timeout after 300s`

**Solution**:
```python
# Increase timeout
result = await execute_code_in_sandbox(code, timeout=600)
```

---

## 📚 Documentation

- **Full Documentation**: [docs/QUICK_WIN_2_COMPLETE.md](../docs/QUICK_WIN_2_COMPLETE.md)
- **Implementation Plan**: [docs/TZ_IMPLEMENTATION_PLAN.md](../docs/TZ_IMPLEMENTATION_PLAN.md)
- **TZ Document**: Расширенное техническое задание_3-1.md (Section 2.7)

---

## ✅ Status

**Quick Win #2**: ✅ **COMPLETE**

**Files Created**: 5  
**Lines of Code**: ~1,200  
**Implementation Time**: ~4 hours  
**Test Cases**: 20+

**Next**: Quick Win #3 - Strategy Tournament System 🏆
