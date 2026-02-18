"""
🔍 PROJECT ECOSYSTEM AUDIT: AI Agents assess project readiness for autonomous work

Два агента комплексно аудитируют проект, определяя что нужно доработать,
чтобы проект стал полноценной рабочей средой для AI-агентов.

Сценарий:
  Phase 1: DeepSeek — исследует структуру проекта, агентскую инфраструктуру,
           MCP-инструменты, конфигурации, документацию. Находит GAPs.
  Phase 2: Qwen — читает конкретные файлы по найденным GAPs, предлагает
           конкретные доработки с приоритетами.
  Phase 3: DeepSeek — рецензирует предложения, оценивает трудозатраты.
  Phase 4: Qwen — финальный roadmap с конкретными задачами.

Фокус: не просто "баги", а что нужно чтобы агенты могли:
  - Автономно запускать бэктесты
  - Анализировать результаты
  - Предлагать оптимизации стратегий
  - Работать с базой данных
  - Мониторить систему
  - Самообучаться на результатах

Запуск:
  .\\.venv\\Scripts\\python.exe demo_project_audit.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")
QW_KEY = os.getenv("QWEN_API_KEY", "")
DS_URL = "https://api.deepseek.com/v1/chat/completions"
QW_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

DS_MODEL = "deepseek-chat"
QW_MODEL = "qwen3-coder-flash"
DS_TEMPERATURE = 0.0
QW_TEMPERATURE = 0.1

PROJECT_ROOT = Path(__file__).parent.resolve()

# ─── Project Context для агентов ──────────────────────────────────────────
PROJECT_CONTEXT = """
## Project: Bybit Strategy Tester v2 — Контекст для Экосистемного Аудита

**Назначение:** Система бэктестинга криптовалютных стратегий для Bybit с паритетом
метрик TradingView. Проект включает AI-агентскую систему для автоматического
анализа, оптимизации и мониторинга торговых стратегий.

**Стек:** Python 3.13, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, Bybit API v5

**Масштаб:**
- 517 Python файлов в backend/, 135 тестов в tests/
- 753 API маршрута на /api/v1/
- Commission = 0.0007 (НЕ менять — паритет TradingView)
- FallbackEngineV4 — эталонный движок (2687 строк)
- 166 TradingView-parity метрик

**AI-Агентская Инфраструктура (ТЕКУЩЕЕ СОСТОЯНИЕ):**
- backend/agents/llm/connections.py — DeepSeek + Qwen коннекторы (969 строк)
- backend/agents/mcp/ — MCP tool registry + trading_tools (5 файлов)
- backend/agents/self_improvement/ — Модули: self_reflection, feedback_loop,
  llm_reflection, strategy_evolution, performance_evaluator (7 файлов)
- backend/agents/consensus/ — Многоагентный консенсус
- backend/agents/communication/ — Межагентная коммуникация
- backend/agents/memory/ — Агентская память
- mcp-server/ — MCP сервер (отдельный проект, 150+ файлов)
- demo_self_improvement.py — Рабочая демо: DeepSeek аудит + Qwen фикс (71.7сек)

**ВОПРОС ДЛЯ АУДИТА:**
Что нужно доработать/добавить, чтобы AI-агенты (DeepSeek + Qwen) могли
АВТОНОМНО работать с проектом? Включая:
1. Запуск бэктестов и анализ результатов
2. Оптимизация параметров стратегий
3. Работа с базой данных (чтение метрик, истории)
4. Мониторинг здоровья системы
5. Самообучение на результатах прошлых бэктестов
6. Создание и тестирование новых стратегий

