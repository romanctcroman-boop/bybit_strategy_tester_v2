# GSD Checkpoints

## Checkpoint Types

### checkpoint:decision

Copilot needs a user decision before proceeding.

**Format:**

```xml
<task type="checkpoint:decision" gate="blocking">
  <decision>Which optimizer to use?</decision>
  <context>Walk-forward needs an optimizer. Two viable options.</context>
  <options>
    <option id="bayesian"><name>Bayesian (Optuna)</name><pros>Smart search</pros><cons>Complex setup</cons></option>
    <option id="grid"><name>Grid Search</name><pros>Simple, exhaustive</pros><cons>Slow for many params</cons></option>
  </options>
  <resume-signal>Select: bayesian or grid</resume-signal>
</task>
```

### checkpoint:human-verify

User needs to visually or manually verify something.

**Rules:**

1. Copilot STARTS the dev server BEFORE presenting the checkpoint
2. User ONLY visits URLs — never runs CLI commands
3. Resume with "approved" or description of issues

**Format:**

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Strategy Builder UI — server at http://localhost:8000</what-built>
  <how-to-verify>Visit http://localhost:8000/frontend/strategy-builder.html. Check: parameter form renders, backtest runs, chart displays.</how-to-verify>
  <resume-signal>Type "approved" or describe issues</resume-signal>
</task>
```

### checkpoint:human-action

User must do something Copilot literally cannot.

**Only for:**

- External account creation (Bybit API key)
- Secrets that Copilot doesn't have access to
- Physical verification (hardware)

**NOT for:**

- Package installs → Copilot can run pip/npm
- File creation → Copilot can create files
- CLI commands → Copilot can run terminal commands

## Checkpoint Behavior in Plans

- Plan runs tasks until checkpoint
- At checkpoint: agent pauses and reports details
- User responds
- Agent resumes from checkpoint

## Ordering Rule

Place checkpoints AFTER the automation they verify:

```
✅ Task 1: Build the feature (auto)
✅ Task 2: Start server (auto)
✅ Task 3: Verify feature works (checkpoint:human-verify)

❌ Task 1: Verify feature works (checkpoint — nothing to verify yet!)
❌ Task 2: Build the feature (auto)
```
