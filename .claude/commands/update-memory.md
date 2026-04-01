---
name: update-memory
description: Manually sync the Memory Bank files to reflect the current state of the project and session.
argument-hint: "[optional: focus area]"
disable-model-invocation: true
---

Manually sync the Memory Bank files to reflect the current state of the project and session.

Usage: /update-memory [optional: focus area]

Examples:
  /update-memory
  /update-memory "fixed DCA engine bug"
  /update-memory "refactored adapter, split into modules"

Steps:
1. Read all current Memory Bank files to understand existing state:
   - memory-bank/activeContext.md
   - memory-bank/progress.md
   - memory-bank/systemPatterns.md (if architecture changed)

2. Reflect on what was accomplished in this session:
   - What files were changed and why?
   - Were any bugs fixed? Note them in progress.md under ✅
   - Were any new problems discovered? Note in progress.md under ⚠️
   - Did any architecture decisions change? Update systemPatterns.md

3. Update memory-bank/activeContext.md:
   - Set "Последнее обновление" to today's date (2026-03-15 format)
   - Update "Что сделано в этой сессии"
   - Update "Текущий фокус" (what's being worked on NOW)
   - Update "Следующие шаги" (what should happen NEXT session)
   - Update "Открытые вопросы / Блокеры" (anything unresolved)

4. Update memory-bank/progress.md if needed:
   - Move fixed bugs from ⚠️ to ✅
   - Add new known issues
   - Update file size table if major refactoring happened

5. Confirm what was updated and briefly summarize the changes made to Memory Bank.

Rules:
- Keep activeContext.md focused on CURRENT state, not history
- progress.md tracks WHAT IS TRUE NOW, not chronological log
- Don't duplicate info that's already in CLAUDE.md (architecture) or git log (history)
- After major refactoring, also check if systemPatterns.md or techContext.md need updating
- Memory Bank is for ME (future Claude sessions), not for the user to read
