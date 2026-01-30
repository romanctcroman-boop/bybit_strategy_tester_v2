"""
File Operations Router.

Provides endpoints for file management operations:
- Upload/download backtest results
- Export data to CSV/JSON
- Manage user files

TODO: Implement actual file operations. Current placeholder.
See: docs/API_MIDDLEWARE_AUDIT_2026_01_28.md - P1 task "file_ops router"
"""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Allowed export directories (relative to project root)
ALLOWED_EXPORT_DIRS = ["exports", "data/exports", "backtest_results"]


class FileExportRequest(BaseModel):
    """Request model for file export."""

    filename: str
    format: str = "json"  # json, csv
    data_type: str  # backtest, optimization, strategy


class FileExportResponse(BaseModel):
    """Response model for file export."""

    success: bool
    path: str | None = None
    message: str


@router.get("/status")
async def file_ops_status():
    """
    Check file operations service status.

    Returns:
        Service status and available operations.
    """
    return {
        "status": "ok",
        "message": "File operations service is running",
        "available_operations": [
            "GET /api/v1/file-ops/status - This endpoint",
            "GET /api/v1/file-ops/exports - List available exports",
            # TODO: Add more when implemented
        ],
        "note": "Full file operations coming soon",
    }


@router.get("/exports")
async def list_exports():
    """
    List available export files.

    Returns:
        List of export files with metadata.
    """
    exports = []
    project_root = Path(__file__).parent.parent.parent.parent

    for export_dir in ALLOWED_EXPORT_DIRS:
        dir_path = project_root / export_dir
        if dir_path.exists() and dir_path.is_dir():
            for file in dir_path.iterdir():
                if file.is_file() and file.suffix in [".json", ".csv", ".xlsx"]:
                    exports.append(
                        {
                            "name": file.name,
                            "path": str(file.relative_to(project_root)),
                            "size_bytes": file.stat().st_size,
                            "modified": file.stat().st_mtime,
                        }
                    )

    return {"exports": exports, "count": len(exports)}
