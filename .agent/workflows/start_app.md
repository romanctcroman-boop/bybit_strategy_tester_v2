---
description: Start the Bybit Strategy Tester v2 application
---

# Start Application

## Overview

Start all backend services for the Bybit Strategy Tester v2 platform.

## Prerequisites

- Python 3.11+ venv activated at `.venv/`
- Redis installed (optional, for caching)
- SQLite databases present (`data.sqlite3`, `bybit_klines_15m.db`)

## Quick Start (VS Code Task)

Use the VS Code task **"Start All Services"** which starts services in order:

1. Clear Python Cache
2. Start Redis Server
3. Start Kline DB Service
4. Start DB Maintenance Server
5. Start Uvicorn Server (port 8000, 4 workers)
6. Start MCP Server
7. Start AI Agent Service

## Manual Start (Single Server)

If only the API server is needed:

```powershell
.\.venv\Scripts\uvicorn.exe backend.api.app:app --host 0.0.0.0 --port 8000
```

## Verification

After starting, verify the server is healthy:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/health
```

Expected: `{"status": "ok", ...}`

## Key URLs

| URL                                                  | Purpose             |
| ---------------------------------------------------- | ------------------- |
| http://localhost:8000/frontend/strategy-builder.html | Strategy Builder UI |
| http://localhost:8000/frontend/dashboard.html        | Dashboard           |
| http://localhost:8000/docs                           | Swagger API docs    |
| http://localhost:8000/api/v1/health                  | Health check        |

## Stop All Services

Use the VS Code task **"Stop All Services"** or run:

```powershell
.\stop_all.ps1
```
