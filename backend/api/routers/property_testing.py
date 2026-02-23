"""
Property-Based Testing API Router.

Provides REST API for property-based testing of trading strategies.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.property_testing import (
    PropertyTestResult,
    TestReport,
    TestResult,
    get_property_testing_service,
)

router = APIRouter(prefix="/api/v1/property-testing")


# ============================================================
# Request/Response Models
# ============================================================


class PropertyTestRequest(BaseModel):
    """Request to run a property test."""

    property_name: str
    test_data: dict
    num_examples: int | None = 100


class StrategyTestRequest(BaseModel):
    """Request to test strategy invariants."""

    strategy_config: dict
    market_data: list[dict]


class EdgeCaseRequest(BaseModel):
    """Request to generate edge cases."""

    property_name: str
    num_cases: int = 10


class TestResultResponse(BaseModel):
    """Response for a single test result."""

    property_name: str
    result: str
    examples_tested: int
    failing_example: str | None = None
    error_message: str | None = None
    duration_ms: float
    timestamp: str


class TestReportResponse(BaseModel):
    """Response for a test report."""

    total_properties: int
    passed: int
    failed: int
    skipped: int
    errors: int
    success_rate: float
    duration_ms: float
    results: list[TestResultResponse]
    timestamp: str


class PropertyInfo(BaseModel):
    """Information about a registered property."""

    name: str
    description: str
    type: str
    min_examples: int
    max_examples: int


class ServiceStatusResponse(BaseModel):
    """Service status response."""

    initialized: bool
    registered_properties: int
    total_tests_run: int
    tests_passed: int
    tests_failed: int
    test_reports: int
    last_test: str | None = None


# ============================================================
# Helper Functions
# ============================================================


def _convert_result(result: PropertyTestResult) -> TestResultResponse:
    """Convert PropertyTestResult to response model."""
    return TestResultResponse(
        property_name=result.property_name,
        result=result.result.value,
        examples_tested=result.examples_tested,
        failing_example=(
            str(result.failing_example)[:500] if result.failing_example else None
        ),
        error_message=result.error_message,
        duration_ms=result.duration_ms,
        timestamp=result.timestamp.isoformat(),
    )


def _convert_report(report: TestReport) -> TestReportResponse:
    """Convert TestReport to response model."""
    return TestReportResponse(
        total_properties=report.total_properties,
        passed=report.passed,
        failed=report.failed,
        skipped=report.skipped,
        errors=report.errors,
        success_rate=report.success_rate,
        duration_ms=report.duration_ms,
        results=[_convert_result(r) for r in report.results],
        timestamp=report.timestamp.isoformat(),
    )


# ============================================================
# API Endpoints
# ============================================================


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """Get property testing service status."""
    service = get_property_testing_service()
    status = service.get_status()
    return ServiceStatusResponse(**status)


@router.get("/properties", response_model=list[PropertyInfo])
async def list_properties():
    """List all registered properties."""
    service = get_property_testing_service()
    properties = service.list_properties()
    return [PropertyInfo(**p) for p in properties]


@router.get("/properties/{property_name}", response_model=PropertyInfo)
async def get_property(property_name: str):
    """Get information about a specific property."""
    service = get_property_testing_service()
    properties = service.list_properties()

    for p in properties:
        if p["name"] == property_name:
            return PropertyInfo(**p)

    raise HTTPException(
        status_code=404,
        detail=f"Property '{property_name}' not found",
    )


@router.post("/run", response_model=TestResultResponse)
async def run_property_test(request: PropertyTestRequest):
    """Run a single property test."""
    service = get_property_testing_service()

    result = service.run_property_test(
        property_name=request.property_name,
        test_data=request.test_data,
        num_examples=request.num_examples,
    )

    return _convert_result(result)


@router.post("/run-all", response_model=TestReportResponse)
async def run_all_tests(num_examples: int = 100):
    """Run all registered property tests."""
    service = get_property_testing_service()

    report = service.run_all_tests(num_examples=num_examples)
    return _convert_report(report)


@router.post("/test-strategy", response_model=TestReportResponse)
async def test_strategy_invariants(request: StrategyTestRequest):
    """Test trading strategy invariants."""
    service = get_property_testing_service()

    if not request.market_data:
        raise HTTPException(
            status_code=400,
            detail="Market data is required",
        )

    report = service.test_strategy_invariants(
        strategy_config=request.strategy_config,
        market_data=request.market_data,
    )

    return _convert_report(report)


@router.post("/edge-cases", response_model=list[dict])
async def generate_edge_cases(request: EdgeCaseRequest):
    """Generate edge cases for a property."""
    service = get_property_testing_service()

    # Verify property exists
    properties = service.list_properties()
    if not any(p["name"] == request.property_name for p in properties):
        raise HTTPException(
            status_code=404,
            detail=f"Property '{request.property_name}' not found",
        )

    cases = service.generate_edge_cases(
        property_name=request.property_name,
        num_cases=request.num_cases,
    )

    return cases


@router.post("/edge-cases/{property_name}/run", response_model=TestReportResponse)
async def run_edge_case_tests(property_name: str):
    """Run edge case tests for a property."""
    service = get_property_testing_service()

    # Verify property exists
    properties = service.list_properties()
    if not any(p["name"] == property_name for p in properties):
        raise HTTPException(
            status_code=404,
            detail=f"Property '{property_name}' not found",
        )

    # Generate and run edge cases
    edge_cases = service.generate_edge_cases(property_name, num_cases=10)

    results = []
    for _i, case in enumerate(edge_cases):
        result = service.run_property_test(
            property_name=property_name,
            test_data=case,
            num_examples=1,
        )
        results.append(result)

    passed = sum(1 for r in results if r.result == TestResult.PASSED)
    failed = sum(1 for r in results if r.result == TestResult.FAILED)
    errors = sum(1 for r in results if r.result == TestResult.ERROR)

    report = TestReport(
        total_properties=len(results),
        passed=passed,
        failed=failed,
        skipped=0,
        errors=errors,
        results=results,
        duration_ms=sum(r.duration_ms for r in results),
    )

    return _convert_report(report)


@router.get("/history", response_model=list[dict])
async def get_test_history(
    limit: int = 10,
    since: str | None = None,
):
    """Get test execution history."""
    service = get_property_testing_service()

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid 'since' format. Use ISO format.",
            )

    history = service.get_test_history(limit=limit, since=since_dt)
    return history


@router.get("/failures", response_model=dict)
async def get_failure_summary():
    """Get summary of recent test failures."""
    service = get_property_testing_service()
    return service.get_failure_summary()


@router.get("/summary", response_model=dict)
async def get_testing_summary():
    """Get comprehensive testing summary."""
    service = get_property_testing_service()

    status = service.get_status()
    failures = service.get_failure_summary()
    properties = service.list_properties()

    success_rate = 0.0
    if status["total_tests_run"] > 0:
        success_rate = (status["tests_passed"] / status["total_tests_run"]) * 100

    return {
        "status": "healthy" if status["initialized"] else "not_initialized",
        "properties_registered": len(properties),
        "total_tests_run": status["total_tests_run"],
        "tests_passed": status["tests_passed"],
        "tests_failed": status["tests_failed"],
        "success_rate": round(success_rate, 2),
        "recent_failures": failures["total_failures"],
        "last_test": status["last_test"],
        "property_types": {
            "invariant": sum(1 for p in properties if p["type"] == "invariant"),
            "boundary": sum(1 for p in properties if p["type"] == "boundary"),
            "monotonic": sum(1 for p in properties if p["type"] == "monotonic"),
            "statistical": sum(1 for p in properties if p["type"] == "statistical"),
        },
    }


@router.get("/property-types", response_model=list[str])
async def list_property_types():
    """List all available property types."""
    return [
        "invariant",
        "statistical",
        "boundary",
        "monotonic",
        "idempotent",
        "commutative",
    ]
