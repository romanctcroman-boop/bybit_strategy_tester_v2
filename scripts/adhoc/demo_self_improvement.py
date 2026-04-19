"""
🧠 LIVE DEMO: AI Agents Self-Improvement Session

Агенты получают:
  1. PROJECT BRIEF — краткое описание проекта (факты, не домыслы)
  2. TOOLS — mcp_list_project_structure + mcp_read_project_file
  3. ЗАДАЧУ — найти КОНКРЕТНУЮ проблему и написать КОНКРЕТНЫЙ fix

Сценарий:
  Phase 1: Agent-Auditor (DeepSeek) — аудит кода, поиск багов/code smells
  Phase 2: Agent-Fixer (Qwen) — читает найденные проблемы, пишет конкретный fix
  Phase 3: Обсуждение — согласование приоритетов, итоговый план

Запуск:
  .\\.venv\\Scripts\\python.exe demo_self_improvement.py
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

# Model selection (based on SDK research — see docs/SDK_REFERENCE.md)
DS_MODEL = "deepseek-chat"  # DeepSeek V3.2, 128K context, $0.28/1M input
QW_MODEL = "qwen3-coder-flash"  # Specialized for code + tool calling, 1M context, $0.30/1M input

# Temperature settings (from official SDK docs)
DS_TEMPERATURE = 0.0  # DeepSeek recommends 0.0 for Coding/Math tasks
QW_TEMPERATURE = 0.1  # Low temperature for precise code analysis & fixes

PROJECT_ROOT = Path(__file__).parent.resolve()

# ─── Project Brief (facts for agents) ────────────────────────────────────
PROJECT_BRIEF = """
## Project: Bybit Strategy Tester v2

**Purpose:** Backtesting system for Bybit crypto trading strategies with TradingView metric parity.

**Stack:** Python 3.13, FastAPI, SQLAlchemy, SQLite, Pandas, NumPy, Bybit API v5

**Key Facts:**
- 517 Python files in backend/, 135 test files in tests/
- 753 API routes at /api/v1/
- Commission rate = 0.0007 (0.07%) — CRITICAL, must match TradingView
- Gold standard engine: FallbackEngineV4 (backend/backtesting/engines/fallback_engine_v4.py)
- 166 TradingView-parity metrics in backend/core/metrics_calculator.py
- Multi-agent AI consensus system in backend/agents/
- Two LLM providers: DeepSeek + Qwen (backend/agents/llm/connections.py)

**Key Directories:**
- backend/backtesting/engines/ — Backtest engines (FallbackV3, V4, GPU, Numba, DCA)
- backend/api/routers/ — 70+ API router files
- backend/services/adapters/bybit.py — Bybit API integration
- backend/agents/ — AI agent system (consensus, deliberation, communication)
- backend/core/metrics_calculator.py — 166 metrics
- tests/ — 135 test files (unit, integration, e2e, load, security, chaos)
- frontend/js/ — Static HTML/JS/CSS frontend

**Known Constraints:**
- Only 9 timeframes: 1, 5, 15, 30, 60, 240, D, W, M
- Data starts from 2025-01-01 (DATA_START_DATE)
- SQLite (not PostgreSQL) — single-writer limitation

