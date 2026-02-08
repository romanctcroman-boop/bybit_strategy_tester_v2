# 🧠 Claude Sonnet 4.5 / Opus 4.5 — Enhanced Agent Rules

## Bybit Strategy Tester v2

> **Models**: Claude Sonnet 4.5, Claude Opus 4.5  
> **Mode**: Agent Mode (Extended Thinking + Tool Use)  
> **Autonomy Level**: Maximum  
> **Last Updated**: 2026-02-08  
> **Version**: 2.0

---

## 🎯 Model-Specific Capabilities (Claude 4.5)

### Claude Sonnet 4.5 Strengths

- **Fastest reasoning** — use for quick fixes, code generation, refactoring
- **Tool orchestration** — parallel tool calls, multi-file edits
- **Code-first thinking** — generates code directly without over-explaining
- **Context window**: 200K tokens — can hold entire project context

### Claude Opus 4.5 Strengths

- **Deep reasoning** — complex architecture decisions, algorithm design
- **Extended thinking** — step-by-step analysis for non-obvious problems
- **Planning mode** — multi-phase implementation plans
- **Security analysis** — finds subtle vulnerabilities

### When to Use Deep Thinking (Extended Thinking Mode)

- Complex architectural decisions requiring trade-off analysis
- Performance optimization (profiling → hypothesis → implementation → verification)
- Security vulnerability analysis and remediation
- Multi-step implementation plans spanning 5+ files
- Algorithm design and optimization (Big-O analysis)
- Debugging race conditions or intermittent failures
- Database schema design with constraint analysis

### Thinking Process (Chain-of-Thought)

1. **Decompose** — Break task into atomic sub-problems
2. **Context Gather** — Read relevant files BEFORE reasoning (use `@workspace`, `grep_search`)
3. **Analyze Trade-offs** — Compare 2-3 approaches with pros/cons
4. **Edge Cases** — Consider failure modes, boundary conditions, null/empty inputs
5. **Plan** — Create ordered execution plan with dependencies
6. **Execute** — Implement with parallel tool calls where possible
7. **Verify** — Run tests, check lint, validate output

### Advanced Reasoning Techniques

```markdown
## Multi-File Reasoning

When a change spans multiple files:

1. Map ALL affected files first (grep for usages)
2. Order changes by dependency (models → services → API → tests)
3. Apply changes atomically — don't leave inconsistent state
4. Run tests after EACH logical group of changes

## Hypothesis-Driven Debugging

1. State hypothesis: "The bug is likely in X because Y"
2. Design minimal test to confirm/deny
3. If confirmed → fix. If denied → next hypothesis
4. Maximum 3 hypotheses before escalating

## Architecture Decision Records (ADR)

For non-trivial decisions, document:

- Context: What situation requires a decision?
- Decision: What was decided?
- Consequences: What are the trade-offs?
- Alternatives: What was rejected and why?
```

---

## Memory & Context Management

### Session Start Checklist (MANDATORY)

```
□ Read AGENTS.MD (global rules)
□ Read .agent/memory/CONTEXT.md (what happened last)
□ Read .agent/memory/TODO.md (pending work)
□ Scan CHANGELOG.md tail (last 50 lines)
□ Check .agent/docs/DECISIONS.md (recent ADRs)
□ Check .agent/docs/ARCHITECTURE.md (system map)
□ Check applicable .github/instructions/ (path-specific rules)
□ Check applicable .agent/skills/ (reusable patterns)
```

### Session End Checklist

```
□ Update CHANGELOG.md with ALL work done (timestamped)
□ Update .agent/memory/CONTEXT.md (what to know next time)
□ Update .agent/memory/TODO.md (incomplete items)
□ Update ARCHITECTURE.md if structure changed
□ Add ADR to DECISIONS.md if significant decision made
□ Leave clear commit messages (conventional commits)
□ Run final quality check: pytest + ruff + mypy
```

### Smart Context Loading

