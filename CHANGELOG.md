# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-23

### Added

- **MCP Modular Architecture** — Extracted MCP tools to `backend/api/mcp/tools/`
  for better maintainability
- **Rate Limiting Middleware** — Added `slowapi`-based rate limiting with Redis support
- **Health Dashboard** — New `frontend/health-dashboard.html` for service monitoring
- **Environment Validation** — `scripts/validate_env.ps1` script to check configuration
- **Dev Commands** — `dev.ps1` (Windows) and `Makefile` (Linux/Mac) for common tasks
- **Pre-commit Hooks** — Automated code quality checks with ruff, bandit
- **Docstring Standards** — `backend/utils/docstring_standards.py` with Google-style templates
- **Unit Tests for MCP** — New test suite in `tests/backend/api/mcp/`
- **API Documentation** — Added `docs/api/` with endpoint reference

### Changed

- **Project Configuration** — Migrated to modern `pyproject.toml` (PEP 621)
- **README.md** — Complete rewrite following Google documentation standards
- **QUICKSTART.md** — Updated with current commands and structure
- **GitHub Actions** — Updated CI to use ruff instead of black
- **Swagger/OpenAPI** — Enhanced API documentation with detailed descriptions

### Improved

- **Docker Configuration** — Added resource limits to all services
- **`.dockerignore`** — Comprehensive exclusion list for smaller images
- **Code Quality** — Ruff fixed 3,981 linting errors, formatted 113 files

### Removed

- **Inline MCP Tools** — Removed 666 lines of inline code from `app.py`
- **Duplicate Documentation** — Archived 131+ redundant `.md` files

### Organized

- **Root Directory** — Cleaned 500+ temporary `.py` files to `scripts/archive/`
- **Documentation** — Reorganized `docs/` into categories:
    - `docs/api/` — API documentation
    - `docs/architecture/` — System design (7 files)
    - `docs/ai/` — AI agent docs (5 files)
    - `docs/reference/` — Reference documentation (11 files)
    - `docs/guides/` — User guides
    - `docs/archive/` — Historical documentation
- **Temporary Files** — Moved 133 `.json`/`.txt` files to `data/archive/`

### Security

- **Bandit Integration** — Security scanning in CI pipeline
- **Rate Limiting** — Protection against API abuse
- **Path Traversal Protection** — Enhanced file access security in MCP tools

## [2.0.0] - 2025-12-01

### Added

- Initial v2 release with FastAPI backend
- AI agent integration (DeepSeek, Perplexity)
- Backtesting engine with TradingView parity
- WebSocket real-time data
- Docker and Kubernetes support

---

## Migration Notes

### From 2.0.x to 2.1.0

1.  **Install new dependencies**:

    ```powershell
    pip install -r requirements-dev.txt
    pip install slowapi
    ```

2.  **Install pre-commit hooks** (Linux/Mac):

    ```bash
    pre-commit install
    pre-commit run --all-files
    ```

    > **Windows users**: Pre-commit may have fork issues on Windows.
    > Use `.\dev.ps1 lint` and `.\dev.ps1 format` instead.
    > Pre-commit checks run automatically in GitHub Actions CI/CD.

3.  **Update environment**:

    ```powershell
    .\scripts\validate_env.ps1
    ```

4.  **Use new dev commands**:

    ```powershell
    .\dev.ps1 help         # Show all commands
    .\dev.ps1 lint         # Lint code
    .\dev.ps1 format       # Format code
    .\dev.ps1 test         # Run tests
    ```
