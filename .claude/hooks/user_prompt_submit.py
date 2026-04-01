#!/usr/bin/env python3
"""
UserPromptSubmit hook — injects a reminder when the user mentions commission
without "0.0007" in the same prompt. Non-blocking.

Output: JSON with systemMessage to inject into Claude's context.
"""

import json
import re
import sys


COMMISSION_PATTERN = re.compile(r"\bcommission\b", re.IGNORECASE)
CORRECT_VALUE_PATTERN = re.compile(r"0\.0007")


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    # Only fire when "commission" is mentioned without "0.0007"
    if COMMISSION_PATTERN.search(prompt) and not CORRECT_VALUE_PATTERN.search(prompt):
        output = {
            "continue": True,
            "systemMessage": (
                "REMINDER: commission_value = 0.0007 (0.07%) — NEVER change without explicit approval. "
                "12+ files depend on this for TradingView parity. "
                "Exceptions (legacy only): optimize_tasks.py, ai_backtest_executor.py"
            ),
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
