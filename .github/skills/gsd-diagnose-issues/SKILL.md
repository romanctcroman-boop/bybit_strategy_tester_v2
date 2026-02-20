<purpose>
Diagnose issues found during verification or UAT.
Spawns parallel debug investigations, returns root causes and fix suggestions.
</purpose>

<when_to_use>

- When verification report has gaps_found
- When UAT reveals issues
- When multiple related bugs need systematic investigation
  </when_to_use>

<required_reading>

- Verification report or UAT with gaps
- Related PLAN.md and SUMMARY.md files
  </required_reading>

<process>

<step name="triage_gaps">
1. Read all gaps from verification report or UAT
2. Categorize by severity (Blocker → Warning → Info)
3. Group related gaps (may share root cause)
4. Prioritize: fix blockers first
</step>

<step name="investigate_each">
For each gap or gap group:
1. Create `.gsd/debug/{slug}.md` session file
2. Use @gsd-debugger methodology:
   - Gather symptoms from verification evidence
   - Form hypotheses
   - Test systematically
   - Record root cause
3. Suggest minimal fix
</step>

<step name="compile_results">
Update verification/UAT file with:
- Root cause for each gap
- Recommended fix (file, change description)
- Estimated fix scope (small/medium/large)
- Whether fix can be autonomous or needs user input
</step>

<step name="generate_fix_plans">
If fixes are needed:
1. Group related fixes into plans (2-3 tasks each)
2. Create fix PLAN.md files: `{phase}-{plan+N}-PLAN.md`
3. Mark as `type: execute` with `autonomous: true`
4. Include verification criteria to prevent regression
</step>

</process>

<domain_patterns>
Common root causes in this project:

- **Metric drift**: Formula changed or edge case not handled → compare with TradingView
- **Signal misalignment**: Off-by-one in candle indexing → check iloc vs loc
- **Commission error**: Rate changed somewhere → grep all commission references
- **Async bugs**: SQLite in async context without `asyncio.to_thread`
- **Data gaps**: Missing data before DATA_START_DATE → check date filters
- **Type mismatches**: Strategy returns wrong dtype → check signal column type
  </domain_patterns>
