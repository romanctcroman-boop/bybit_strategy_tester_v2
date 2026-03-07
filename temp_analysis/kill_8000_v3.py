"""Kill PID 12920 using multiple methods."""

import ctypes
import subprocess
import time

out_lines = []

# Method 1: taskkill with /T
r1 = subprocess.run(
    ["taskkill", "/F", "/T", "/PID", "12920"], capture_output=True, text=True, encoding="cp1251", errors="replace"
)
out_lines.append(f"Method1 taskkill /T: {r1.stdout.strip()} | {r1.stderr.strip()}")

# Method 2: WMIC
r2 = subprocess.run(
    ["wmic", "process", "where", "ProcessId=12920", "delete"],
    capture_output=True,
    text=True,
    encoding="cp1251",
    errors="replace",
)
out_lines.append(f"Method2 wmic: {r2.stdout.strip()} | {r2.stderr.strip()}")

# Method 3: via python os.kill
import os
import signal

try:
    os.kill(12920, signal.SIGTERM)
    out_lines.append("Method3 os.kill SIGTERM: sent")
    time.sleep(1)
    os.kill(12920, signal.SIGKILL)
    out_lines.append("Method3 os.kill SIGKILL: sent")
except ProcessLookupError as e:
    out_lines.append(f"Method3 os.kill: {e}")
except PermissionError as e:
    out_lines.append(f"Method3 os.kill PERMISSION: {e}")

time.sleep(2)
result2 = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="cp1251", errors="replace")
still = [line.strip() for line in result2.stdout.splitlines() if ":8000" in line and "LISTEN" in line.upper()]
out_lines.append(f"Still: {still}")

with open(r"D:\bybit_strategy_tester_v2\temp_analysis\kill_result2.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))
print("Done")
