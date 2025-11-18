<#
Phase 1 Staging Deployment Script
Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_phase1_staging.ps1 -Branch phase1-staging -PythonVersion 3.13.3
#>
param(
    [string]$Branch = "phase1-staging",
    [string]$PythonVersion = "3.13.3"
)

Write-Host "[INFO] Phase 1 staging deployment starting for branch $Branch" -ForegroundColor Cyan

# 1. Pull latest branch
if (-not (Test-Path .git)) { Write-Error "Run inside repository root"; exit 1 }

Write-Host "[STEP] Fetch + checkout branch" -ForegroundColor Yellow
& git fetch origin 2>$null
& git checkout $Branch 2>$null
& git pull origin $Branch 2>$null

# 2. Python virtual environment
if (-not (Test-Path .venv)) {
    Write-Host "[STEP] Create virtualenv" -ForegroundColor Yellow
    & py -$PythonVersion -m venv .venv
}

Write-Host "[STEP] Activate virtualenv" -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# 3. Upgrade pip & install core deps
Write-Host "[STEP] Install dependencies" -ForegroundColor Yellow
& python -m pip install --upgrade pip
if (Test-Path backend\requirements.txt) {
    & pip install -r backend\requirements.txt
}
if (Test-Path deployment\requirements-prod.txt) {
    & pip install -r deployment\requirements-prod.txt
}
& pip install pybreaker==1.0.2

# 4. Environment file sanity
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Warning "Created .env from example. Fill API keys before using agents."
}

# 5. Database migration
Write-Host "[STEP] Apply migrations" -ForegroundColor Yellow
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/postgres' }
& python -m alembic upgrade head

# 6. Quick health check (without starting separate process if already supervised)
Start-Sleep -Seconds 2
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "[OK] Existing backend already running" -ForegroundColor Green
    $health.Content | Out-File deployment_health_snapshot.json -Encoding UTF8
}
catch {
    Write-Host "[STEP] Start backend server (uvicorn)" -ForegroundColor Yellow
    Start-Process -FilePath python -ArgumentList "-m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --log-level info" -WindowStyle Hidden
    Start-Sleep -Seconds 6
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        Write-Host "[OK] Backend started" -ForegroundColor Green
        $health.Content | Out-File deployment_health_snapshot.json -Encoding UTF8
    }
    catch {
        Write-Error "Backend failed to start: $($_.Exception.Message)"; exit 2
    }
}

# 7. Trigger first agent request (lazy health monitor start)
Write-Host "[STEP] Trigger first agent request" -ForegroundColor Yellow

# Create temporary Python script
$tempScript = Join-Path $env:TEMP "agent_test_$(Get-Random).py"
$pythonCode = @'
import asyncio, json, sys
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "scripts" else Path.cwd()
sys.path.insert(0, str(project_root))

from backend.agents.unified_agent_interface import get_agent_interface, AgentRequest, AgentType

async def main():
    agent = get_agent_interface()
    req = AgentRequest(agent_type=AgentType.DEEPSEEK, task_type="analyze", prompt="ping", code="", context={})
    try:
        resp = await agent.execute(req)
        print(json.dumps({"success": True, "response_keys": list(resp.keys())}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
'@

# Write, execute, cleanup
$pythonCode | Out-File -FilePath $tempScript -Encoding UTF8
try {
    & python $tempScript | Out-File deployment_agent_test.json -Encoding UTF8
    Write-Host "[OK] Agent test completed" -ForegroundColor Green
}
catch {
    Write-Warning "Agent test failed: $($_.Exception.Message)"
}
finally {
    Remove-Item -Path $tempScript -Force -ErrorAction SilentlyContinue
}

Write-Host "[INFO] Phase 1 staging deployment finished" -ForegroundColor Cyan
