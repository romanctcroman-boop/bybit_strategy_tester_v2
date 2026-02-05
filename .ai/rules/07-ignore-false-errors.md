# Ignore False Positive Errors

## Errors to IGNORE (Not Real Problems)

These errors/warnings should be **ignored** by Copilot - they are false positives from VS Code extensions or schema issues, not actual code problems:

### 1. PostgreSQL Extension Schema Errors

```text
$ref '/contributes.configuration.properties.pgsql.connections.items' in 'vscode://schemas/settings/folder' can not be resolved.
```

- **Reason**: VS Code PostgreSQL extension schema issue
- **Action**: IGNORE - not a real error

### 2. YAML Schema Validation Warnings

```text
Matches multiple schemas when only one must validate
```

- **Reason**: YAML files matching multiple schema patterns
- **Action**: IGNORE - configuration files work correctly

### 3. JSON Schema Resolution Errors

```text
$ref ... can not be resolved
```

- **Reason**: Extension schema not loading properly
- **Action**: IGNORE - VS Code extension issue, not code problem

### 4. Stale Lint Errors After File Edit

- If lint errors persist after fixing code, the file may need to be re-opened
- **Action**: IGNORE if the fix was applied correctly

## Errors to ALWAYS Fix

These errors are REAL and must be fixed:

| Error Type          | Example                                       | Action               |
| ------------------- | --------------------------------------------- | -------------------- |
| Python syntax       | `SyntaxError`, `IndentationError`             | Fix immediately      |
| Import errors       | `ModuleNotFoundError`                         | Fix import path      |
| Type errors         | `TypeError`, `AttributeError`                 | Fix code logic       |
| Accessibility (axe) | `Select element must have accessible name`    | Add aria-label/title |
| Missing viewport    | `A 'viewport' meta element was not specified` | Add meta viewport    |
| Inline styles       | `CSS inline styles should not be used`        | Move to CSS file     |

## Quick Reference

```text
IGNORE if error contains:
- "$ref ... can not be resolved"
- "pgsql.connections"
- "vscode://schemas"
- Schema validation from extensions

FIX if error is:
- Python/JS/HTML syntax error
- Security issue
- Accessibility violation
- Code logic error
```
