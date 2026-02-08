---
description: "TDD Red-Green-Refactor workflow for implementing new features with test-first approach."
mode: agent
---

# TDD Workflow: {{feature_name}}

Implement `{{feature_name}}` using strict Test-Driven Development.

## Phase 1 — 🔴 RED: Write Failing Test

1. Create a test file in `tests/` mirroring the source path
2. Write a test that captures the expected behavior of `{{feature_name}}`
3. Use naming: `test_[what]_[scenario]_[expected]`
4. Use fixtures from `conftest.py` (e.g., `sample_ohlcv`, `mock_adapter`)
5. Run the test — it MUST fail. If it passes, the feature already exists or the test is wrong.

## Phase 2 — 🟢 GREEN: Minimal Implementation

1. Write the MINIMUM code to make the test pass
2. No optimization, no refactoring, no extras
3. Run the test — it MUST pass
4. Run ALL related tests — nothing should break

## Phase 3 — 🔵 REFACTOR: Clean Up

1. Remove duplication
2. Improve naming and readability
3. Extract helpers if needed
4. Run ALL tests — everything must still pass
5. Run `ruff check .` and fix any issues

## Rules

- Commission rate is always 0.0007
- Use FallbackEngineV4 for engine tests
- Never call real Bybit API — always mock
- Coverage target: 80% overall, 95% for engines
