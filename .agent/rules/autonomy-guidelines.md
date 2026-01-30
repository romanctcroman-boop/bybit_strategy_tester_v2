---
name: autonomy-guidelines
description: Guidelines for autonomous agent operation with safety guardrails
activation: always
priority: HIGH
---

# Autonomy Guidelines

## Command Execution Policy

### Auto-Execute (Safe) ✅

```powershell
# Read-only commands
ls, dir, cat, type, head, tail, find, grep, rg
git status, git log, git diff, git branch, git show

# Development commands
py -3.14 <script>         # All Python scripts
npm run dev/build/test    # Node scripts
python -m pytest          # All test variants
ruff check/format .       # Linting & formatting
mypy, black, isort        # Type checking & formatting

# Git (local operations)
git add                    # Staging changes
git commit                 # Committing (with messages)
git checkout -b            # Creating branches
git merge                  # Local merges
git pull, fetch            # Updating

# File operations
mkdir, touch               # Creating files/dirs
mv, cp                     # Moving/copying (within workspace)
cat, head, tail            # Reading files

# Code Quality
ruff check --fix .         # Auto-fix linting errors
black .                    # Format code
isort .                    # Organize imports
mypy .                     # Type checking

# Testing & Analysis
pytest -v --cov            # Tests with coverage
cProfile, memory_profiler  # Profiling
pytest --tb=short          # Verbose testing

# Documentation
# Updating CHANGELOG.md
# Adding docstrings
# Creating/updating .md files
# Generating code comments

# Refactoring (Safe)
# Renaming variables/functions (non-public)
# Extracting methods/classes
# Removing dead code
# Simplifying conditionals
# Fixing typos
# Organizing code structure

# Bug Fixes (Low Risk)
# Syntax errors
# Type hints
# Import errors
# Linter warnings
# Obvious bugs (with tests)

# File viewing
view_file, view_file_outline, list_dir
```

### Ask First (Moderate Risk) ⚠️

```powershell
# Git (destructive)
git push origin main/master
git reset --hard
git rebase

# Dependencies
npm install <new package>
pip install <new package>
pip uninstall

# File deletion
rm -rf, del /s
Remove-Item -Recurse

# Database (write operations)
DROP TABLE, TRUNCATE
ALTER TABLE (schema changes)
INSERT/UPDATE/DELETE (data modifications)
SQL migrations

# Configuration
Modifying .gitignore
CI/CD config changes
.env modifications
Environment variables

# Production
Deployment commands
Service restarts
Production config changes
```

### Never Auto-Execute (High Risk) 🚫

```powershell
# Destructive
rm -rf, del /s, Format-Volume
DROP TABLE, TRUNCATE

# Remote operations
git push, git reset --hard
curl/wget to unknown URLs

# System changes
sudo, runas /admin
Registry modifications
Service management
```

## Decision Making

### When to Proceed Automatically

- Clear instructions provided
- Task matches existing patterns
- Low risk of data loss
- Easily reversible
- Fixing bugs or errors
- Improving code quality (linting, formatting)
- Adding documentation
- Refactoring non-public code
- Running tests and fixing failures
- Updating CHANGELOG.md
- Creating feature branches
- Safe code improvements (DRY, simplification)

### When to Ask

- Ambiguous requirements
- Multiple valid approaches
- Irreversible actions
- Security implications

### When to Stop

- Missing required information
- Conflicting requirements
- Potential security issue
- Out of scope request

## Error Recovery

### On Error

1. Don't panic
2. Read the full error message
3. Check if it's a known issue (DECISIONS.md)
4. Try obvious fix first
5. Document in CHANGELOG if significant

### Escalation Path

1. Try self-fix (max 2 attempts)
2. Report to user with:
    - What failed
    - Why it might have failed
    - Suggested solutions
