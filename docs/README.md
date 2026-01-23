# Documentation Index

This directory contains all project documentation organized by category.

## Quick Links

| Document                                         | Description                      |
| ------------------------------------------------ | -------------------------------- |
| [../README.md](../README.md)                     | Project overview and quick start |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md)         | Command cheat sheet              |
| [api/README.md](api/README.md)                   | API documentation                |
| [architecture/README.md](architecture/README.md) | System architecture              |

## Documentation Structure

```
docs/
├── api/                     # API documentation
│   ├── README.md            # API overview
│   ├── endpoints.md         # Endpoint reference
│   └── examples.md          # Usage examples
│
├── architecture/            # Architecture documentation
│   ├── README.md            # Architecture overview
│   ├── ENGINE_ARCHITECTURE.md
│   ├── ENGINE_PARITY.md
│   └── STRATEGIES_PROCESS_FLOW.md
│
├── guides/                  # User guides
│   ├── QUICKSTART.md        # Getting started
│   ├── DEPLOYMENT.md        # Deployment guide
│   └── TROUBLESHOOTING.md   # Common issues
│
├── reference/               # Reference documentation
│   ├── TRADINGVIEW_METRICS_REFERENCE.md
│   ├── TRADINGVIEW_METRICS_MAPPING.md
│   └── CIRCUIT_BREAKER_RUNBOOK.md
│
├── ai/                      # AI agent documentation
│   ├── AI_AGENT_SYSTEM_DOCUMENTATION.md
│   ├── AI_AGENT_COMPARISON_WITH_FRAMEWORKS.md
│   └── AI_AGENT_EVOLUTION_PLAN.md
│
└── archive/                 # Historical documentation
    └── (archived files)
```

## Standards

All documentation follows [Google Developer Documentation Style Guide](https://developers.google.com/style).

### Key Principles

1. **Be concise** — Use short sentences and paragraphs
2. **Use active voice** — "The system processes" not "is processed by"
3. **Address the reader** — Use "you" instead of "the user"
4. **Use present tense** — "The API returns" not "will return"
5. **Format consistently** — Use proper Markdown formatting

### Document Template

```markdown
# Title

Brief description of what this document covers.

## Overview

High-level explanation.

## Prerequisites

What you need before starting.

## Steps

1. First step
2. Second step

## Examples

Code examples and usage.

## See Also

- [Related Document](link.md)
```