**DO NOT suggest:**
- Changing commission_rate (breaks TradingView parity)
- Switching to PostgreSQL (intentional choice for simplicity)
- General advice like "add more tests" — be SPECIFIC
"""

# ─── Colors ───────────────────────────────────────────────────────────────
C_DS = "\033[96m"  # Cyan — DeepSeek
C_QW = "\033[93m"  # Yellow — Qwen
C_TOOL = "\033[92m"  # Green — tool results
C_SYS = "\033[90m"  # Grey — system
C_HDR = "\033[95m"  # Magenta — headers
C_FIX = "\033[91m"  # Red — fixes/issues
C_R = "\033[0m"  # Reset


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
    preview = lines[:35]
    print(f"{C_TOOL}  [TOOL] {name}")
    for line in preview:
        print(f"  | {line}")
    if len(lines) > 35:
        print(f"  | ... (+{len(lines) - 35} more lines)")
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

    # Paginate
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


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return JSON result."""
    if name == "mcp_list_project_structure":
        result = local_list_project_structure(
            args.get("directory", "."),
            args.get("max_depth", 2),
        )
    elif name == "mcp_read_project_file":
        result = local_read_project_file(
            file_path=args.get("file_path", ""),
            start_line=args.get("start_line", 1),
            max_lines=args.get("max_lines", 200),
        )
    else:
        result = {"success": False, "error": f"Unknown tool: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


def format_tree(node: dict, prefix: str = "", is_last: bool = True) -> str:
    """Format tree for display."""
    connector = "L-- " if is_last else "|-- "
    name = node.get("name", "?")
    ntype = node.get("type", "file")
    line = f"{prefix}{connector}{name}/" if ntype == "dir" else f"{prefix}{connector}{name}"
    lines = [line]
    children = node.get("children", [])
    for i, child in enumerate(children):
        ext = "    " if is_last else "|   "
        lines.append(format_tree(child, prefix + ext, i == len(children) - 1))
    return "\n".join(lines)


# ─── Tool Spec ────────────────────────────────────────────────────────────
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "mcp_list_project_structure",
            "description": (
                "List directory structure of the project. "
                "Use directory='tests' to see test files, 'backend/backtesting/engines' for engines, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative path from project root. Examples: '.', 'backend/agents', 'tests'",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "How deep to traverse (1-4, default: 2)",
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
                "Read a file from the project with pagination. "
                "Returns up to max_lines lines starting from start_line. "
                "Response includes has_more and next_start_line for pagination. "
                "For large files (1000+ lines), read in chunks of 200 lines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to file from project root",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Line number to start reading from (default: 1)",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Max lines to return (default: 200, max: 400)",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
]


# ─── Tool-aware LLM Call ─────────────────────────────────────────────────
async def call_llm_with_tools(
    session: aiohttp.ClientSession,
    url: str,
    key: str,
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tool_rounds: int = 4,
    max_tokens: int = 2000,
    temperature: float = 0.0,
    presence_penalty: float = 0.0,
    parallel_tool_calls: bool = False,
    seed: int | None = None,
) -> tuple[str, int]:
    """Call LLM with tool calling support. Returns (text, api_calls).

    Parameters tuned per SDK docs (see docs/SDK_REFERENCE.md):
    - DeepSeek: temperature=0.0 (official for coding), no parallel_tool_calls
    - Qwen: temperature=0.1, parallel_tool_calls=True, seed for reproducibility
    """
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
            if func_name == "mcp_list_project_structure":
                result_data = json.loads(result_json)
                if result_data.get("success"):
                    tool_result(func_name, format_tree(result_data["structure"]))
                else:
                    tool_result(func_name, result_data.get("error", "Error"))
            elif func_name == "mcp_read_project_file":
                result_data = json.loads(result_json)
                if result_data.get("success"):
                    lines = result_data["content"].split("\n")
                    preview = "\n".join(lines[:30])
                    showing = result_data.get("showing_lines", "?")
                    total = result_data.get("total_lines", "?")
                    has_more = result_data.get("has_more", False)
                    size = result_data.get("size_kb", "?")
                    if len(lines) > 30:
                        preview += f"\n... (+{len(lines) - 30} more in this chunk)"
                    extra = f" [MORE AVAILABLE from line {result_data.get('next_start_line')}]" if has_more else ""
                    tool_result(
                        f"read {func_args.get('file_path', '?')} lines {showing}/{total} ({size}KB){extra}",
                        preview,
                    )
                else:
                    tool_result(func_name, result_data.get("error", "Error"))

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_json[:6000],
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
    max_tokens: int = 1500,
    temperature: float = 0.0,
    presence_penalty: float = 0.0,
) -> tuple[str, int]:
    """Simple LLM call without tools.

    Parameters tuned per SDK docs (see docs/SDK_REFERENCE.md).
    """
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


