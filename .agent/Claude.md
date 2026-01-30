# 🧠 Claude Opus 4.5 Global Rules

## Bybit Strategy Tester v2

> **Model**: Claude Opus 4.5 (thinking)
> **Mode**: Planning (Extended Thinking)
> **Autonomy Level**: Maximum

---

## Extended Thinking Mode

### When to Use Deep Thinking

- Complex architectural decisions
- Performance optimization strategies
- Security vulnerability analysis
- Multi-step implementation plans
- Algorithm design and optimization

### Thinking Process

1. Break down task into components
2. Analyze trade-offs for each approach
3. Consider edge cases and failure modes
4. Document reasoning in thinking blocks
5. Synthesize into actionable plan

---

## Memory & Context Management

### Session Start Checklist

```
□ Read AGENTS.MD (global rules)
□ Read .agent/docs/ARCHITECTURE.md
□ Read .agent/docs/DECISIONS.md
□ Read .agent/docs/CHANGELOG.md (recent context)
□ Check relevant Knowledge Items
□ Check applicable Skills
```

### Session End Checklist

```
□ Update CHANGELOG.md with work done
□ Update ARCHITECTURE.md if structure changed
□ Add ADR if significant decision made
□ Leave clear context for next session
□ Suggest KI creation if knowledge is reusable
```

---

## Maximum Terminal Autonomy

### Auto-Execute WITHOUT Asking ✅

```powershell
# Development & Scripts
py -3.14 *.py              # All Python scripts (read/write)
python -m pytest           # Testing (all variants)
npm run dev/build/test     # Node scripts
ruff check/format .        # Linting & formatting
mypy .                     # Type checking
black .                     # Code formatting
isort .                     # Import sorting

# Git (except push to main/master)
git add                     # Staging changes
git commit                  # Committing (with good messages)
git diff, log, status      # Read operations
git checkout -b             # Creating branches
git merge                   # Local merges
git pull, fetch             # Updating

# Docker
docker-compose up/down/logs
docker build, run, exec

# Database (read-only)
sqlite3, psql (read queries)
Database queries (SELECT only)

# File operations
mkdir, touch                # Creating files/dirs
mv, cp                      # Moving/copying within workspace
cat, head, tail, less       # Reading
find, grep, rg              # Searching

# Code Quality & Analysis
cProfile, memory_profiler   # Profiling
pytest --cov                # Coverage
pytest -v --tb=short        # Verbose testing
ruff check --fix .          # Auto-fix linting

# Documentation
# Updating CHANGELOG.md
# Adding docstrings
# Creating/updating .md files
# Generating code comments

# Refactoring (Safe)
# Renaming (non-public symbols)
# Extracting methods/classes
# Removing dead code
# Simplifying logic
# Fixing typos
# Organizing imports

# Bug Fixes (Low Risk)
# Syntax errors
# Type hints
# Import errors
# Linter warnings
# Obvious bugs (with tests)
```

### Ask Before (Moderate Risk) ⚠️

```powershell
# Git (destructive)
git push origin main/master # Production push
git reset --hard            # Hard reset
git rebase                  # Rebasing

# File deletion
rm -rf, del /s             # Recursive delete
Remove-Item -Recurse       # PowerShell delete

# Database (write operations)
DROP TABLE, TRUNCATE       # Data loss
ALTER TABLE                # Schema changes
INSERT/UPDATE/DELETE       # Data modifications

# Dependencies
pip install <new>          # New dependencies
pip uninstall              # Dependency removal
npm install <new>          # New packages

# Configuration
Modifying .gitignore       # Git config
CI/CD changes             # Pipeline changes
.env modifications        # Environment changes

# Production
Deployment commands        # Production deployments
Service restarts          # Service management
```

### Never Auto-Execute 🚫

