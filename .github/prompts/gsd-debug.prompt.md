---
description: "Start a scientific debugging session. Gather symptoms, form hypotheses, test systematically."
tools: ["search/readFile", "edit/editFiles", "edit/createFile", "search/listDirectory", "search/textSearch", "runCommands/runInTerminal", "runTests", "search/codebase", "usages"]
---

<objective>
Start a scientific debugging session for a reported issue.
Create a debug session file and systematically find root cause.

Use when: Something is broken and needs investigation, not a quick fix.
</objective>

<execution_context>
@.github/agents/gsd-debugger.agent.md
</execution_context>

<context>
Issue description: ${input}
</context>

<process>

<step name="create_session">
Create `.gsd/debug/{slug}.md` with:
- Trigger: verbatim user description
- Status: gathering
- Empty sections for symptoms, hypotheses, evidence, resolution
</step>

<step name="gather_symptoms">
Ask the user (or inspect):
1. What did you expect to happen?
2. What actually happened?
3. Any error messages or stack traces?
4. Can you reproduce it? Steps?
5. When did it start? (after what change?)
</step>

<step name="investigate">
Hand off to @gsd-debugger agent with symptoms.
Agent follows scientific method:
1. Form 2-3 hypotheses
2. Test one at a time
3. Record evidence for/against
4. Track eliminated hypotheses
5. Find root cause
</step>

<step name="resolve">
Once root cause found:
1. Apply minimal fix
2. Run tests to verify
3. Update debug session file with resolution
4. Close session
</step>

</process>

<success_criteria>

- [ ] Debug session file exists in `.gsd/debug/`
- [ ] Root cause identified with evidence chain
- [ ] Fix applied and verified
- [ ] Related tests pass
      </success_criteria>
