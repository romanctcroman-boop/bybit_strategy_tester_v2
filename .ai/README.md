# Unified AI Rules Structure

> **Single Source of Truth for Cursor & GitHub Copilot**

## Overview

This `.ai/` directory contains unified AI rules that synchronize to:

- `.cursor/rules/` - Cursor IDE
- `.github/instructions/` - GitHub Copilot path-specific instructions
- `.github/prompts/` - GitHub Copilot prompts
- `.github/copilot-instructions.md` - GitHub Copilot main instructions

## Directory Structure

```
.ai/
├── README.md                 # This file
├── rules/                    # Core rules (modular)
│   ├── 01-core.md            # Workflow & principles
│   ├── 02-variable-tracking.md
│   ├── 03-tradingview-parity.md
│   ├── 04-code-patterns.md
│   ├── 05-testing.md
│   └── 06-architecture.md
├── path-specific/            # File pattern rules
│   ├── strategies.md         # **/strategies/**/*.py
│   ├── api-connectors.md     # **/adapters/**/*.py
│   ├── backtester.md         # **/backtesting/**/*.py
│   ├── api-endpoints.md      # **/api/**/*.py
│   └── tests.md              # **/tests/**/*.py
├── prompts/                  # Reusable prompts
│   ├── analyze-task.md
│   ├── safe-refactor.md
│   ├── add-strategy.md
│   ├── add-api-endpoint.md
│   ├── debug-session.md
│   └── tradingview-parity-check.md
└── context/                  # Session context
    ├── ai-context.md         # Project state tracking
    └── variable-tracker.md   # Variable safety tracking
```

## Sync Script

Run to synchronize `.ai/` to IDE-specific locations:

```bash
# Preview changes
python scripts/sync-ai-rules.py --dry-run --verbose

# Apply changes
python scripts/sync-ai-rules.py

# Sync only to Cursor
python scripts/sync-ai-rules.py --cursor-only

# Sync only to Copilot
python scripts/sync-ai-rules.py --copilot-only
```

## How It Works

### Cursor

Files from `.ai/rules/` and `.ai/path-specific/` are copied to `.cursor/rules/`.
Cursor also uses native `.cursor/rules/*.mdc` rules (not synced from .ai/). Path comparison and Copilot 2026 features: `docs/ai/CURSOR_COPILOT_SYNC.md`.

### GitHub Copilot

- **Main instructions**: `.ai/rules/*.md` → combined into `.github/copilot-instructions.md`
- **Path-specific**: `.ai/path-specific/*.md` → `.github/instructions/*.instructions.md` (with `applyTo` frontmatter)
- **Prompts**: `.ai/prompts/*.md` → `.github/prompts/*.prompt.md`

## Usage

### Edit Rules

1. Edit files in `.ai/` (source of truth)
2. Run sync script
3. Changes propagate to both IDEs

### Add New Rule

1. Create file in appropriate `.ai/` subdirectory
2. Add to sync mapping if path-specific
3. Run sync script

### Using Prompts

**In Copilot Chat:**

```
/add-strategy
```

**In Cursor:**

```
@rules analyze this task using the analyze-task prompt
```

## Critical Values

These values MUST be consistent across all rules:

| Value         | Setting          | Reason                   |
| ------------- | ---------------- | ------------------------ |
| Commission    | 0.0007 (0.07%)   | TradingView parity       |
| Gold Standard | FallbackEngineV2 | Reference implementation |
| Metrics       | 166              | Full calculation suite   |

## Maintenance

- **Weekly**: Review and update context files
- **Per session**: Update `ai-context.md` with progress
- **After refactor**: Run sync script

---

_Last updated: 2025-01-30_
