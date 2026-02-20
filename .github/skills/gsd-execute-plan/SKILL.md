<purpose>
Execute a single PLAN.md file: run tasks in order, verify each one, handle checkpoints, create SUMMARY.md when done.
Adapted for Bybit Strategy Tester v2 (Python, FastAPI, pytest, ruff).
</purpose>

<when_to_use>

- Called by `gsd:execute-phase` prompt for each plan in a wave
- Can also be invoked directly for single-plan execution
  </when_to_use>

<required_reading>

- The PLAN.md file being executed
- `.gsd/STATE.md` — current position
- `.gsd/PROJECT.md` — constraints and critical rules
  </required_reading>

<process>

<step name="load_plan" priority="first">
1. Read the PLAN.md file
2. Parse frontmatter: phase, plan, type, wave, depends_on, files_modified, autonomous, must_haves
3. Read all files listed in `files_modified` to understand current state
4. If `depends_on` is not empty, verify those plans have SUMMARY.md files
</step>

<step name="execute_tasks">
For each `<task>` in the plan:

**type="auto":**

1. Read the `<files>` listed
2. Execute the `<action>` — implement the change
3. Run the `<verify>` command
4. Check `<done>` criteria met
5. If verify fails: fix and retry (max 3 attempts)

**type="tdd":**

1. Write the test first (RED — must fail)
2. Run test to confirm it fails
3. Implement minimal code (GREEN — must pass)
4. Refactor if needed (BLUE)

**type="checkpoint:decision":**

1. Present options to user
2. Wait for response
3. Record decision in plan context

**type="checkpoint:human-verify":**

1. Start dev server if needed
2. Present what was built and how to verify
3. Wait for "approved" or issue description
   </step>

<step name="quality_checks">
After ALL tasks complete:
1. `pytest tests/ -v -m "not slow"` — tests pass
2. `ruff check . --fix` — fix linting
3. `ruff format .` — format code
4. Check for commission_rate consistency (must be 0.0007)
5. Check no hardcoded dates (use DATA_START_DATE from config)
</step>

<step name="create_summary">
Create `.gsd/phases/XX-name/{phase}-{plan}-SUMMARY.md`:

```yaml
---
phase: XX-name
plan: YY
subsystem: [primary: engine, api, strategy, metrics, frontend, database, infra]
tags: [tech keywords used]
requires:
  - phase: [prior phase]
    provides: [what it built]
provides:
  - [what this plan delivered]
affects: [downstream phases/components]
tech-stack:
  added: [new libraries/tools]
  patterns: [new patterns established]
key-files:
  created: [new files]
  modified: [changed files]
key-decisions:
  - "Decision: rationale"
patterns-established:
  - "Pattern: description"
duration: Xmin
completed: YYYY-MM-DD
---

# Phase XX Plan YY Summary

One-liner: [Substantive description, e.g., "RSI strategy with divergence detection using pandas_ta"]

## What Was Built
[Concrete deliverables]

## Decisions Made
[Key decisions with rationale]

## Issues Encountered
[Problems and how they were resolved]

## Next Phase Readiness
[What's needed for downstream work]
```

</step>

</process>

<deviation_rules>
Auto-deviate WITHOUT permission for:

- Bug discovered during execution → fix it, note in SUMMARY
- Test reveals edge case → add test + fix
- Import error → fix dependency chain
- Commission rate drift → STOP and report (CRITICAL)

Ask before deviating for:

- Scope expansion beyond plan
- Architecture changes
- New dependency installation
- Changes to unrelated files
  </deviation_rules>
