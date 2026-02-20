<purpose>
Verify that a completed phase achieves its goal.
Uses goal-backward verification: check must_haves, not just task completion.
</purpose>

<when_to_use>

- After all plans in a phase are executed
- Called by `gsd:verify-work` prompt
- Called by `gsd:execute-phase` as final step
  </when_to_use>

<required_reading>

- All PLAN.md files for the phase (for must_haves)
- All SUMMARY.md files (for what was built)
- `.gsd/ROADMAP.md` (for phase goal)
  </required_reading>

<process>

<step name="gather_criteria">
1. Collect `must_haves` from all PLAN.md frontmatters
2. Merge truths, artifacts, key_links across all plans
3. If no must_haves, derive from ROADMAP.md phase goal
</step>

<step name="verify_truths">
For each truth (observable behavior):
1. Find code that implements it
2. Run test that exercises it (if exists)
3. Verify it's not a stub
4. Record: ✓ VERIFIED / ✗ FAILED with evidence
</step>

<step name="verify_artifacts">
For each artifact:
1. Check EXISTS — file at path
2. Check SUBSTANTIVE — not empty, not placeholder
3. Check EXPORTS — expected items exported (if specified)
4. Check CONTAINS — required patterns present (if specified)
5. Check MIN_LINES — minimum size (if specified)
</step>

<step name="verify_key_links">
For each key_link:
1. Open `from` file
2. Search for connection to `to` using `pattern`
3. Verify it's real code (not commented out)
4. Record: ✓ WIRED / ✗ NOT WIRED with details
</step>

<step name="scan_anti_patterns">
In all files_modified across all plans:
1. Search for `# TODO`, `# FIXME`, `# HACK`
2. Search for `pass` as only function body
3. Search for `raise NotImplementedError`
4. Search for `print()` (should be `logger`)
5. Search for hardcoded commission rates != 0.0007
6. Search for hardcoded dates (should use DATA_START_DATE)
</step>

<step name="automated_checks">
Run:
1. `pytest tests/ -v` — all pass
2. `ruff check .` — clean
3. `ruff format . --check` — formatted
4. `grep -rn "commission" backend/ | grep -v "0.0007" | grep -v "#"` — no drift
</step>

<step name="generate_report">
Create `.gsd/phases/XX-name/{phase}-VERIFICATION.md`:

Status: passed | gaps_found | human_needed

Include all evidence tables.
If gaps_found: generate recommended fix plans.
</step>

</process>

<severity_levels>

- 🛑 Blocker: Prevents goal achievement, MUST fix before proceeding
- ⚠️ Warning: Incomplete but doesn't block, should fix
- ℹ️ Info: Notable observation, not problematic
  </severity_levels>
