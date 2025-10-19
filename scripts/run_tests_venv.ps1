param(
    [string]$TestTarget = "tests/test_xpending_parser.py"
)

# Resolve project root (one level up from script folder)
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Write-Host "Project root: $ProjectRoot"

# Ensure PYTHONPATH points to project root for imports
$env:PYTHONPATH = $ProjectRoot.Path
Write-Host "Set PYTHONPATH=$($env:PYTHONPATH)"

# Prefer venv python if present
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
}
else {
    $Python = 'python'
}
Write-Host "Using python: $Python"

$
# Ensure current working directory is project root so sys.path[0] is the repo root
Set-Location $ProjectRoot.Path
Write-Host "Changed directory to: $(Get-Location)"

# Run pytest for the target
Write-Host "Running pytest for: $TestTarget"
& $Python -m pytest -q $TestTarget
$Exit = $LASTEXITCODE
Write-Host "pytest exit code: $Exit"
exit $Exit
