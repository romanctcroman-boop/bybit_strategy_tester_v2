#!/usr/bin/env python3
"""
SessionEnd hook — appends a session-end timestamp to memory-bank/activeContext.md.

Fires on: clear, resume, logout, prompt_input_exit, bypass_permissions_disabled, other
"""

import json
import os
import sys
from datetime import datetime, timezone


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        data = {}

    reason = data.get("reason", "other")
    session_id = data.get("session_id", "unknown")[:8]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        sys.exit(0)

    active_context_path = os.path.join(project_dir, "memory-bank", "activeContext.md")
    if not os.path.exists(active_context_path):
        sys.exit(0)

    note = f"\n<!-- session_end: {ts} | reason={reason} | id={session_id} -->\n"

    try:
        with open(active_context_path, "a", encoding="utf-8") as f:
            f.write(note)
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
