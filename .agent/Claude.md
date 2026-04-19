# 🧠 Claude Sonnet 4 / Opus 4 — Agent Rules

## Bybit Strategy Tester v2

> **Models**: Claude Sonnet 4, Claude Opus 4
> **Mode**: Agent Mode (Extended Thinking + Tool Use)
> **Autonomy Level**: Maximum
> **Version**: 3.1
> **Last Updated**: 2026-02-14

---

## 🌐 Язык общения

**Вывод беседы в чат на Русском языке.** Все ответы, объяснения, комментарии к задачам и отчёты о проделанной работе — на русском. Код, имена переменных и комментарии в коде остаются на английском (Google-style docstrings, etc.).

---

## 🎯 Model-Specific Capabilities

### Claude Sonnet 4 Strengths

- **Fastest reasoning** — use for quick fixes, code generation, refactoring
- **Tool orchestration** — parallel tool calls, multi-file edits
- **Code-first thinking** — generates code directly without over-explaining
- **Context window**: 200K tokens — can hold entire project context

### Claude Opus 4 Strengths

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

---

## ⚡ Speed Rules (CRITICAL)

### DO:

- **Edit first, verify once** — batch all edits, then one `get_errors` call
- **Parallel reads** — read 3-5 files simultaneously
- **Targeted tests** — `pytest tests/path/ -q` only for changed modules
- **Fix and move on** — don't re-verify what `get_errors` already confirmed as clean

### DON'T:

- Run full `pytest tests/` after every small edit
- Run `mypy .` on the whole project — use `get_errors` on specific files
- Read 8 context files before starting work
- Run `ruff check .` globally — use `get_errors` per file
- Over-explain — code speaks for itself

### Verification Strategy

```
Small change (1-2 files):  get_errors on those files → done
Medium change (3-5 files): get_errors on all → targeted pytest if logic changed
Large change (5+ files):   get_errors → pytest on affected module → ruff check .
```

---

## 🎯 Context Loading (Minimal)

### Always available (auto-loaded by VS Code):

- `copilot-instructions.md` — project rules
- `.github/instructions/*.md` — path-specific rules (auto-applied)
- `AGENTS.MD` — global agent rules

### Load ONLY when needed:

- `CHANGELOG.md` — only if asked about recent changes
- `DECISIONS.md` — only for architecture decisions
- `.agent/memory/` — only for multi-session continuity

---

## 🔧 Work Patterns

### Quick Fix (< 5 min)

1. Read affected file(s)
2. Apply fix(es)
3. `get_errors` on changed files
4. Done

### Feature/Refactor (5-30 min)

1. Read affected files in parallel
2. Plan edits (dependency order)
3. Apply all edits
4. `get_errors` on all changed files
5. Run targeted tests if logic changed
6. Update CHANGELOG.md

### Bug Fix

1. Reproduce: read error context
2. Hypothesize (max 2 theories)
3. Fix most likely cause
4. `get_errors` + targeted test
5. If still broken → try theory 2

---

## 🧪 Testing (Targeted Only)

```powershell
# Changed adapters → test adapters
pytest tests/backend/services/ -q --tb=short

# Changed engines → test engines
pytest tests/backend/backtesting/ -q --tb=short

# Changed API routes → test API
pytest tests/backend/api/ -q --tb=short

# Changed strategies → test strategies
pytest tests/backend/strategies/ -q --tb=short

# Pre-commit (full) → only when explicitly asked
pytest tests/ -q --tb=line --ignore=tests/backend/api/routers/test_chat_history.py
```

### Known Broken Tests (skip):

- `test_chat_history.py` — missing `chat_conversations` table (pre-existing)

---

## 🧠 Advanced Reasoning

### Thinking Process (Chain-of-Thought)

1. **Decompose** — Break task into atomic sub-problems
2. **Context Gather** — Read relevant files BEFORE reasoning
3. **Analyze Trade-offs** — Compare 2-3 approaches with pros/cons
4. **Edge Cases** — Consider failure modes, boundary conditions, null/empty inputs
5. **Plan** — Create ordered execution plan with dependencies
6. **Execute** — Implement with parallel tool calls where possible
7. **Verify** — Run tests, check lint, validate output

### Multi-File Reasoning

When a change spans multiple files:

1. Map ALL affected files first (grep for usages)
2. Order changes by dependency (models → services → API → tests)
3. Apply changes atomically — don't leave inconsistent state
4. Run tests after EACH logical group of changes

### Hypothesis-Driven Debugging

1. State hypothesis: "The bug is likely in X because Y"
2. Design minimal test to confirm/deny
3. If confirmed → fix. If denied → next hypothesis
4. Maximum 3 hypotheses before escalating

### Architecture Decision Records (ADR)

For non-trivial decisions, document:

- Context: What situation requires a decision?
- Decision: What was decided?
- Consequences: What are the trade-offs?
- Alternatives: What was rejected and why?

---

## 📋 Memory & Context Management

### Session Start Checklist (MANDATORY)

