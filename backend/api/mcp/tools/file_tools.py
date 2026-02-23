"""
MCP File Access Tools

Provides secure, sandboxed file access for MCP tools.
Extracted from app.py for better modularity.
"""

import logging
import subprocess
import time
from pathlib import Path

# Try to import metrics
try:
    from backend.monitoring.phase5_collector import (
        MCP_TOOL_CALLS,
        MCP_TOOL_DURATION,
        MCP_TOOL_ERRORS,
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    MCP_TOOL_CALLS = None
    MCP_TOOL_DURATION = None
    MCP_TOOL_ERRORS = None

logger = logging.getLogger(__name__)

# Security: blocked file patterns
BLOCKED_PATTERNS = [
    ".env",
    ".git",
    "secrets",
    "credentials",
    ".key",
    ".pem",
    "password",
]

# Project root (resolved once)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _update_metrics(tool: str, success: bool, duration: float, error_type: str | None = None):
    """Update Prometheus metrics if available."""
    if not _METRICS_AVAILABLE:
        return
    try:
        MCP_TOOL_CALLS.labels(tool=tool, success=str(success).lower()).inc()
        MCP_TOOL_DURATION.labels(tool=tool).observe(duration)
        if error_type:
            MCP_TOOL_ERRORS.labels(tool=tool, error_type=error_type).inc()
    except Exception as e:
        logger.warning(f"Failed to update metrics: {e}")


def _is_path_safe(target_path: Path, project_root: Path) -> tuple[bool, str]:
    """
    Check if path is safe to access.

    Returns:
        tuple of (is_safe, error_message)
    """
    # Security: ensure within project root
    if not str(target_path).startswith(str(project_root)):
        return False, "Path traversal detected: file must be within project root"

    # Security: block sensitive files
    path_lower = str(target_path).lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in path_lower:
            return False, f"Access denied: sensitive file pattern '{pattern}' detected"

    return True, ""


async def read_project_file(file_path: str, max_size_kb: int = 100) -> dict:
    """
    Securely read project files (read-only, sandboxed).

    Args:
        file_path: Relative path from project root (e.g., "backend/api/app.py")
        max_size_kb: Maximum file size to read (default 100KB for safety)

    Returns:
        dict with success, content, metadata

    Security:
        - Only allows reading files within project root
        - Blocks access to .env, .git, secrets
        - Enforces file size limits
    """
    start_time = time.perf_counter()

    try:
        target_path = (PROJECT_ROOT / file_path).resolve()

        # Security check
        is_safe, error = _is_path_safe(target_path, PROJECT_ROOT)
        if not is_safe:
            return {"success": False, "error": error, "file_path": file_path}

        # Check file exists
        if not target_path.exists():
            return {"success": False, "error": "File not found", "file_path": file_path}

        # Check file size
        file_size = target_path.stat().st_size
        max_size_bytes = max_size_kb * 1024
        if file_size > max_size_bytes:
            return {
                "success": False,
                "error": f"File too large: {file_size} bytes (max {max_size_bytes})",
                "file_path": file_path,
                "file_size_kb": file_size // 1024,
            }

        # Read file content
        with open(target_path, encoding="utf-8") as f:
            content = f.read()

        duration = time.perf_counter() - start_time
        _update_metrics("read_project_file", True, duration)

        return {
            "success": True,
            "content": content,
            "file_path": file_path,
            "absolute_path": str(target_path),
            "file_size_kb": file_size // 1024,
            "lines": len(content.splitlines()),
            "encoding": "utf-8",
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP read_project_file error: {e}")
        _update_metrics("read_project_file", False, duration, type(e).__name__)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": file_path,
        }


async def list_project_structure(
    directory: str = ".", max_depth: int = 3, include_hidden: bool = False
) -> dict:
    """
    List project directory structure (read-only navigation).

    Args:
        directory: Relative path from project root (default "." for root)
        max_depth: Maximum recursion depth (default 3 for safety)
        include_hidden: Include hidden files/folders (default False)

    Returns:
        dict with success, structure (tree), file_count, dir_count

    Security:
        - Read-only access within project root
        - Depth limit to prevent resource exhaustion
        - Blocks .git, .env, node_modules by default
    """
    start_time = time.perf_counter()

    try:
        target_dir = (PROJECT_ROOT / directory).resolve()

        # Security check
        is_safe, error = _is_path_safe(target_dir, PROJECT_ROOT)
        if not is_safe:
            return {"success": False, "error": error, "directory": directory}

        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "success": False,
                "error": "Directory not found or not a directory",
                "directory": directory,
            }

        # Blocked directories
        blocked_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
        }

        def build_tree(path: Path, depth: int = 0) -> dict:
            if depth > max_depth:
                return {"name": path.name, "type": "directory", "truncated": True}

            result = {
                "name": path.name,
                "type": "directory" if path.is_dir() else "file",
                "relative_path": str(path.relative_to(PROJECT_ROOT)),
            }

            if path.is_file():
                result["size_kb"] = path.stat().st_size // 1024
                return result

            # List directory contents
            children = []
            try:
                for item in sorted(path.iterdir()):
                    # Skip hidden unless requested
                    if not include_hidden and item.name.startswith("."):
                        continue
                    # Skip blocked directories
                    if item.is_dir() and item.name in blocked_dirs:
                        continue
                    children.append(build_tree(item, depth + 1))
            except PermissionError:
                result["error"] = "Permission denied"

            result["children"] = children
            return result

        structure = build_tree(target_dir)

        # Count items
        def count_items(node: dict) -> tuple[int, int]:
            files = 0
            dirs = 0
            if node.get("type") == "file":
                files = 1
            else:
                dirs = 1
                for child in node.get("children", []):
                    f, d = count_items(child)
                    files += f
                    dirs += d
            return files, dirs

        file_count, dir_count = count_items(structure)

        duration = time.perf_counter() - start_time
        _update_metrics("list_project_structure", True, duration)

        return {
            "success": True,
            "directory": directory,
            "structure": structure,
            "file_count": file_count,
            "dir_count": dir_count,
            "max_depth": max_depth,
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP list_project_structure error: {e}")
        _update_metrics("list_project_structure", False, duration, type(e).__name__)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "directory": directory,
        }


