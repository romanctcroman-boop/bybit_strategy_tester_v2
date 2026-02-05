# Session Template

Copy this template at the start of each coding session.

---

## Session #[NUMBER] - [DATE]

**Time:** [HH:MM - HH:MM MSK]
**Goal:** [What you want to accomplish this session]

---

### Pre-Session Checklist

Before starting work:

- [ ] Read `docs/ai-context.md` (restore project context)
- [ ] Check `.copilot/variable-tracker.md` (understand current state)
- [ ] Run tests: `pytest tests/ -v` (all passing?)
- [ ] Review last session log
- [ ] Check TODOs from last session

---

### Session Plan

#### Tasks for This Session

1. [ ] Task 1: [description] (Est: X min)
2. [ ] Task 2: [description] (Est: Y min)
3. [ ] Task 3: [description] (Est: Z min)

**Total estimated time:** [total] minutes
**Priority order:** [1, 2, 3 or different]

#### If Time Permits (Stretch Goals)

- [ ] Stretch 1: [description]
- [ ] Stretch 2: [description]

---

### Work Log

#### [HH:MM] Task 1: [name]

**Action:** [what you're doing]
**Files:** [affected files]
**Status:** 🚧 In progress / ✅ Complete / ❌ Blocked

**Notes:**

- [any important observations]

**Variables modified:**

- [variable name]: [file:line] - [what changed]

#### [HH:MM] Task 2: [name]

**Action:** [what you're doing]
**Files:** [affected files]
**Status:** 🚧 In progress / ✅ Complete / ❌ Blocked

**Notes:**

- [any important observations]

---

### Decisions Made

#### Decision 1: [topic]

**Question:** [what decision was needed]
**Chosen:** [what you decided]
**Alternatives considered:** [other options]
**Rationale:** [why this choice]
**Impact:** [what it affects]

---

### Bugs Encountered

#### Bug 1: [description]

**Error:** [error message or behavior]
**Root cause:** [what was wrong]
**Fix:** [how you fixed it]
**Prevention:** [how to avoid in future]
**Commit:** [commit hash]

---

### Session Summary

**Completed tasks:**

- ✅ [Task 1]
- ✅ [Task 2]
- ⏸️ [Task 3 - partially done]

**Files modified:**

- [file 1] - [changes]
- [file 2] - [changes]

**Tests status:**

- Added: X new tests
- Coverage: Y% → Z%
- All passing: Yes/No

**Time spent:**

- Planned: X minutes
- Actual: Y minutes
- Efficiency: [on track / slower / faster]

---

### For Next Session

**TODO (Priority):**

1. 🔴 High: [task description]
2. 🟡 Medium: [task description]
3. 🟢 Low: [task description]

**Blocked by:**

- [blocker 1] - [what's needed to unblock]

**Context notes:**
[Anything important for next session to know]

---

### Update Tracker

After session:

- [ ] Update `docs/ai-context.md` with session summary
- [ ] Update `.copilot/variable-tracker.md` if variables changed
- [ ] Update `CHANGELOG.md` if significant changes
- [ ] Commit all changes: `git commit -m "Session #[N]: [summary]"`
