---
description: Structured approach for complex multi-phase tasks in VS Code Agent Mode
---

# Multi-Phase Task Workflow

Use this workflow when a task requires multiple independent workstreams.

## When to Use

- Complex refactoring across multiple modules
- Simultaneous testing and documentation
- Research + implementation + verification
- Any task requiring 5+ file changes

## Workflow Steps

### Phase 1: Planning

1. Create a TODO list with all subtasks
2. Map file dependencies (which files affect which)
3. Identify safe parallelism (independent changes)

### Phase 2: Execution

4. Execute changes in dependency order:
    - **Layer 1**: Models, constants, base classes
    - **Layer 2**: Services, engines, business logic
    - **Layer 3**: API routers, schemas
    - **Layer 4**: Tests
    - **Layer 5**: Frontend (if affected)
    - **Layer 6**: Documentation

5. Run tests after each layer:

    ```powershell
    .\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
    ```

### Phase 3: Verification

6. Run full test suite
7. Run linting: `ruff check . --fix && ruff format .`
8. Verify imports: `python -c "from backend.api.app import app; print('OK')"`
9. Update CHANGELOG.md with completed items

## Context Handoff

If work spans multiple sessions:

- Update `.agent/memory/CONTEXT.md` with progress
- Document incomplete work in `.agent/memory/TODO.md`
- Note any decisions made in `docs/DECISIONS.md`