async def analyze_code_quality(file_path: str, tools: list[str] | None = None) -> dict:
    """
    Analyze code quality using Ruff, Black, Bandit.

    Args:
        file_path: Relative path to Python file (e.g., "backend/api/app.py")
        tools: List of tools to run (default: ["ruff", "black", "bandit"])

    Returns:
        dict with success, results per tool, summary statistics

    Note:
        Requires ruff, black, bandit installed in environment
    """
    start_time = time.perf_counter()

    if tools is None:
        tools = ["ruff", "black", "bandit"]

    try:
        target_path = (PROJECT_ROOT / file_path).resolve()

        # Security check
        is_safe, error = _is_path_safe(target_path, PROJECT_ROOT)
        if not is_safe:
            return {"success": False, "error": error, "file_path": file_path}

        if not target_path.exists():
            return {"success": False, "error": "File not found", "file_path": file_path}

        if not str(target_path).endswith(".py"):
            return {
                "success": False,
                "error": "Only Python files supported",
                "file_path": file_path,
            }

        results = {}

        # Ruff (linting)
        if "ruff" in tools:
            try:
                proc = subprocess.run(
                    ["ruff", "check", str(target_path), "--output-format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                import json

                try:
                    issues = json.loads(proc.stdout) if proc.stdout else []
                except json.JSONDecodeError:
                    issues = []
                results["ruff"] = {
                    "success": proc.returncode == 0,
                    "issues": issues,
                    "issue_count": len(issues),
                }
            except FileNotFoundError:
                results["ruff"] = {"success": False, "error": "ruff not installed"}
            except subprocess.TimeoutExpired:
                results["ruff"] = {"success": False, "error": "timeout"}

        # Black (formatting)
        if "black" in tools:
            try:
                proc = subprocess.run(
                    ["black", "--check", "--diff", str(target_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                results["black"] = {
                    "success": proc.returncode == 0,
                    "formatted": proc.returncode == 0,
                    "diff": proc.stdout if proc.returncode != 0 else None,
                }
            except FileNotFoundError:
                results["black"] = {"success": False, "error": "black not installed"}
            except subprocess.TimeoutExpired:
                results["black"] = {"success": False, "error": "timeout"}

        # Bandit (security)
        if "bandit" in tools:
            try:
                proc = subprocess.run(
                    ["bandit", "-f", "json", str(target_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                import json

                try:
                    bandit_result = json.loads(proc.stdout) if proc.stdout else {}
                    issues = bandit_result.get("results", [])
                except json.JSONDecodeError:
                    issues = []
                results["bandit"] = {
                    "success": len(issues) == 0,
                    "issues": issues,
                    "issue_count": len(issues),
                }
            except FileNotFoundError:
                results["bandit"] = {"success": False, "error": "bandit not installed"}
            except subprocess.TimeoutExpired:
                results["bandit"] = {"success": False, "error": "timeout"}

        # Summary
        all_passed = all(r.get("success", False) for r in results.values())
        total_issues = sum(r.get("issue_count", 0) for r in results.values())

        duration = time.perf_counter() - start_time
        _update_metrics("analyze_code_quality", True, duration)

        return {
            "success": True,
            "file_path": file_path,
            "results": results,
            "all_passed": all_passed,
            "total_issues": total_issues,
            "tools_run": list(results.keys()),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"MCP analyze_code_quality error: {e}")
        _update_metrics("analyze_code_quality", False, duration, type(e).__name__)
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "file_path": file_path,
        }


def register_file_tools(mcp):
    """
    Register all file tools with the MCP server.

    Args:
        mcp: The MCP server instance (FastMCP or _DummyMCP)
    """

    @mcp.tool()
    async def mcp_read_project_file(file_path: str, max_size_kb: int = 100) -> dict:
        """Securely read project files (read-only, sandboxed)"""
        return await read_project_file(file_path, max_size_kb)

    @mcp.tool()
    async def mcp_list_project_structure(
        directory: str = ".", max_depth: int = 3, include_hidden: bool = False
    ) -> dict:
        """List project directory structure (read-only navigation)"""
        return await list_project_structure(directory, max_depth, include_hidden)

    @mcp.tool()
    async def mcp_analyze_code_quality(file_path: str, tools: list | None = None) -> dict:
        """Analyze code quality using Ruff, Black, Bandit"""
        return await analyze_code_quality(file_path, tools)

    logger.info("✅ MCP File tools registered")


__all__ = [
    "analyze_code_quality",
    "list_project_structure",
    "read_project_file",
    "register_file_tools",
]
