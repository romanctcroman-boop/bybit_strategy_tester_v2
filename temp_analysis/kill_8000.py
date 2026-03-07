"""Kill any process listening on port 8000."""

import subprocess
import sys

# Find PIDs on port 8000
result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="cp1251", errors="replace")

pids = set()
for line in result.stdout.splitlines():
    if ":8000" in line and ("LISTENING" in line or "LISTEN" in line):
        parts = line.split()
        if parts:
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                pass

print(f"Found PIDs on :8000 (LISTEN): {pids}")

for pid in pids:
    kill_result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
    print(f"  Kill PID {pid}: {kill_result.stdout.strip()} {kill_result.stderr.strip()}")

# Verify
import time

time.sleep(2)
result2 = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="cp1251", errors="replace")
still = [l for l in result2.stdout.splitlines() if ":8000" in l and ("LISTENING" in l or "LISTEN" in l)]
print(f"Still on :8000 after kill: {still}")
print("Done.")
