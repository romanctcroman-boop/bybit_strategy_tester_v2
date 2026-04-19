#!/usr/bin/env python3
"""
Windows toast notification hook for Claude Code.
Fires on Notification event (idle_prompt) — when Claude finishes a long task
and is waiting for the next prompt.

Input: JSON via stdin with hook_event_name and notification_type fields.
"""

import json
import subprocess
import sys


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        data = {}

    notification_type = data.get("notification_type", "")

    # Only notify when Claude is idle (finished a task), not mid-permission-prompt
    if notification_type not in ("idle_prompt", ""):
        sys.exit(0)

    # Build a readable message
    hook_event = data.get("hook_event_name", "Notification")
    title = "Claude Code"
    message = "Claude is done — ready for your next prompt"
    if notification_type == "permission_prompt":
        message = "Claude needs your approval"

    # Windows balloon tip via PowerShell (non-blocking, auto-dismisses after 5s)
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $True; "
        f"$n.ShowBalloonTip(5000, '{title}', '{message}', "
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Milliseconds 500; "
        "$n.Dispose()"
    )

    try:
        subprocess.run(
            ["powershell.exe", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Not on Windows or PowerShell unavailable — silently skip
        pass


if __name__ == "__main__":
    main()
