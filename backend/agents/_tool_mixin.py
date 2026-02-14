"""
Tool Execution Mixin for UnifiedAgentInterface

Extracted from unified_agent_interface.py to reduce file size.
Contains: MCP tool execution, local tool emulation, retry logic.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger


class ToolMixin:
    """Mixin providing MCP / local tool execution with retry."""

    # ------------------------------------------------------------------
    # Retry wrapper
    # ------------------------------------------------------------------

    async def _execute_tool_with_retry(self, tool_call: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        """
        Execute MCP tool call with exponential backoff retry.

        Args:
            tool_call: Tool call from DeepSeek API
            max_retries: Maximum number of retry attempts

        Returns:
            Tool result dict with success/error
        """
        function_name = tool_call.get("function", {}).get("name", "unknown")
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self._execute_mcp_tool(tool_call)

                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"🔄 Tool {function_name} succeeded on attempt {attempt + 1}")
                    return result

                error_msg = result.get("error", "")
                retryable_errors = [
                    "timeout",
                    "connection",
                    "rate limit",
                    "temporary",
                    "503",
                    "502",
                    "500",
                ]
                is_retryable = any(err.lower() in error_msg.lower() for err in retryable_errors)

                if not is_retryable or attempt >= max_retries:
                    return result

                last_error = error_msg

            except Exception as e:
                last_error = str(e)
                if attempt >= max_retries:
                    logger.error(f"❌ Tool {function_name} failed after {max_retries + 1} attempts: {e}")
                    return {
                        "success": False,
                        "error": f"Tool failed after {max_retries + 1} attempts: {last_error}",
                    }

            delay = 2**attempt
            logger.warning(
                f"⏳ Tool {function_name} failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay}s... Error: {last_error}"
            )
            await asyncio.sleep(delay)

        return {
            "success": False,
            "error": f"Tool failed after {max_retries + 1} attempts: {last_error}",
        }

    # ------------------------------------------------------------------
    # MCP tool execution
    # ------------------------------------------------------------------

    async def _execute_mcp_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """
        Выполнить MCP tool call

        Args:
            tool_call: Tool call от DeepSeek API

        Returns:
            Tool result dict
        """
        function_name = None
        try:
            function_name = tool_call.get("function", {}).get("name")
            arguments_str = tool_call.get("function", {}).get("arguments", "{}")

            logger.info(f"🔧 Executing tool: {function_name}")
            logger.debug(f"   Arguments (raw): {arguments_str}")

            # Parse arguments
            if isinstance(arguments_str, str):
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse tool arguments: {e}")
                    return {
                        "success": False,
                        "error": f"Invalid tool arguments JSON: {e!s}",
                    }
            else:
                arguments = arguments_str

            logger.debug(f"   Arguments (parsed): {arguments}")

            # If MCP disabled → local emulation
            if self.mcp_disabled:
                logger.debug("🧩 MCP disabled: executing tool via local emulation layer")
                return await self._execute_local_tool(function_name, arguments)

            # Normal path: import real MCP tool implementations
            try:
                from backend.api.app import (
                    mcp_analyze_code_quality,
                    mcp_list_project_structure,
                    mcp_read_project_file,
                )

                logger.debug("✅ MCP tools imported successfully")
            except ImportError as e:
                logger.error(f"❌ Failed to import MCP tools: {e}")
                return {
                    "success": False,
                    "error": f"Failed to import MCP tools: {e!s}",
                }

            tool_map = {
                "mcp_read_project_file": mcp_read_project_file,
                "mcp_list_project_structure": mcp_list_project_structure,
                "mcp_analyze_code_quality": mcp_analyze_code_quality,
            }

            if function_name not in tool_map:
                logger.error(f"❌ Unknown tool: {function_name}")
                return {"success": False, "error": f"Unknown tool: {function_name}"}

            tool_func = tool_map[function_name]

            try:
                result = await tool_func(**arguments)
            except TypeError as e:
                if "not callable" in str(e):
                    logger.warning("   Tool is wrapped, trying .fn attribute")
                    actual_func = getattr(tool_func, "fn", None)
                    if actual_func:
                        result = await actual_func(**arguments)
                    else:
                        raise
                else:
                    raise

            logger.info(f"✅ Tool executed: {function_name} -> success={result.get('success')}")
            if not result.get("success"):
                logger.warning(f"   Tool returned error: {result.get('error')}")
            return result

        except Exception as e:
            logger.error(f"❌ Tool execution failed for {function_name}: {e}")
            import traceback

            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            return {"success": False, "error": f"Tool execution error: {e!s}"}

    # ------------------------------------------------------------------
    # Local tool emulation (MCP-disabled mode)
    # ------------------------------------------------------------------

    async def _execute_local_tool(self, function_name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        """Local emulation for MCP tools when autonomy mode disables MCP bridge.

        🔐 SECURITY: Implements path traversal protection per consensus proposal (99% approval).
        """
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent

        if not function_name:
            return {"success": False, "error": "No tool name provided"}

        if function_name == "mcp_read_project_file":
            return await self._local_read_file(project_root, arguments)

        if function_name == "mcp_list_project_structure":
            return self._local_list_structure(project_root, arguments)

        if function_name == "mcp_analyze_code_quality":
            return self._local_analyze_quality(project_root, arguments)

        return {
            "success": False,
            "error": f"Unknown tool (local mode): {function_name}",
        }

    # -- helpers for local tools --

    @staticmethod
    async def _local_read_file(project_root, arguments: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        rel_path = arguments.get("file_path", "")
        max_size_kb = int(arguments.get("max_size_kb", 100))
        if not rel_path:
            return {"success": False, "error": "file_path required"}

        rel_path = Path(rel_path).as_posix()
        if ".." in rel_path or rel_path.startswith("/"):
            logger.warning(f"🚫 Path traversal attempt blocked: {rel_path}")
            return {
                "success": False,
                "error": "Path traversal blocked: '..' and absolute paths not allowed",
            }

        target = (project_root / rel_path).resolve()
        if not target.is_relative_to(project_root):
            return {"success": False, "error": "Access outside project directory denied"}

        blocked_patterns = [".env", ".git", "secrets", "*.key", "*.pem", "id_rsa", "*.crt"]
        if any(target.match(pattern) for pattern in blocked_patterns):
            return {"success": False, "error": f"Access to sensitive file '{target.name}' denied"}

        if not target.exists() or not target.is_file():
            return {"success": False, "error": f"File not found: {rel_path}"}

        try:
            size_kb = target.stat().st_size / 1024.0
            if size_kb > max_size_kb:
                return {"success": False, "error": f"File too large ({size_kb:.1f}KB > {max_size_kb}KB)"}
            text = target.read_text(encoding="utf-8", errors="ignore")
            return {
                "success": True,
                "file_path": rel_path,
                "content": text,
                "size_kb": round(size_kb, 2),
                "source": "local_emulation",
            }
        except Exception as e:
            return {"success": False, "error": f"Read error: {e}"}

    @staticmethod
    def _local_list_structure(project_root, arguments: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        directory = arguments.get("directory", ".")
        max_depth = int(arguments.get("max_depth", 3))
        include_hidden = bool(arguments.get("include_hidden", False))
        base = (project_root / directory).resolve()
        if not base.exists() or not base.is_dir():
            return {"success": False, "error": f"Directory not found: {directory}"}

        MAX_ENTRIES_PER_DIR = 1000
        MAX_TOTAL_FILES = 10000
        file_count = [0]
        truncation_markers: list[str] = []

        def walk(path: Path, depth: int):
            if depth > max_depth or file_count[0] > MAX_TOTAL_FILES:
                return None
            entries = []
            for idx, child in enumerate(sorted(path.iterdir())):
                if idx >= MAX_ENTRIES_PER_DIR:
                    entries.append({"type": "truncated", "message": f"Truncated (>{MAX_ENTRIES_PER_DIR} entries)"})
                    truncation_markers.append(
                        f"Directory '{path.relative_to(base)}' truncated at {MAX_ENTRIES_PER_DIR} entries"
                    )
                    break

                name = child.name
                if not include_hidden and name.startswith("."):
                    continue
                if name in {".git", "__pycache__", "node_modules"}:
                    continue

                file_count[0] += 1
                if file_count[0] > MAX_TOTAL_FILES:
                    entries.append({"type": "truncated", "message": f"Max total files reached ({MAX_TOTAL_FILES})"})
                    truncation_markers.append(f"Max total files reached ({MAX_TOTAL_FILES})")
                    break

                if child.is_dir():
                    entries.append({"type": "dir", "name": name, "children": walk(child, depth + 1)})
                else:
                    entries.append({"type": "file", "name": name, "size": child.stat().st_size})
            return entries

        tree = {directory: walk(base, 0)}
        result = {
            "success": True,
            "structure": tree,
            "source": "local_emulation",
            "files_scanned": file_count[0],
        }
        if truncation_markers:
            result["truncation_info"] = truncation_markers
        return result

    @staticmethod
    def _local_analyze_quality(project_root, arguments: dict[str, Any]) -> dict[str, Any]:
        fp = arguments.get("file_path")
        if not fp:
            return {"success": False, "error": "file_path required"}
        target = project_root / fp
        if not target.exists():
            return {"success": False, "error": f"File not found: {fp}"}
        code = target.read_text(encoding="utf-8", errors="ignore")
        lines = code.splitlines()
        todo_count = sum(1 for line in lines if "TODO" in line or "FIXME" in line)
        long_lines = sum(1 for line in lines if len(line) > 120)
        score = max(0, 100 - (todo_count * 2 + long_lines))
        report = (
            f"Code Quality (local heuristic)\n"
            f"Lines: {len(lines)}\n"
            f"TODO/FIXME: {todo_count}\n"
            f"Long lines (>120c): {long_lines}\n"
            f"Heuristic score: {score}/100"
        )
        return {"success": True, "report": report, "source": "local_emulation"}
