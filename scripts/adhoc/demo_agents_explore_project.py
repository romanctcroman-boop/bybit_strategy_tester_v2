"""
🔍 LIVE DEMO: AI Agents Explore Project Structure

DeepSeek и Qwen получают реальный tool calling:
  - mcp_list_project_structure → дерево каталогов
  - mcp_read_project_file     → чтение файлов

Сценарий:
  1. Агент-Архитектор (DeepSeek) запрашивает структуру проекта через tool
  2. Агент-Ревьюер (Qwen) читает ключевые файлы через tool
  3. Оба обсуждают архитектуру, находят сильные/слабые стороны

Запуск:
  .\.venv\Scripts\python.exe demo_agents_explore_project.py
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

PROJECT_ROOT = Path(__file__).parent.resolve()

# ─── Colors ───────────────────────────────────────────────────────────────
C_DS = "\033[96m"  # Cyan — DeepSeek
C_QW = "\033[93m"  # Yellow — Qwen
C_TOOL = "\033[92m"  # Green — tool results
C_SYS = "\033[90m"  # Grey — system
C_HDR = "\033[95m"  # Magenta — headers
C_R = "\033[0m"  # Reset


def header(text: str):
    print(f"\n{C_HDR}{'═' * 70}")
    print(f"  {text}")
    print(f"{'═' * 70}{C_R}\n")


def agent_says(name: str, color: str, text: str):
    print(f"{color}┌─ {name} ─────────────────────────────────────────")
    for line in text.strip().split("\n"):
        print(f"│ {line}")
    print(f"└{'─' * 60}{C_R}\n")


def tool_result(name: str, result_text: str):
    lines = result_text.strip().split("\n")
    preview = lines[:30]
    print(f"{C_TOOL}  🔧 Tool: {name}")
    for line in preview:
        print(f"  │ {line}")
    if len(lines) > 30:
        print(f"  │ ... (+{len(lines) - 30} more lines)")
    print(f"  └{'─' * 50}{C_R}\n")


def system_msg(text: str):
    print(f"{C_SYS}  ⚙ {text}{C_R}")


# ─── Local Tool Implementations ──────────────────────────────────────────
def local_list_project_structure(directory: str = ".", max_depth: int = 3) -> dict:
    """List project structure locally (no server needed)."""
    target = (PROJECT_ROOT / directory).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        return {"success": False, "error": "Path outside project"}

    blocked = {
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
    blocked_prefixes = ("test_e2e_test_", "test_eval_test_", "test_memory_test_")

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
                    if child.name in blocked:
                        continue
                    if any(child.name.startswith(p) for p in blocked_prefixes):
                        continue
                    children.append(build_tree(child, depth + 1))
            except PermissionError:
                pass
            result["children"] = children
        return result

    tree = build_tree(target)
    return {"success": True, "structure": tree}


def local_read_project_file(file_path: str, max_size_kb: int = 50) -> dict:
    """Read a project file locally (no server needed)."""
    target = (PROJECT_ROOT / file_path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        return {"success": False, "error": "Path outside project"}
    if not target.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    size = target.stat().st_size
    if size > max_size_kb * 1024:
        return {"success": False, "error": f"File too large: {size // 1024}KB"}

    blocked_names = {".env", "server.key", "server.crt"}
    if target.name in blocked_names:
        return {"success": False, "error": f"Blocked file: {target.name}"}

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "success": True,
        "content": content,
        "file_path": file_path,
        "lines": len(content.splitlines()),
        "size_kb": size // 1024,
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
            args.get("file_path", ""),
            args.get("max_size_kb", 50),
        )
    else:
        result = {"success": False, "error": f"Unknown tool: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


def format_tree(node: dict, prefix: str = "", is_last: bool = True) -> str:
    """Format tree structure for display."""
    connector = "└── " if is_last else "├── "
    name = node.get("name", "?")
    ntype = node.get("type", "file")
    line = f"{prefix}{connector}{name}/" if ntype == "dir" else f"{prefix}{connector}{name}"
    lines = [line]

    children = node.get("children", [])
    for i, child in enumerate(children):
        extension = "    " if is_last else "│   "
        lines.append(format_tree(child, prefix + extension, i == len(children) - 1))

    return "\n".join(lines)


# ─── Tool-aware LLM Call ─────────────────────────────────────────────────
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "mcp_list_project_structure",
            "description": "List directory structure of the project. Returns a tree of files and folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative path from project root (default: '.')",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "How deep to traverse (default: 2)",
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
            "description": "Read a file from the project. Returns file content as string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to file (e.g. 'backend/api/app.py')",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
]


async def call_llm_with_tools(
    session: aiohttp.ClientSession,
    url: str,
    key: str,
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tool_rounds: int = 3,
) -> tuple[str, int]:
    """
    Call LLM with tool calling support. Handles multi-round tool use.
    Returns (final_text, total_api_calls).
    """
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    conversation = [{"role": "system", "content": system}] + messages
    total_calls = 0

    for round_num in range(max_tool_rounds + 1):
        payload = {
            "model": model,
            "messages": conversation,
            "max_tokens": 1500,
            "temperature": 0.7,
        }
        if tools and round_num < max_tool_rounds:
            payload["tools"] = tools

        async with session.post(url, json=payload, headers=headers) as resp:
            total_calls += 1
            if resp.status != 200:
                error = await resp.text()
                return f"[API Error {resp.status}]: {error[:200]}", total_calls

            data = await resp.json()

        choice = data["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # No tool calls — this is the final response
            return message.get("content", ""), total_calls

        # Process tool calls
        conversation.append(message)  # Add assistant message with tool_calls

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            system_msg(f"Agent вызывает tool: {func_name}({json.dumps(func_args, ensure_ascii=False)})")

            # Execute tool
            result_json = execute_tool(func_name, func_args)

            # Show tree if it's a structure listing
            if func_name == "mcp_list_project_structure":
                result_data = json.loads(result_json)
                if result_data.get("success"):
                    tree_str = format_tree(result_data["structure"])
                    tool_result(func_name, tree_str)
                else:
                    tool_result(func_name, result_data.get("error", "Unknown error"))
            elif func_name == "mcp_read_project_file":
                result_data = json.loads(result_json)
                if result_data.get("success"):
                    content = result_data["content"]
                    lines = content.split("\n")
                    preview = "\n".join(lines[:25])
                    if len(lines) > 25:
                        preview += f"\n... (+{len(lines) - 25} more lines)"
                    tool_result(f"{func_name} → {func_args.get('file_path', '?')}", preview)
                else:
                    tool_result(func_name, result_data.get("error", "Unknown error"))

            # Add tool result to conversation
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_json[:4000],  # Truncate large results
                }
            )

    return "[Max tool rounds exceeded]", total_calls


# ─── Main Demo ────────────────────────────────────────────────────────────
async def main():
    if not DS_KEY or not QW_KEY:
        print("❌ Set DEEPSEEK_API_KEY and QWEN_API_KEY in .env")
        sys.exit(1)

    ARCHITECT_SYSTEM = (
        "You are Agent-Architect (DeepSeek), a senior software architect. "
        "You have access to tools that let you explore the project structure and read files. "
        "USE THE TOOLS to understand the project before making any claims. "
        "Start by calling mcp_list_project_structure to see what's in the project. "
        "Then read key files like pyproject.toml, main.py, or important modules. "
        "Be specific and factual. Respond in Russian."
    )

    REVIEWER_SYSTEM = (
        "You are Agent-Reviewer (Qwen), a code reviewer and quality expert. "
        "You have access to tools that let you explore the project structure and read files. "
        "USE THE TOOLS to read specific files and assess code quality. "
        "Focus on: architecture, code quality, testing coverage, documentation. "
        "Be critical but constructive. Respond in Russian."
    )

    header("🔍 AI Agents Explore Project Structure")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  DeepSeek: deepseek-chat (Architect)")
    print(f"  Qwen: qwen-flash (Reviewer, Singapore)")
    print(f"  Проект: {PROJECT_ROOT.name}")
    print()

    total_start = time.time()
    total_api_calls = 0

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # ── PHASE 1: Architect explores project ──────────────────────
        header("📁 PHASE 1: Architect (DeepSeek) исследует проект")

        system_msg("DeepSeek получает доступ к tools и начинает исследование...")
        print()

        architect_response, calls = await call_llm_with_tools(
            session,
            DS_URL,
            DS_KEY,
            "deepseek-chat",
            ARCHITECT_SYSTEM,
            [
                {
                    "role": "user",
                    "content": (
                        "Исследуй структуру этого проекта. Используй tool mcp_list_project_structure "
                        "чтобы увидеть каталоги, а затем mcp_read_project_file чтобы прочитать "
                        "pyproject.toml и backend/api/app.py (или другие ключевые файлы). "
                        "Затем дай краткое описание архитектуры проекта (максимум 300 слов)."
                    ),
                }
            ],
            tools=TOOLS_SPEC,
            max_tool_rounds=3,
        )
        total_api_calls += calls

        agent_says("🏗 Agent-Architect (DeepSeek)", C_DS, architect_response)

        # ── PHASE 2: Reviewer explores & reads code ──────────────────
        header("🔬 PHASE 2: Reviewer (Qwen) читает код и оценивает качество")

        system_msg("Qwen получает доступ к tools и начинает ревью кода...")
        print()

        reviewer_response, calls = await call_llm_with_tools(
            session,
            QW_URL,
            QW_KEY,
            "qwen-flash",
            REVIEWER_SYSTEM,
            [
                {
                    "role": "user",
                    "content": (
                        "Проведи ревью этого проекта. Используй tool mcp_list_project_structure "
                        "для обзора, потом mcp_read_project_file чтобы прочитать 2-3 ключевых файла "
                        "(например main.py, backend/backtesting/engines/ или тесты). "
                        "Оцени: архитектуру, качество кода, тестирование. "
                        "Дай оценку от 1 до 10 по каждому критерию. Максимум 300 слов."
                    ),
                }
            ],
            tools=TOOLS_SPEC,
            max_tool_rounds=3,
        )
        total_api_calls += calls

        agent_says("🔍 Agent-Reviewer (Qwen)", C_QW, reviewer_response)

        # ── PHASE 3: Discussion ──────────────────────────────────────
        header("💬 PHASE 3: Обсуждение между агентами")

        # Architect responds to reviewer's findings
        system_msg("DeepSeek отвечает на замечания Qwen...")
        discussion_prompt = (
            f"Ревьюер (Qwen) дал такую оценку проекта:\n\n"
            f"---\n{reviewer_response[:1500]}\n---\n\n"
            f"Твоя оценка архитектуры была:\n\n"
            f"---\n{architect_response[:1500]}\n---\n\n"
            f"Согласен ли ты с замечаниями ревьюера? "
            f"Что бы ты добавил или оспорил? Дай итоговые рекомендации (200 слов)."
        )

        # Simple call without tools for discussion
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": ARCHITECT_SYSTEM},
                {"role": "user", "content": discussion_prompt},
            ],
            "max_tokens": 1000,
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {DS_KEY}", "Content-Type": "application/json"}
        async with session.post(DS_URL, json=payload, headers=headers) as resp:
            total_api_calls += 1
            data = await resp.json()
            architect_reply = data["choices"][0]["message"]["content"]

        agent_says("🏗 Agent-Architect (DeepSeek) — Ответ", C_DS, architect_reply)

        # Reviewer's final word
        system_msg("Qwen даёт финальное заключение...")
        final_prompt = (
            f"Архитектор ответил на твои замечания:\n\n"
            f"---\n{architect_reply[:1500]}\n---\n\n"
            f"Дай финальное заключение: согласие/несогласие, TOP-3 приоритета для улучшения."
        )

        payload = {
            "model": "qwen-flash",
            "messages": [
                {"role": "system", "content": REVIEWER_SYSTEM},
                {"role": "user", "content": final_prompt},
            ],
            "max_tokens": 800,
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {QW_KEY}", "Content-Type": "application/json"}
        async with session.post(QW_URL, json=payload, headers=headers) as resp:
            total_api_calls += 1
            data = await resp.json()
            reviewer_final = data["choices"][0]["message"]["content"]

        agent_says("🔍 Agent-Reviewer (Qwen) — Финал", C_QW, reviewer_final)

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.time() - total_start
    header("📊 ИТОГИ")
    print(f"  ⏱  Время: {elapsed:.1f}s")
    print(f"  📡 API вызовов: {total_api_calls}")
    print(f"  🏗  DeepSeek: deepseek-chat (Architect + tool calling)")
    print(f"  🔍  Qwen: qwen-flash (Reviewer + tool calling)")
    print(f"  📁  Проект: {PROJECT_ROOT.name}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
