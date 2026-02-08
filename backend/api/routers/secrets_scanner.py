"""
Git Secrets Scanner API Router.

Provides REST API endpoints for scanning repository for leaked credentials.
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.git_secrets_scanner import (
    Finding,
    ScanResult,
    SecretPattern,
    SecretType,
    SeverityLevel,
    get_secrets_scanner,
)

router = APIRouter(prefix="/secrets-scanner", tags=["secrets-scanner"])


# Request/Response Models
class ScanDirectoryRequest(BaseModel):
    """Request to scan a directory."""

    directory: str = Field(..., description="Path to directory to scan")
    recursive: bool = Field(default=True, description="Scan recursively")


class ScanHistoryRequest(BaseModel):
    """Request to scan git history."""

    repo_path: str = Field(..., description="Path to git repository")
    max_commits: int = Field(
        default=100, ge=1, le=1000, description="Maximum commits to scan"
    )


class AddPatternRequest(BaseModel):
    """Request to add a custom pattern."""

    name: str = Field(..., description="Pattern name")
    pattern: str = Field(..., description="Regex pattern")
    secret_type: SecretType = Field(default=SecretType.GENERIC_SECRET)
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)
    description: str = Field(default="")
    false_positive_patterns: list[str] = Field(default_factory=list)


class MarkFalsePositiveRequest(BaseModel):
    """Request to mark a finding as false positive."""

    finding_id: str = Field(..., description="Finding ID to mark")


class FindingResponse(BaseModel):
    """Response model for a finding."""

    finding_id: str
    secret_type: str
    severity: str
    file_path: str
    line_number: int
    line_content: str
    pattern_name: str
    commit_hash: str | None = None
    author: str | None = None
    commit_date: datetime | None = None
    is_false_positive: bool
    remediation: str


class ScanResultResponse(BaseModel):
    """Response model for scan result."""

    scan_id: str
    start_time: datetime
    end_time: datetime | None = None
    status: str
    files_scanned: int
    findings_count: int
    findings: list[FindingResponse]
    errors: list[str]
    scan_path: str
    include_history: bool


class PatternResponse(BaseModel):
    """Response model for a pattern."""

    name: str
    pattern: str
    secret_type: str
    severity: str
    description: str


class StatisticsResponse(BaseModel):
    """Response model for statistics."""

    total_scans: int
    total_files_scanned: int
    total_findings: int
    false_positives_marked: int
    findings_by_severity: dict
    findings_by_type: dict
    patterns_count: int


def _finding_to_response(finding: Finding) -> FindingResponse:
    """Convert Finding to response model."""
    return FindingResponse(
        finding_id=finding.finding_id,
        secret_type=finding.secret_type.value,
        severity=finding.severity.value,
        file_path=finding.file_path,
        line_number=finding.line_number,
        line_content=finding.line_content,
        pattern_name=finding.pattern_name,
        commit_hash=finding.commit_hash,
        author=finding.author,
        commit_date=finding.commit_date,
        is_false_positive=finding.is_false_positive,
        remediation=finding.remediation,
    )


def _scan_result_to_response(result: ScanResult) -> ScanResultResponse:
    """Convert ScanResult to response model."""
    return ScanResultResponse(
        scan_id=result.scan_id,
        start_time=result.start_time,
        end_time=result.end_time,
        status=result.status.value,
        files_scanned=result.files_scanned,
        findings_count=len(result.findings),
        findings=[_finding_to_response(f) for f in result.findings],
        errors=result.errors,
        scan_path=result.scan_path,
        include_history=result.include_history,
    )


@router.get("/status")
async def get_status():
    """Get scanner status."""
    scanner = get_secrets_scanner()
    stats = scanner.get_statistics()

    return {
        "operational": True,
        "patterns_loaded": stats["patterns_count"],
        "total_scans": stats["total_scans"],
        "total_findings": stats["total_findings"],
    }


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """Get scanning statistics."""
    scanner = get_secrets_scanner()
    stats = scanner.get_statistics()
    return StatisticsResponse(**stats)


@router.post("/scan/directory", response_model=ScanResultResponse)
async def scan_directory(request: ScanDirectoryRequest):
    """Scan a directory for secrets."""
    scanner = get_secrets_scanner()

    directory = Path(request.directory)
    if not directory.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {request.directory}",
        )

    if not directory.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.directory}",
        )

    result = scanner.scan_directory(directory, recursive=request.recursive)
    return _scan_result_to_response(result)


@router.post("/scan/history", response_model=ScanResultResponse)
async def scan_git_history(request: ScanHistoryRequest):
    """Scan git history for secrets."""
    scanner = get_secrets_scanner()

    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {request.repo_path}",
        )

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not a git repository: {request.repo_path}",
        )

    result = scanner.scan_git_history(repo_path, max_commits=request.max_commits)
    return _scan_result_to_response(result)


@router.post("/scan/file")
async def scan_single_file(file_path: str = Query(..., description="File to scan")):
    """Scan a single file for secrets."""
    scanner = get_secrets_scanner()

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a file: {file_path}",
        )

    findings = scanner.scan_file(path)

    return {
        "file_path": file_path,
        "findings_count": len(findings),
        "findings": [_finding_to_response(f) for f in findings],
    }


@router.get("/scans", response_model=list[ScanResultResponse])
async def get_scan_history(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum scans to return"),
):
    """Get scan history."""
    scanner = get_secrets_scanner()
    history = scanner.get_scan_history(limit=limit)
    return [_scan_result_to_response(s) for s in history]


@router.get("/scans/{scan_id}", response_model=ScanResultResponse)
async def get_scan(scan_id: str):
    """Get a specific scan by ID."""
    scanner = get_secrets_scanner()
    result = scanner.get_scan_by_id(scan_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {scan_id}",
        )

    return _scan_result_to_response(result)


@router.get("/scans/{scan_id}/report")
async def get_scan_report(
    scan_id: str,
    format_type: str = Query(
        default="json", enum=["json", "markdown"], description="Report format"
    ),
):
    """Generate a report for a scan."""
    scanner = get_secrets_scanner()
    result = scanner.get_scan_by_id(scan_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan not found: {scan_id}",
        )

    report = scanner.generate_report(result, format_type=format_type)

    if format_type == "markdown":
        return {"format": "markdown", "content": report}

    return {"format": "json", "content": report}


@router.get("/patterns", response_model=list[PatternResponse])
async def list_patterns():
    """List all configured patterns."""
    scanner = get_secrets_scanner()
    patterns = scanner.get_patterns()

    return [
        PatternResponse(
            name=p.name,
            pattern=p.pattern,
            secret_type=p.secret_type.value,
            severity=p.severity.value,
            description=p.description,
        )
        for p in patterns
    ]


@router.post("/patterns")
async def add_pattern(request: AddPatternRequest):
    """Add a custom pattern."""
    scanner = get_secrets_scanner()

    # Validate regex
    import re

    try:
        re.compile(request.pattern)
    except re.error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid regex pattern: {e!s}",
        )

    pattern = SecretPattern(
        name=request.name,
        pattern=request.pattern,
        secret_type=request.secret_type,
        severity=request.severity,
        description=request.description,
        false_positive_patterns=request.false_positive_patterns,
    )

    scanner.add_pattern(pattern)

    return {"message": f"Pattern added: {request.name}"}


@router.delete("/patterns/{pattern_name}")
async def remove_pattern(pattern_name: str):
    """Remove a pattern by name."""
    scanner = get_secrets_scanner()
    success = scanner.remove_pattern(pattern_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_name}",
        )

    return {"message": f"Pattern removed: {pattern_name}"}


@router.post("/false-positives")
async def mark_false_positive(request: MarkFalsePositiveRequest):
    """Mark a finding as false positive."""
    scanner = get_secrets_scanner()
    scanner.mark_false_positive(request.finding_id)

    return {"message": f"Marked as false positive: {request.finding_id}"}


@router.get("/secret-types")
async def list_secret_types():
    """List all secret types."""
    return {"secret_types": [{"id": st.value, "name": st.name} for st in SecretType]}


@router.get("/severity-levels")
async def list_severity_levels():
    """List all severity levels."""
    return {
        "severity_levels": [{"id": sl.value, "name": sl.name} for sl in SeverityLevel]
    }


@router.get("/health")
async def health_check():
    """Health check for secrets scanner."""
    scanner = get_secrets_scanner()
    stats = scanner.get_statistics()

    return {
        "healthy": True,
        "patterns_loaded": stats["patterns_count"],
        "total_scans": stats["total_scans"],
    }