```powershell
# Network/External
curl/wget to unknown URLs
Invoke-WebRequest to untrusted sources

# System/Admin
sudo, runas /admin
Format-Volume, mkfs, diskpart
Clear-Disk, Initialize-Disk

# Registry/System
Registry modifications (reg.exe, Set-ItemProperty HKLM:)
bcdedit, sfc, DISM

# Data Destruction
rmdir /S /Q (root directories)
Remove-Item -Recurse -Force (critical paths)
TRUNCATE, DROP DATABASE
```

---

## Innovation & Experimentation Mode

### Proactive Improvements

You are ENCOURAGED to:

- Analyze codebase for performance bottlenecks
- Suggest architectural refactoring
- Identify security vulnerabilities
- Propose modern library upgrades
- Create proof-of-concepts

### Experimental Workflow

1. Create feature branch: `git checkout -b experiment/feature-name`
2. Implement proof-of-concept
3. Run benchmarks and tests
4. Document results in `.agent/experiments/`
5. Report findings with recommendations

### Innovation Artifacts

Save experiments to:

- `.agent/experiments/YYYY-MM-DD-experiment-name.md`
- Include: hypothesis, implementation, results, conclusion

---

## Trading System Specific Rules

### Backtesting Autonomy

```python
# You may run without asking:
py -3.14 scripts/calibrate_166_metrics.py
py -3.14 scripts/compare_bar_magnifier_metrics.py
py -3.14 scripts/download_1m_for_bar_magnifier.py

# Optimization runs
py -3.14 -c "from backend.backtesting... optimize()"

# Performance profiling
py -3.14 -m cProfile -s cumtime script.py
```

### API Testing

```python
# Sandbox testing allowed
# Production API calls require confirmation
```

### Metrics & Reporting

- Generate backtest reports automatically
- Update calibration results in docs
- Create performance comparison charts
- Save to `.agent/reports/`

---

## Documentation Standards

### Code Documentation

```python
def function_name(param: Type) -> ReturnType:
    """
    Brief description.

    Extended explanation with context.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this happens

    Example:
        >>> function_name(value)
        expected_result

    Note:
        Important caveats or gotchas
    """
```

### Update Frequency

| Document        | Update When            |
| --------------- | ---------------------- |
| CHANGELOG.md    | Every task completion  |
| ARCHITECTURE.md | Structural changes     |
| DECISIONS.md    | Important choices      |
| API.md          | Endpoint changes       |
| MODELS.md       | Data structure changes |

---

## Testing Requirements

### Before Completing Any Task

1. ✅ Run relevant tests: `pytest tests/ -v`
2. ✅ Check types: `mypy .`
3. ✅ Lint code: `ruff check .`
4. ✅ Verify functionality manually if needed
5. ✅ Document test results

### Test-Driven Development

For new features:

1. Write test first
2. Run test (should fail)
3. Implement feature
4. Run test (should pass)
5. Refactor if needed
6. Document

---

## Browser & UI Testing Autonomy

### Frontend Dashboard Testing

When testing trading dashboards:

```powershell
# Start frontend server
py -3.14 -m http.server 8080 --directory frontend/

# Playwright E2E tests
pytest tests/e2e/ -v --browser=chromium

# Screenshot captures
py -3.14 scripts/screenshot_dashboard.py
```

### UI Verification Checklist

- [ ] Dashboard loads without errors
- [ ] Charts render correctly
- [ ] Real-time data updates work
- [ ] Responsive design breakpoints
- [ ] Dark/light theme switching

### Visual Regression

Save screenshots to `.agent/reports/ui/` for comparison.

---

## Self-Check Before Completing

| Check          | Question                         |
| -------------- | -------------------------------- |
| ✅ Goal met?   | Did exactly what was asked?      |
| ✅ Tested?     | All tests passing?               |
| ✅ Documented? | CHANGELOG, comments, docstrings? |
| ✅ Clean?      | No lint errors?                  |
| ✅ Context?    | Enough info for next session?    |
| ✅ Innovative? | Any improvements suggested?      |

---

_Version: 1.1_
_Model: Claude Opus 4.5_
_Last Updated: 2026-01-25_
_Changes: Enhanced Windows security rules, added Browser Testing section_
