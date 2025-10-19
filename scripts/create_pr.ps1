<#
.SYNOPSIS
  Create a pull request for a local branch and push it to origin.

.DESCRIPTION
  This script ensures the correct remote, pushes a local branch and creates a PR on GitHub.
  It prefers the GitHub CLI (`gh`) when available and authenticated. If `gh` is missing or not
  authenticated, it falls back to the GitHub REST API and requires a Personal Access Token (PAT).

.NOTES
  - Provide a token either as the -Token parameter or in the environment variable GITHUB_TOKEN.
  - The script will abort if there are uncommitted changes (to avoid accidental commits of logs).
  - Default repo values are set for RomanCTC/bybit_strategy_tester_v2 and branch integration/testcontainers.

USAGE examples:
  # use environment token
  $env:GITHUB_TOKEN = 'ghp_...'
  .\create_pr.ps1

  # pass token explicitly and open PR in browser
  .\create_pr.ps1 -Token 'ghp_...' -Open

#>

param(
    [string]$RepoOwner = 'RomanCTC',
    [string]$RepoName = 'bybit_strategy_tester_v2',
    [string]$Branch = 'integration/testcontainers',
    [string]$Base = 'main',
    [string]$RemoteUrl = "https://github.com/RomanCTC/bybit_strategy_tester_v2.git",
    [string]$Title = 'Integration: testcontainers smoke',
    [string]$Body = 'Adds integration tests (testcontainers) and CI workflow.',
    [switch]$Open,
    [string]$Token
)

function Abort([string]$msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "Starting create_pr.ps1..." -ForegroundColor Cyan

# ensure running in repo root (best-effort)
$cwd = Get-Location
Write-Host "Working directory: $cwd"

# check git presence
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Abort 'git is not available in PATH.'
}

# check for uncommitted changes
$status = git status --porcelain
if ($status) {
    Write-Host "There are uncommitted changes in the working tree:" -ForegroundColor Yellow
    git status --short
    Abort 'Commit or stash changes before running this script.'
}

# ensure remote is set correctly
$currentRemote = (git remote get-url origin 2>$null) -join ''
if ($currentRemote -ne $RemoteUrl) {
    Write-Host "Setting origin to $RemoteUrl"
    git remote remove origin 2>$null | Out-Null
    git remote add origin $RemoteUrl
}
else {
    Write-Host "Origin already set to $RemoteUrl"
}

# fetch remote refs
git fetch origin $Base

# push branch
Write-Host "Pushing branch $Branch to origin..."
$pushResult = git push -u origin $Branch 2>&1
Write-Host $pushResult

# Try GitHub CLI first
if (Get-Command gh -ErrorAction SilentlyContinue) {
    try {
        gh auth status 2>&1 | Out-Null
        Write-Host "Using gh to create PR..."
        $ghOutput = gh pr create --repo "$RepoOwner/$RepoName" --base $Base --head $Branch --title $Title --body $Body --web:false 2>&1
        if ($LASTEXITCODE -eq 0) {
            # gh prints URL to stdout
            $prUrl = ($ghOutput | Select-String -Pattern 'https://github.com/.+?/pull/\d+' -AllMatches).Matches.Value | Select-Object -First 1
            if (-not $prUrl) { $prUrl = $ghOutput | Select-String -Pattern 'http' | Select-Object -First 1 }
            Write-Host "PR created: $prUrl"
            if ($Open -and $prUrl) { Start-Process $prUrl }
            exit 0
        }
        else {
            Write-Host "gh failed or returned non-zero; falling back to REST API." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "gh unavailable or unauthenticated; falling back to REST API." -ForegroundColor Yellow
    }
}

# fall back to REST API; find token
if (-not $Token) { $Token = $env:GITHUB_TOKEN }
if (-not $Token) { Abort 'No GitHub token provided. Set -Token or $env:GITHUB_TOKEN.' }

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$apiUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/pulls"
$bodyObj = @{ title = $Title; head = $Branch; base = $Base; body = $Body }
$json = $bodyObj | ConvertTo-Json -Depth 10

Write-Host "Creating PR via GitHub API..."
try {
    $resp = Invoke-RestMethod -Uri $apiUrl -Method Post -Headers @{ Authorization = "token $Token"; "User-Agent" = "create_pr.ps1" } -Body $json -ContentType 'application/json'
    if ($resp.html_url) {
        Write-Host "PR created: $($resp.html_url)" -ForegroundColor Green
        if ($Open) { Start-Process $resp.html_url }
    }
    else {
        Write-Host "Unexpected response from API:" -ForegroundColor Yellow
        $resp | Format-List | Out-Host
    }
}
catch {
    Write-Host "Failed to create PR via API:" -ForegroundColor Red
    $_ | Format-List | Out-Host
    Abort 'API call failed.'
}