**КРИТЕРИИ ОЦЕНКИ GAP:**
- Какие инструменты есть vs. нужны?
- Какие API endpoints агенты могут вызывать?
- Достаточна ли документация для агентов?
- Есть ли обратная связь (результат → обучение)?
- Безопасность: что агенты НЕ должны делать?
"""


# ─── Colors ───────────────────────────────────────────────────────────────
C_DS = "\033[96m"
C_QW = "\033[93m"
C_TOOL = "\033[92m"
C_SYS = "\033[90m"
C_HDR = "\033[95m"
C_R = "\033[0m"


def header(text: str):
    print(f"\n{C_HDR}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{C_R}\n")


def agent_says(name: str, color: str, text: str):
    print(f"{color}+-- {name} {'─' * max(1, 55 - len(name))}")
    for line in text.strip().split("\n"):
        print(f"| {line}")
    print(f"+{'─' * 60}{C_R}\n")


def tool_result(name: str, result_text: str):
    lines = result_text.strip().split("\n")
    preview = lines[:30]
    print(f"{C_TOOL}  [TOOL] {name}")
    for line in preview:
        print(f"  | {line}")
    if len(lines) > 30:
        print(f"  | ... (+{len(lines) - 30} more lines)")
    print(f"  +{'─' * 50}{C_R}\n")


def system_msg(text: str):
    print(f"{C_SYS}  >> {text}{C_R}")


# ─── Local Tool Implementations ──────────────────────────────────────────
BLOCKED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "bybit_strategy_tester.egg-info",
    "build",
    "logs",
    "data",
    "agent_memory",
    "journal",
    "screenshots",
    "dump.rdb",
}
BLOCKED_PREFIXES = ("test_e2e_test_", "test_eval_test_", "test_memory_test_")
BLOCKED_FILES = {".env", "server.key", "server.crt"}


def local_list_project_structure(directory: str = ".", max_depth: int = 3) -> dict:
    """List project structure locally."""
    target = (PROJECT_ROOT / directory).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        return {"success": False, "error": "Path outside project"}

    def build_tree(path: Path, depth: int = 0) -> dict:
        if depth > max_depth:
            return {"name": path.name, "type": "dir", "truncated": True}
        result = {"name": path.name, "type": "dir" if path.is_dir() else "file"}
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir()):
                    if child.name.startswith("."):
                        continue
                    if child.name in BLOCKED_DIRS:
                        continue
                    if any(child.name.startswith(p) for p in BLOCKED_PREFIXES):
                        continue
                    children.append(build_tree(child, depth + 1))
            except PermissionError:
                pass
            result["children"] = children
        return result

    tree = build_tree(target)
    return {"success": True, "structure": tree}


def local_read_project_file(
    file_path: str,
    max_size_kb: int = 80,
    start_line: int = 1,
    max_lines: int = 200,
) -> dict:
    """Read a project file locally with pagination."""
    target = (PROJECT_ROOT / file_path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        return {"success": False, "error": "Path outside project"}
    if not target.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    if target.name in BLOCKED_FILES:
        return {"success": False, "error": f"Blocked: {target.name}"}

    size = target.stat().st_size
    all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    total_lines = len(all_lines)

    start_idx = max(0, start_line - 1)
    end_idx = min(total_lines, start_idx + max_lines)
    selected = all_lines[start_idx:end_idx]
    content = "\n".join(selected)

    has_more = end_idx < total_lines
    return {
        "success": True,
        "content": content,
        "file_path": file_path,
        "total_lines": total_lines,
        "showing_lines": f"{start_idx + 1}-{end_idx}",
        "has_more": has_more,
        "next_start_line": end_idx + 1 if has_more else None,
        "size_kb": round(size / 1024, 1),
    }


def local_search_in_files(
    pattern: str,
    directory: str = "backend",
    file_ext: str = ".py",
    max_results: int = 20,
) -> dict:
    """Search for pattern in project files (grep-like)."""
    target = (PROJECT_ROOT / directory).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        return {"success": False, "error": "Path outside project"}

    results = []
    pattern_lower = pattern.lower()

    for py_file in target.rglob(f"*{file_ext}"):
        if any(part in BLOCKED_DIRS for part in py_file.parts):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
            for i, line in enumerate(lines, 1):
                if pattern_lower in line.lower():
                    rel_path = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
                    results.append(
                        {
                            "file": rel_path,
                            "line": i,
                            "text": line.strip()[:150],
                        }
                    )
                    if len(results) >= max_results:
                        return {"success": True, "results": results, "truncated": True}
        except Exception:
            continue

    return {"success": True, "results": results, "truncated": False}


def local_list_api_endpoints(prefix: str = "") -> dict:
    """List API router files and their prefixes."""
    routers_dir = PROJECT_ROOT / "backend" / "api" / "routers"
    if not routers_dir.exists():
        return {"success": False, "error": "Routers directory not found"}

    endpoints = []
    for f in sorted(routers_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            # Extract router prefix
            for line in content.split("\n"):
                if "prefix=" in line and "APIRouter" in line:
                    endpoints.append({"file": f.name, "declaration": line.strip()[:120]})
                    break
                if 'prefix="' in line or "prefix='" in line:
                    endpoints.append({"file": f.name, "declaration": line.strip()[:120]})
                    break
            else:
                endpoints.append({"file": f.name, "declaration": "(no prefix found)"})
        except Exception:
            endpoints.append({"file": f.name, "declaration": "(read error)"})

    if prefix:
        endpoints = [e for e in endpoints if prefix.lower() in e["declaration"].lower()]

    return {"success": True, "endpoints": endpoints, "total": len(endpoints)}


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return JSON result."""
    handlers = {
        "mcp_list_project_structure": lambda: local_list_project_structure(
            args.get("directory", "."),
            args.get("max_depth", 2),
        ),
        "mcp_read_project_file": lambda: local_read_project_file(
            file_path=args.get("file_path", ""),
            start_line=args.get("start_line", 1),
            max_lines=args.get("max_lines", 200),
        ),
        "mcp_search_in_files": lambda: local_search_in_files(
            pattern=args.get("pattern", ""),
            directory=args.get("directory", "backend"),
            file_ext=args.get("file_ext", ".py"),
            max_results=args.get("max_results", 20),
        ),
        "mcp_list_api_endpoints": lambda: local_list_api_endpoints(
            prefix=args.get("prefix", ""),
        ),
    }
    handler = handlers.get(name)
    if handler:
        result = handler()
    else:
        result = {"success": False, "error": f"Unknown tool: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


def format_tree(node: dict, prefix: str = "", is_last: bool = True) -> str:
    connector = "L-- " if is_last else "|-- "
    name = node.get("name", "?")
    ntype = node.get("type", "file")
    line = f"{prefix}{connector}{name}/" if ntype == "dir" else f"{prefix}{connector}{name}"
    lines = [line]
    for i, child in enumerate(node.get("children", [])):
        ext = "    " if is_last else "|   "
        lines.append(format_tree(child, prefix + ext, i == len(node.get("children", [])) - 1))
    return "\n".join(lines)


# ─── Tool Spec (расширенный для экосистемного аудита) ─────────────────────
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "mcp_list_project_structure",
            "description": (
                "List directory structure. Use to explore project layout. "
                "Good starting points: 'backend/agents', 'backend/api/routers', "
                "'backend/backtesting', 'mcp-server/tools', 'tests'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative path from project root",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Depth 1-4 (default: 2)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_read_project_file",
            "description": (
                "Read a project file with pagination. Key files to check: "
                "backend/agents/llm/connections.py, backend/agents/mcp/tool_registry.py, "
                "backend/agents/mcp/trading_tools.py, backend/agents/self_improvement/*.py, "
                "AGENTS.MD, .github/copilot-instructions.md"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to file"},
                    "start_line": {"type": "integer", "description": "Start line (default: 1)"},
                    "max_lines": {"type": "integer", "description": "Max lines (default: 200)"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_search_in_files",
            "description": (
                "Search for a text pattern in project files (case-insensitive grep). "
                "Use to find: tool registrations, API endpoints, agent capabilities, "
                "config constants, TODO/FIXME comments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text to search for"},
                    "directory": {"type": "string", "description": "Dir to search (default: 'backend')"},
                    "file_ext": {"type": "string", "description": "File extension filter (default: '.py')"},
                    "max_results": {"type": "integer", "description": "Max results (default: 20)"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_list_api_endpoints",
            "description": (
                "List all API router files in backend/api/routers/ with their URL prefixes. "
                "Use to understand what HTTP API is available for agents to call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prefix": {"type": "string", "description": "Filter by prefix substring (optional)"},
                },
                "required": [],
            },
        },
    },
]


# ─── LLM Call Functions ──────────────────────────────────────────────────
async def call_llm_with_tools(
    session: aiohttp.ClientSession,
    url: str,
    key: str,
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tool_rounds: int = 6,
    max_tokens: int = 4000,
    temperature: float = 0.0,
    presence_penalty: float = 0.0,
    parallel_tool_calls: bool = False,
    seed: int | None = None,
) -> tuple[str, int]:
    """Call LLM with tool support. Returns (text, api_calls)."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    conversation = [{"role": "system", "content": system}, *messages]
    total_calls = 0

    for round_num in range(max_tool_rounds + 1):
        payload = {
            "model": model,
            "messages": conversation,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tool_choice": "auto",
        }
        if presence_penalty != 0.0:
            payload["presence_penalty"] = presence_penalty
        if seed is not None:
            payload["seed"] = seed
        if tools and round_num < max_tool_rounds:
            payload["tools"] = tools
            if parallel_tool_calls:
                payload["parallel_tool_calls"] = True

        async with session.post(url, json=payload, headers=headers) as resp:
            total_calls += 1
            if resp.status != 200:
                error = await resp.text()
                return f"[API Error {resp.status}]: {error[:300]}", total_calls
            data = await resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return message.get("content", ""), total_calls

        conversation.append(message)

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            system_msg(f"Agent calls: {func_name}({json.dumps(func_args, ensure_ascii=False)})")
            result_json = execute_tool(func_name, func_args)

            # Display tool output
            result_data = json.loads(result_json)
            if func_name == "mcp_list_project_structure" and result_data.get("success"):
                tool_result(func_name, format_tree(result_data["structure"]))
            elif func_name == "mcp_read_project_file" and result_data.get("success"):
                lines = result_data["content"].split("\n")
                preview = "\n".join(lines[:30])
                showing = result_data.get("showing_lines", "?")
                total = result_data.get("total_lines", "?")
                has_more = result_data.get("has_more", False)
                if len(lines) > 30:
                    preview += f"\n... (+{len(lines) - 30} more in this chunk)"
                extra = f" [MORE from line {result_data.get('next_start_line')}]" if has_more else ""
                tool_result(f"read {func_args.get('file_path', '?')} [{showing}/{total}]{extra}", preview)
            elif func_name == "mcp_search_in_files" and result_data.get("success"):
                matches = result_data.get("results", [])
                text = "\n".join(f"  {m['file']}:{m['line']} — {m['text']}" for m in matches[:15])
                if not text:
                    text = "(no matches)"
                tool_result(f"search '{func_args.get('pattern', '?')}' → {len(matches)} results", text)
            elif func_name == "mcp_list_api_endpoints" and result_data.get("success"):
                eps = result_data.get("endpoints", [])
                text = "\n".join(f"  {e['file']}: {e['declaration']}" for e in eps[:20])
                tool_result(f"API endpoints ({result_data.get('total', 0)} total)", text)
            else:
                tool_result(func_name, json.dumps(result_data, indent=2)[:500])

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_json[:8000],
                }
            )

    return "[Max tool rounds exceeded]", total_calls


async def call_llm_simple(
    session: aiohttp.ClientSession,
    url: str,
    key: str,
    model: str,
    system: str,
    user_msg: str,
    max_tokens: int = 2000,
    temperature: float = 0.0,
    presence_penalty: float = 0.0,
) -> tuple[str, int]:
    """Simple LLM call without tools."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if presence_penalty != 0.0:
        payload["presence_penalty"] = presence_penalty
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            error = await resp.text()
            return f"[API Error {resp.status}]: {error[:300]}", 1
        data = await resp.json()
        return data["choices"][0]["message"]["content"], 1


# ─── System Prompts ──────────────────────────────────────────────────────
ARCHITECT_SYSTEM = f"""You are a Senior AI/ML Architect doing an ECOSYSTEM AUDIT.

{PROJECT_CONTEXT}

Your goal: determine what the project NEEDS so that AI agents can work AUTONOMOUSLY.

You have tools to explore the project. Use them strategically:
- List structure to see what modules exist
- Read key files to understand current capabilities
- Search for patterns to find gaps
- List API endpoints to see what's callable

Think like an architect: what's the GAP between current state and
"agents can autonomously run backtests, analyze results, optimize strategies"?

Respond in Russian. Be concrete — file paths, function names, missing tools.
Do NOT suggest generic advice. Every recommendation must be ACTIONABLE.
"""

ENGINEER_SYSTEM = f"""You are a Senior Backend Engineer specializing in AI agent tooling.

{PROJECT_CONTEXT}

You receive an architect's gap analysis and must propose CONCRETE implementations.
Use tools to read actual code and verify your proposals are feasible.

For each proposal:
- Exact file(s) to create or modify
- Key functions/classes to add
- Estimated effort (hours)
- Priority (P0-critical, P1-high, P2-medium, P3-nice-to-have)
- Dependencies on other proposals

Respond in Russian. Be pragmatic — propose what actually works, not theory.
"""


# ─── Main ─────────────────────────────────────────────────────────────────
async def main():
    if not DS_KEY or not QW_KEY:
        print("Set DEEPSEEK_API_KEY and QWEN_API_KEY in .env")
        sys.exit(1)

    header("PROJECT ECOSYSTEM AUDIT")
    print(f"  Date:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Architect: DeepSeek {DS_MODEL} (gap analysis)")
    print(f"  Engineer:  Qwen {QW_MODEL} (implementation plan)")
    print("  Focus:     Agent autonomy readiness")
    print(f"  Project:   {PROJECT_ROOT.name}")
    print()

    total_start = time.time()
    total_api_calls = 0
    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # ── Pre-flight ────────────────────────────────────────────
        system_msg("Checking API connectivity...")
        for name, url, key, model in [
            ("DeepSeek", DS_URL, DS_KEY, DS_MODEL),
            ("Qwen", QW_URL, QW_KEY, QW_MODEL),
        ]:
            for attempt in range(3):
                try:
                    test_payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                    }
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    async with session.post(url, json=test_payload, headers=headers) as resp:
                        if resp.status == 200:
                            system_msg(f"  {name}: OK")
                            break
                        else:
                            system_msg(f"  {name}: status {resp.status}, retry {attempt + 1}/3...")
                except Exception as e:
                    system_msg(f"  {name}: error ({type(e).__name__}), retry {attempt + 1}/3...")
                    await asyncio.sleep(3)
            else:
                print(f"\n  FATAL: Cannot connect to {name}")
                sys.exit(1)

        print()

        # ═════════════════════════════════════════════════════════════
        # PHASE 1: Architect explores project, finds GAPs
        # ═════════════════════════════════════════════════════════════
        header("PHASE 1: GAP ANALYSIS (DeepSeek explores project ecosystem)")

        system_msg("DeepSeek explores agent infrastructure, tools, APIs...")
        print()

        # noinspection RuCyrillicWarning
        audit_task = (
            "Provedite ekosistemnyy audit proekta dlya agent-readiness.\n\n"
            "STRATEGIYA ISSLEDOVANIYA (8 instrumentov maximum):\n"
            "1. mcp_list_project_structure('backend/agents') - structure agentskoy sistemy\n"
            "2. mcp_read_project_file('backend/agents/mcp/trading_tools.py') - kakie tools est'\n"
            "3. mcp_list_api_endpoints() - kakie API endpoints dostupny\n"
            "4. mcp_read_project_file('backend/agents/self_improvement/self_reflection.py', max_lines=100) - samouluchshenie\n"
            "5. mcp_search_in_files('run_backtest', 'backend') - kak zapuskat' backtesty\n"
            "6. mcp_read_project_file('backend/agents/mcp/tool_registry.py', max_lines=80) - tool registry\n"
            "7. mcp_search_in_files('agent', 'backend/api/routers') - est' li API dlya agentov\n"
            "8. mcp_list_project_structure('backend/agents/memory') - pamyat' agentov\n\n"
            "POSLE issledovaniya napishi GAP ANALYSIS:\n"
            "- Chto YEST' (current capabilities)\n"
            "- Chto NUZHNO (required for autonomy)\n"
            "- GAP (raznitsa)\n\n"
            "Kategorii:\n"
            "1. TOOLS - kakie instrumenty agentam nuzhny no ikh net\n"
            "2. API - kakie endpointy agenty dolzhny vyzyvat'\n"
            "3. MEMORY - kak agenty dolzhny zapominat' i uchit'sya\n"
            "4. WORKFLOW - kakie rabochie protsessy avtomatizirovat'\n"
            "5. SAFETY - chto agenty NE dolzhny delat'\n"
            "6. DOCS - kakaya dokumentatsiya nuzhna agentam\n\n"
            "Respond in Russian. Maximum 800 words. Be SPECIFIC - file paths, function names."
        )

        audit_response, calls = await call_llm_with_tools(
            session,
            DS_URL,
            DS_KEY,
            DS_MODEL,
            ARCHITECT_SYSTEM,
            [{"role": "user", "content": audit_task}],
            tools=TOOLS_SPEC,
            max_tool_rounds=10,
            max_tokens=4000,
            temperature=DS_TEMPERATURE,
            presence_penalty=0.3,
        )
        total_api_calls += calls
        agent_says("ARCHITECT (DeepSeek) - Gap Analysis", C_DS, audit_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 2: Engineer reads gaps, proposes implementations
        # ═════════════════════════════════════════════════════════════
        header("PHASE 2: IMPLEMENTATION PLAN (Qwen designs solutions)")

        system_msg("Qwen reads gap analysis and proposes concrete implementations...")
        print()

        # noinspection RuCyrillicWarning
        impl_task = (
            f"Arkhitektor nashyol sleduyushchiye GAPs:\n\n"
            f"---\n{audit_response[:4000]}\n---\n\n"
            f"Tvoya zadacha — predlozhit' KONKRETNYE realizatsii:\n\n"
            f"1. Prochitay klyuchevye fayly chtoby ponyat' tekushchiy kod\n"
            f"2. Dlya KAZHDOGO gap-a predlozhi:\n"
            f"   - Fayly dlya sozdaniya/modifikatsii\n"
            f"   - Klyuchevye funktsii/klassy\n"
            f"   - Prioritet (P0/P1/P2/P3)\n"
            f"   - Trudozatraty (chasy)\n"
            f"   - Zavisimosti\n\n"
            f"3. ITOGO: top-5 zadach v poryadke prioriteta\n\n"
            f"Ispolzuy tools chtoby proverit' svoi predlozheniya.\n"
            f"Respond in Russian. Maximum 800 words."
        )

        impl_response, calls = await call_llm_with_tools(
            session,
            QW_URL,
            QW_KEY,
            QW_MODEL,
            ENGINEER_SYSTEM,
            [{"role": "user", "content": impl_task}],
            tools=TOOLS_SPEC,
            max_tool_rounds=8,
            max_tokens=4000,
            temperature=QW_TEMPERATURE,
            parallel_tool_calls=True,
            seed=42,
        )
        total_api_calls += calls
        agent_says("ENGINEER (Qwen) - Implementation Plan", C_QW, impl_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 3: Architect reviews proposals
        # ═════════════════════════════════════════════════════════════
        header("PHASE 3: REVIEW (DeepSeek reviews implementation plan)")

        system_msg("DeepSeek reviews feasibility and priorities...")

        review_task = (
            f"Inzhener predlozhil plan realizatsii:\n\n"
            f"---\n{impl_response[:4000]}\n---\n\n"
            f"Moy pervonachal'nyy analiz byl:\n"
            f"---\n{audit_response[:2000]}\n---\n\n"
            f"Otsen' kazhdoye predlozheniye:\n"
            f"- APPROVE - mozhno realizovyvat'\n"
            f"- MODIFY - ideya vernaya no nuzhna dorabotka\n"
            f"- REJECT - ne nuzhno ili opasno\n"
            f"- ADD - on propustil chto-to vazhnoye\n\n"
            f"V kontse day TOP-5 zadach s ocenkoy trudozatrat.\n"
            f"Respond in Russian. Maximum 500 words."
        )

        review_response, calls = await call_llm_simple(
            session,
            DS_URL,
            DS_KEY,
            DS_MODEL,
            ARCHITECT_SYSTEM,
            review_task,
            max_tokens=2500,
            temperature=DS_TEMPERATURE,
            presence_penalty=0.3,
        )
        total_api_calls += calls
        agent_says("ARCHITECT (DeepSeek) - Review", C_DS, review_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 4: Engineer creates final roadmap
        # ═════════════════════════════════════════════════════════════
        header("PHASE 4: FINAL ROADMAP (Qwen creates actionable plan)")

        system_msg("Qwen creates final prioritized roadmap...")

        roadmap_task = (
            f"Arkhitektor otsenilpredlozheniya:\n\n"
            f"---\n{review_response[:2500]}\n---\n\n"
            f"Sostav' FINAL'NYY ROADMAP:\n\n"
            f"Format dlya kazhdoy zadachi:\n"
            f"### [P0/P1/P2] Nazvanie\n"
            f"- Fayly: konkretnye puti\n"
            f"- Chto sdelat': 2-3 predlozheniya\n"
            f"- Trudozatraty: X chasov\n"
            f"- Rezul'tat: chto agenty smogut delat' posle\n\n"
            f"Maximum 10 zadach. Otsortirovano po prioritetu.\n"
            f"Respond in Russian. Maximum 600 words."
        )

        roadmap_response, calls = await call_llm_simple(
            session,
            QW_URL,
            QW_KEY,
            QW_MODEL,
            ENGINEER_SYSTEM,
            roadmap_task,
            max_tokens=3000,
            temperature=QW_TEMPERATURE,
        )
        total_api_calls += calls
        agent_says("ENGINEER (Qwen) - Final Roadmap", C_QW, roadmap_response)

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.time() - total_start
    header("AUDIT COMPLETE")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  API calls:  {total_api_calls}")
    print(f"  Architect:  DeepSeek {DS_MODEL}")
    print(f"  Engineer:   Qwen {QW_MODEL}")
    print()
    print("  Workflow:   GAP ANALYSIS -> IMPLEMENTATION -> REVIEW -> ROADMAP")
    print("  Output:     Prioritized roadmap for agent autonomy")
    print()

    # Save results to file
    results_file = PROJECT_ROOT / "docs" / "AGENT_ECOSYSTEM_AUDIT.md"
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, "w", encoding="utf-8") as f:
        f.write("# Agent Ecosystem Audit Results\n\n")
        f.write(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> Architect: DeepSeek {DS_MODEL} | Engineer: Qwen {QW_MODEL}\n")
        f.write(f"> Duration: {elapsed:.1f}s | API calls: {total_api_calls}\n\n")
        f.write(f"## Phase 1: Gap Analysis (DeepSeek)\n\n{audit_response}\n\n")
        f.write(f"## Phase 2: Implementation Plan (Qwen)\n\n{impl_response}\n\n")
        f.write(f"## Phase 3: Review (DeepSeek)\n\n{review_response}\n\n")
        f.write(f"## Phase 4: Final Roadmap (Qwen)\n\n{roadmap_response}\n\n")

    print(f"  Results saved to: {results_file.relative_to(PROJECT_ROOT)}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
