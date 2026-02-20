Add an entry to CHANGELOG.md for recent changes.

Usage: /changelog [brief description of change]

Example: /changelog Added Bollinger Squeeze strategy with tests

Steps:
1. Read CHANGELOG.md to understand the current structure and most recent entries
2. Identify the change category:
   - **Added** — new feature, new file, new endpoint
   - **Changed** — modification to existing behaviour
   - **Fixed** — bug fix
   - **Removed** — deleted file or feature
   - **Deprecated** — something that will be removed later
   - **Security** — security fix

3. Write the entry under `## [Unreleased]` with today's date (2026-02-19 format)
4. Format: bold title with date, then bullet list of details including:
   - What changed
   - Why it was changed
   - Which files were affected
   - Any critical constants or patterns involved

5. Edit CHANGELOG.md to insert the new entry (don't overwrite existing entries)

Keep entries factual and precise. The CHANGELOG is the authoritative history of the project.
