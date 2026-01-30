---
description: Run parallel agents for complex multi-phase tasks
---

# Multi-Agent Workflow

Use this workflow when a task requires multiple independent workstreams that can run in parallel.

## When to Use

- Complex refactoring across multiple modules
- Simultaneous testing and documentation
- Research + implementation + verification

## Workflow Steps

// turbo-all

### Phase 1: Planning

1. Define subtasks and assign to agents
2. Create shared context in `.agent/memory/CONTEXT.md`

### Phase 2: Execution

3. Agent 1: Primary implementation
4. Agent 2: Tests and validation
5. Agent 3: Documentation updates

### Phase 3: Integration

6. Merge results from all agents
7. Run integration tests
8. Update `TODO.md` with completed items

## Agent Handoff Protocol

- Each agent updates `CONTEXT.md` with progress
- Use `.agent/experiments/` for intermediate results
- Final agent consolidates and reports
