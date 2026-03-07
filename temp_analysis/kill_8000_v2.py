"""Kill port 8000 and write result to file."""

import subprocess
import time

out_lines = []

result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="cp1251", errors="replace")

pids = set()
for line in result.stdout.splitlines():
    if ":8000" in line:
        out_lines.append(f"NETSTAT: {line.strip()}")
        if "LISTEN" in line.upper():
            parts = line.split()
            if parts:
                try:
                    pids.add(int(parts[-1]))
                except ValueError:
                    pass

out_lines.append(f"LISTEN PIDs: {pids}")

for pid in pids:
    r = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True)
    out_lines.append(f"Kill {pid}: {r.stdout.strip()} {r.stderr.strip()}")

time.sleep(2)
result2 = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="cp1251", errors="replace")
still = [line.strip() for line in result2.stdout.splitlines() if ":8000" in line and "LISTEN" in line.upper()]
out_lines.append(f"Still after kill: {still}")

with open(r"D:\bybit_strategy_tester_v2\temp_analysis\kill_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))

print("Written to kill_result.txt")
