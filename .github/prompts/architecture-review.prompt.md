---
mode: "agent"
description: "Review and improve system architecture"
---

# Architecture Review Prompt

Conduct a thorough architecture review of a component or the entire system.

## Instructions

### Phase 1: Map Current State

1. **Read** `docs/architecture/` and `.agent/docs/ARCHITECTURE.md`
2. **Map dependencies** between modules:
    ```
    Component A → depends on → Component B
    Component B → depends on → Component C
    ```
3. **Identify coupling** — Which modules are too tightly coupled?
4. **Check layering** — Does data flow correctly through layers?
    ```
    API Router → Service → Repository → Database
    (no skipping layers!)
    ```

### Phase 2: Evaluate

5. **SOLID principles check**:
    - [ ] Single Responsibility — Each class has one job
    - [ ] Open/Closed — Extendable without modification
    - [ ] Liskov Substitution — Subtypes are substitutable
    - [ ] Interface Segregation — No forced unused dependencies
    - [ ] Dependency Inversion — Depend on abstractions
6. **Common issues to find**:
    - Circular imports
    - God classes (>500 lines)
    - God functions (>50 lines)
    - Missing abstractions / interfaces
    - Hardcoded values instead of config
    - Missing error handling boundaries

### Phase 3: Recommend

7. **Prioritize findings** by impact and effort:
   | Finding | Impact | Effort | Priority |
   |---------|--------|--------|----------|
   | Issue 1 | High | Low | P0 |
   | Issue 2 | Medium | Medium | P1 |

8. **Create ADR** for significant changes in `docs/DECISIONS.md`

### Architecture Rules for This Project

```markdown
## Layer Rules:

- API routers MUST NOT contain business logic
- Services MUST NOT import from API layer
- Engines MUST NOT import from Services
- Strategies MUST only implement generate_signals()
- Database queries MUST go through repository pattern

## Critical Constants:

- commission_rate = 0.0007 (IMMUTABLE)
- DATA_START_DATE = 2025-01-01 (IMMUTABLE)
- FallbackEngineV4 = gold standard (REFERENCE)
```

### Output Format

```markdown
## Architecture Review Report

**Scope**: [component/system]
**Date**: [YYYY-MM-DD]

### Findings

1. [Finding with severity]
2. [Finding with severity]

### Recommendations

1. [Recommendation with priority]
2. [Recommendation with priority]

### ADRs Created

- ADR-XXX: [title]
```