- [ ] Read AGENTS.MD (global rules)
- [ ] Read .agent/memory/CONTEXT.md (what happened last)
- [ ] Read .agent/memory/TODO.md (pending work)
- [ ] Scan CHANGELOG.md tail (last 50 lines)
- [ ] Check applicable .github/instructions/ (path-specific rules)

### Session End Checklist

- [ ] Update CHANGELOG.md with ALL work done (timestamped)
- [ ] Update .agent/memory/CONTEXT.md (what to know next time)
- [ ] Update .agent/memory/TODO.md (incomplete items)
- [ ] Update ARCHITECTURE.md if structure changed
- [ ] Add ADR to DECISIONS.md if significant decision made
- [ ] Leave clear commit messages (conventional commits)

### Smart Context Loading

```markdown
## Priority Context (always load):
1. copilot-instructions.md — project rules
2. .agent/memory/CONTEXT.md — recent state
3. Path-specific instructions for current task

## On-Demand Context (load when relevant):
4. .copilot/variable-tracker.md — when modifying critical vars
5. .agent/rules/*.md — when autonomy questions arise
6. docs/architecture/*.md — when touching architecture
```

---

## ⚠️ Project Critical Rules (from copilot-instructions.md)

- **commission_rate = 0.0007** — never change
- **FallbackEngineV4** — gold standard engine
- **DATA_START_DATE = 2025-01-01** — import from database_policy.py
- **9 timeframes only**: 1, 5, 15, 30, 60, 240, D, W, M

---

## 🛡️ Safety

### Auto-execute: file reads, edits, git add/commit, pytest, ruff, grep

### Ask first: git push, pip install, rm -rf, DB migrations, .env changes

### Never: curl unknown URLs, sudo, DROP TABLE, registry edits

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
black .                    # Code formatting
isort .                    # Import sorting

# Git (except push to main/master)
git add                    # Staging changes
git commit                 # Committing (with good messages)
git diff, log, status      # Read operations
git checkout -b            # Creating branches
git merge                  # Local merges
git pull, fetch            # Updating

# Docker
docker-compose up/down/logs
docker build, run, exec

# Database (read-only)
sqlite3, psql (read queries)

# File operations
mkdir, touch               # Creating files/dirs
mv, cp                     # Moving/copying within workspace
cat, head, tail, less      # Reading
find, grep, rg             # Searching

# Code Quality & Analysis
cProfile, memory_profiler  # Profiling
pytest --cov               # Coverage
ruff check --fix .         # Auto-fix linting
```

### Ask Before (Moderate Risk) ⚠️

```powershell
git push origin main/master # Production push
git reset --hard            # Hard reset
git rebase                  # Rebasing
rm -rf, del /s              # Recursive delete
DROP TABLE, TRUNCATE        # Data loss
ALTER TABLE                 # Schema changes
pip install <new>           # New dependencies
Modifying .gitignore        # Git config
.env modifications          # Environment changes
```

### Never Auto-Execute 🚫

```powershell
curl/wget to unknown URLs
sudo, runas /admin
Format-Volume, diskpart
Registry modifications
DROP DATABASE
```

---

## 🚀 Advanced Tool Orchestration

### Parallel Tool Usage Strategy

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
1. grep_search for function/class names → find definitions
2. list_code_usages → find all callers/importers
3. file_search with glob patterns → find by naming convention
4. semantic_search → when you don't know exact names
5. read_file on __init__.py → understand module structure
```

---

## 🔍 Advanced Debugging Protocol

### Systematic Debug Flow

1. **REPRODUCE**: Understand the exact error/behavior
2. **HYPOTHESIZE**: Form 2-3 theories about root cause
3. **NARROW**: Use binary search to isolate the issue
4. **ROOT CAUSE**: Identify the exact line/condition
5. **FIX**: Implement minimal change
6. **VERIFY**: Run tests + manual verification
7. **PREVENT**: Add test for this specific case

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

## 📊 Performance Profiling

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

## 🧪 Testing Standards

### Smart Test Selection

```markdown
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

## 📝 Documentation Standards

### Code Documentation

```python
def function_name(param: Type) -> ReturnType:
    """Brief description.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this happens
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

## 🏁 Innovation & Experimentation

You are ENCOURAGED to:

- Analyze codebase for performance bottlenecks
- Suggest architectural refactoring
- Identify security vulnerabilities
- Propose modern library upgrades
- Create proof-of-concepts in `.agent/experiments/`

---

## ✅ Self-Check Before Completing

| Check          | Question                             |
| -------------- | ------------------------------------ |
| ✅ Goal met?   | Did exactly what was asked?          |
| ✅ Tested?     | All tests passing?                   |
| ✅ Documented? | CHANGELOG, comments, docstrings?     |
| ✅ Clean?      | No lint errors, no type errors?      |
| ✅ Context?    | Enough info for next session?        |
| ✅ Secure?     | No secrets, no injection vectors?    |
| ✅ Complete?   | No half-done changes or broken refs? |

---

_Version: 3.1 — Cleaned up from merged v2.0/v3.0, removed duplicate content_
_Models: Claude Sonnet 4, Claude Opus 4_
_Last Updated: 2026-02-14_