# ─── Main ─────────────────────────────────────────────────────────────────
async def main():
    if not DS_KEY or not QW_KEY:
        print("Set DEEPSEEK_API_KEY and QWEN_API_KEY in .env")
        sys.exit(1)

    # ── System prompts with project brief ─────────────────────────────
    AUDITOR_SYSTEM = f"""You are Agent-Auditor, a senior Python code auditor specializing in trading systems.

{PROJECT_BRIEF}

YOUR TASK: Find REAL, SPECIFIC code issues in this project.

HOW TO USE TOOLS EFFICIENTLY:
- Read the FIRST 100 lines of a file for class/function overview
- Then jump to SPECIFIC line ranges where you suspect issues
- Do NOT read entire 2000+ line files sequentially!
- Example: read lines 1-100, then lines 800-1000 where the main loop is

WHAT TO LOOK FOR:
- Division by zero without guards
- Missing edge cases (empty dataframe, NaN values, zero volume)
- Variables assigned but never used
- Incorrect math formulas
- Missing error handling in critical paths

OUTPUT FORMAT (STRICT):
For each issue:
```
ISSUE #N [SEVERITY]: Title
FILE: path/to/file.py, lines X-Y
PROBLEM: What is wrong (1-2 sentences)
IMPACT: What can break (1 sentence)
```

RULES:
- Find 3-5 issues maximum
- Do NOT suggest cosmetic changes (formatting, naming, comments)
- Do NOT suggest changing commission_rate
- After reading code, STOP calling tools and write your findings
- Respond in Russian. Maximum 400 words.
"""

    FIXER_SYSTEM = f"""You are Agent-Fixer, a senior Python developer who writes precise code fixes.

{PROJECT_BRIEF}

YOUR TASK: Take the issues found by the Auditor and write CONCRETE fixes.

HOW TO USE TOOLS:
- Read ONLY the specific lines mentioned by the Auditor (use start_line parameter)
- Read 50-100 lines around the problematic area, not the whole file
- After reading, STOP calling tools and write the fix

OUTPUT FORMAT (STRICT):
For each fix:
```
FIX #N: Title
FILE: path/to/file.py
BEFORE (exact current code):
... (copy exact lines from the file)
AFTER (fixed code):
... (your fix, minimal changes)
WHY: Brief explanation
```

RULES:
- Fixes must be minimal — change as few lines as possible
- Do NOT break existing tests
- Do NOT change commission_rate or other critical constants
- After reading the relevant code sections, WRITE the fixes immediately
- Do NOT read more files after you have enough context
- Respond in Russian. Maximum 500 words.
"""

    header("SELF-IMPROVEMENT SESSION")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Auditor: DeepSeek {DS_MODEL} (temp={DS_TEMPERATURE})")
    print(f"  Fixer:   Qwen {QW_MODEL} (temp={QW_TEMPERATURE}, Singapore)")
    print(f"  Project: {PROJECT_ROOT.name} (517 .py files, 135 tests)")
    print()

    total_start = time.time()
    total_api_calls = 0

    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # ── Pre-flight connectivity check ─────────────────────────
        system_msg("Checking API connectivity...")
        for name, url, key in [
            ("DeepSeek", DS_URL, DS_KEY),
            ("Qwen", QW_URL, QW_KEY),
        ]:
            for attempt in range(3):
                try:
                    test_payload = {
                        "model": DS_MODEL if "deepseek" in url else QW_MODEL,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                    }
                    test_headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    async with session.post(url, json=test_payload, headers=test_headers) as resp:
                        if resp.status == 200:
                            system_msg(f"  {name}: OK (status {resp.status})")
                            break
                        else:
                            system_msg(f"  {name}: status {resp.status}, retry {attempt + 1}/3...")
                except Exception as e:
                    system_msg(f"  {name}: connection error ({type(e).__name__}), retry {attempt + 1}/3...")
                    await asyncio.sleep(3)
            else:
                print(f"\n  FATAL: Cannot connect to {name} after 3 attempts. Check network.")
                sys.exit(1)

        print()

        # ═════════════════════════════════════════════════════════════
        # PHASE 1: Auditor reads code and finds issues
        # ═════════════════════════════════════════════════════════════
        header("PHASE 1: AUDIT (DeepSeek reads code, finds real issues)")

        system_msg("DeepSeek starts code audit with tool access...")
        print()

        audit_task = (
            "Проведи аудит ОДНОГО критического файла: backend/backtesting/engines/fallback_engine_v4.py\n\n"
            "СТРАТЕГИЯ ЧТЕНИЯ (следуй ей!):\n"
            "1. Прочитай строки 1-100 — импорты, классы, общая структура\n"
            "2. Прочитай строки 700-900 — начало run() метода, инициализация\n"
            "3. Прочитай строки 1300-1500 — основной цикл обработки баров\n"
            "4. СТОП! Не читай больше. Напиши 3-5 найденных проблем.\n\n"
            "Ищи: division by zero, необработанные NaN/пустые данные, неиспользуемые переменные, "
            "ошибки в формулах, пропущенную обработку ошибок.\n"
            "НЕ предлагай косметику — только реальные баги и edge cases."
        )

        audit_response, calls = await call_llm_with_tools(
            session,
            DS_URL,
            DS_KEY,
            DS_MODEL,
            AUDITOR_SYSTEM,
            [{"role": "user", "content": audit_task}],
            tools=TOOLS_SPEC,
            max_tool_rounds=8,
            max_tokens=4000,
            temperature=DS_TEMPERATURE,
            presence_penalty=0.3,
        )
        total_api_calls += calls

        agent_says("AUDITOR (DeepSeek) — Found Issues", C_DS, audit_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 2: Fixer reads issues + code, writes fixes
        # ═════════════════════════════════════════════════════════════
        header("PHASE 2: FIX (Qwen reads issues + code, writes patches)")

        system_msg("Qwen reads auditor findings and actual code to write fixes...")
        print()

        fix_task = (
            f"Аудитор нашёл следующие проблемы:\n\n"
            f"---\n{audit_response[:3000]}\n---\n\n"
            f"Твоя задача:\n"
            f"1. Прочитай ТОЛЬКО конкретные строки, указанные аудитором (используй start_line)\n"
            f"2. Читай по 50-100 строк вокруг проблемного места, НЕ весь файл\n"
            f"3. Максимум 2-3 вызова tool, потом ПИШИ fix\n"
            f"4. Для КАЖДОЙ проблемы напиши:\n"
            f"   - Файл и строки\n"
            f"   - BEFORE: точный код сейчас (скопируй из файла)\n"
            f"   - AFTER: исправленный код\n"
            f"   - Почему это исправляет проблему\n"
            f"5. Начни с самой критичной проблемы."
        )

        fix_response, calls = await call_llm_with_tools(
            session,
            QW_URL,
            QW_KEY,
            QW_MODEL,
            FIXER_SYSTEM,
            [{"role": "user", "content": fix_task}],
            tools=TOOLS_SPEC,
            max_tool_rounds=6,
            max_tokens=4000,
            temperature=QW_TEMPERATURE,
            parallel_tool_calls=True,
            seed=42,
        )
        total_api_calls += calls

        agent_says("FIXER (Qwen) — Proposed Fixes", C_QW, fix_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 3: Auditor reviews fixes, final verdict
        # ═════════════════════════════════════════════════════════════
        header("PHASE 3: REVIEW (DeepSeek reviews proposed fixes)")

        system_msg("DeepSeek reviews Qwen's proposed fixes...")

        review_task = (
            f"Fixer (Qwen) предложил такие исправления:\n\n"
            f"---\n{fix_response[:3000]}\n---\n\n"
            f"Твои оригинальные находки были:\n\n"
            f"---\n{audit_response[:2000]}\n---\n\n"
            f"Оцени каждый fix:\n"
            f"- APPROVE — fix корректен, можно применять\n"
            f"- REJECT — fix неверен или сломает что-то\n"
            f"- MODIFY — идея верная, но нужно доработать\n\n"
            f"Для каждого fix укажи свой вердикт и почему. "
            f"В конце дай итоговый SCORE: сколько из предложенных fixes безопасно применять."
        )

        review_response, calls = await call_llm_simple(
            session,
            DS_URL,
            DS_KEY,
            DS_MODEL,
            AUDITOR_SYSTEM,
            review_task,
            max_tokens=2000,
            temperature=DS_TEMPERATURE,
            presence_penalty=0.3,
        )
        total_api_calls += calls

        agent_says("AUDITOR (DeepSeek) — Fix Review", C_DS, review_response)

        # ═════════════════════════════════════════════════════════════
        # PHASE 4: Fixer's final response
        # ═════════════════════════════════════════════════════════════
        header("PHASE 4: FINAL PLAN (Qwen responds + action items)")

        system_msg("Qwen responds to review and creates final plan...")

        final_task = (
            f"Аудитор оценил твои fixes:\n\n"
            f"---\n{review_response[:2000]}\n---\n\n"
            f"Составь ФИНАЛЬНЫЙ ПЛАН:\n"
            f"1. Какие fixes принимаешь (APPROVED)\n"
            f"2. Какие доработаешь (MODIFY) — покажи обновлённый код\n"
            f"3. С какими отказами согласен (REJECTED)\n"
            f"4. TOP-3 действия в порядке приоритета\n\n"
            f"Будь кратким. Максимум 250 слов."
        )

        final_response, calls = await call_llm_simple(
            session,
            QW_URL,
            QW_KEY,
            QW_MODEL,
            FIXER_SYSTEM,
            final_task,
            max_tokens=1200,
            temperature=QW_TEMPERATURE,
        )
        total_api_calls += calls

        agent_says("FIXER (Qwen) — Final Plan", C_QW, final_response)

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.time() - total_start
    header("SESSION COMPLETE")
    print(f"  Time:      {elapsed:.1f}s")
    print(f"  API calls: {total_api_calls}")
    print(f"  Auditor:   DeepSeek {DS_MODEL} (audit + review, temp={DS_TEMPERATURE})")
    print(f"  Fixer:     Qwen {QW_MODEL} (fixes + final plan, temp={QW_TEMPERATURE})")
    print(f"  Project:   {PROJECT_ROOT.name}")
    print()
    print("  Workflow:  AUDIT -> FIX -> REVIEW -> FINAL PLAN")
    print("  Result:    Concrete fixes with approve/reject verdicts")
    print()


if __name__ == "__main__":
    asyncio.run(main())