```markdown
## Priority Context (always load):

1. copilot-instructions.md — project rules
2. .agent/memory/CONTEXT.md — recent state
3. Path-specific instructions for current task

## On-Demand Context (load when relevant):

4. .copilot/variable-tracker.md — when modifying critical vars
5. .agent/rules/\*.md — when autonomy questions arise
6. docs/architecture/\*.md — when touching architecture
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

| Check          | Question                             |
| -------------- | ------------------------------------ |
| ✅ Goal met?   | Did exactly what was asked?          |
| ✅ Tested?     | All tests passing?                   |
| ✅ Documented? | CHANGELOG, comments, docstrings?     |
| ✅ Clean?      | No lint errors, no type errors?      |
| ✅ Context?    | Enough info for next session?        |
| ✅ Innovative? | Any improvements suggested?          |
| ✅ Complete?   | No half-done changes or broken refs? |
| ✅ Secure?     | No secrets, no injection vectors?    |

---

## 🚀 Advanced Tool Orchestration (Claude 4.5 Specific)

### Parallel Tool Usage Strategy

Claude 4.5 excels at calling multiple tools simultaneously. Use this:

```markdown
## When to Parallelize:

- Reading multiple files that don't depend on each other
- Running grep_search + file_search simultaneously
- Checking errors in multiple files at once
- Reading instruction files + source files together

## When to Serialize:

- Edit A must complete before Edit B (dependency)
- Need file content before knowing what to edit
- Terminal commands that depend on prior output
- Test results needed to decide next action
```

### Multi-File Edit Workflow

```markdown
1. GATHER: Read all affected files in parallel (read_file × N)
2. PLAN: Map dependency order of changes
3. EDIT: Apply changes in dependency order
4. VERIFY: Check for errors (get_errors for all files)
5. TEST: Run relevant test suite
6. COMMIT: Stage and commit with conventional message
```

### Smart File Discovery

```markdown
## Finding relevant files for a task:

1. grep_search for function/class names → find definitions
2. list_code_usages → find all callers/importers
3. file_search with glob patterns → find by naming convention
4. semantic_search → when you don't know exact names
5. read_file on **init**.py → understand module structure
```

---

## 🔍 Advanced Debugging Protocol

### Systematic Debug Flow

```markdown
1. REPRODUCE: Understand the exact error/behavior
2. HYPOTHESIZE: Form 2-3 theories about root cause
3. NARROW: Use binary search to isolate the issue
    - Add strategic logging/breakpoints
    - Check input/output at each layer boundary
4. ROOT CAUSE: Identify the exact line/condition
5. FIX: Implement minimal change
6. VERIFY: Run tests + manual verification
7. PREVENT: Add test for this specific case
```

### Error Pattern Recognition

```python
# Common patterns in this project:
# 1. SQLAlchemy detached instance → use asyncio.to_thread() or eager loading
# 2. Bybit API retCode != 0 → check rate limits, validate params
# 3. DataFrame column missing → check strategy.generate_signals() output
# 4. Commission mismatch → ALWAYS use 0.0007
# 5. Timeframe mapping → check legacy TF conversion (3→5, 120→60)
```

---

## 🧪 Testing Superpowers

### Smart Test Selection

```markdown
## Run only relevant tests:

- Changed backend/backtesting/ → pytest tests/backtesting/ -v
- Changed backend/api/ → pytest tests/api/ -v
- Changed strategies/ → pytest tests/strategies/ -v
- Changed core metrics → pytest tests/ -v -k "metric"
- Unsure → pytest tests/ -v --tb=short (all tests, short output)
```

### Test Quality Rules

```python
# Every test MUST:
# 1. Test ONE thing (single assertion focus)
# 2. Have descriptive name: test_[what]_[scenario]_[expected]
# 3. Use fixtures from conftest.py (sample_ohlcv, mock_adapter)
# 4. NEVER call real Bybit API
# 5. Run in < 5 seconds (mark slow tests with @pytest.mark.slow)
```

---

## 📊 Performance Profiling Skills

### When Performance Matters

```python
# Profile BEFORE optimizing:
# 1. py -3.14 -m cProfile -s cumtime script.py
# 2. memory_profiler for memory-intensive operations
# 3. timeit for micro-benchmarks
# 4. pandas .info() and .memory_usage() for DataFrame optimization

# Common bottlenecks in this project:
# - Large DataFrame copies (use .copy() only when needed)
# - Repeated indicator calculations (cache results)
# - SQLite N+1 queries (use batch loading)
# - JSON serialization of large trade lists
```

---

_Version: 2.0_
_Models: Claude Sonnet 4.5, Claude Opus 4.5_
_Last Updated: 2026-02-08_
_Changes: v2.0 - Complete rewrite for Claude 4.5 capabilities, added tool orchestration, advanced debugging, performance profiling, multi-file reasoning, hypothesis-driven debugging_
