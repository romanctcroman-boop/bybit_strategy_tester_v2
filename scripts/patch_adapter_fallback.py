"""Patch strategy_builder_adapter.py: fix Bug #2 use_fallback diagnostics."""

import sys

fpath = r"d:\bybit_strategy_tester_v2\backend\backtesting\strategy_builder_adapter.py"

with open(fpath, "rb") as f:
    raw = f.read()

old = (
    b"        # Fallback: Look for signal blocks by category ONLY when:\r\n"
    b"        # 1. No main node exists at all, OR\r\n"
    b"        # 2. Main node exists but has NO incoming connections AND produced 0 signals.\r\n"
    b"        # If user wired connections to main node, respect that wiring even if\r\n"
    b"        # it produced 0 signals \xd0\xb2\xd0\x82\xe2\x80\x9d don't silently override with category-based routing.\r\n"
    b"        use_fallback = not main_node_id or (\r\n"
    b"            not has_connections_to_main and entries.sum() == 0 and short_entries.sum() == 0\r\n"
    b"        )\r\n"
    b"\r\n"
    b"        if use_fallback:\r\n"
)

new = (
    b"        # Fallback: Look for signal blocks by category ONLY when:\r\n"
    b"        # 1. No main node exists at all, OR\r\n"
    b"        # 2. Main node exists but has NO incoming connections AND produced 0 signals.\r\n"
    b"        # 3. (Bug #2 fix) Connections exist but ALL blocks produced 0 signals --\r\n"
    b"        #    log diagnostic warning and enable fallback so user is not left with 0 trades.\r\n"
    b"        use_fallback = not main_node_id or (\r\n"
    b"            not has_connections_to_main and entries.sum() == 0 and short_entries.sum() == 0\r\n"
    b"        )\r\n"
    b"\r\n"
    b"        if (\r\n"
    b"            has_connections_to_main\r\n"
    b"            and not use_fallback\r\n"
    b"            and entries.sum() == 0\r\n"
    b"            and short_entries.sum() == 0\r\n"
    b"        ):\r\n"
    b"            _conn_count = sum(\r\n"
    b"                1 for conn in self.connections\r\n"
    b'                if conn.get("target", {}).get("nodeId") == main_node_id\r\n'
    b"            )\r\n"
    b"            logger.warning(\r\n"
    b"                \"[SignalRouting] Strategy '%s': %d connection(s) to main node but \"\r\n"
    b'                "ALL signal series are empty (0 long, 0 short entries). "\r\n'
    b'                "Possible causes: indicator period > data length, wrong port wiring, "\r\n'
    b'                "or block execution error. Enabling category-based fallback routing.",\r\n'
    b"                self.name, _conn_count,\r\n"
    b"            )\r\n"
    b"            use_fallback = True  # Bug #2 fix: don't silently return 0 trades\r\n"
    b"\r\n"
    b"        if use_fallback:\r\n"
)

if old in raw:
    new_raw = raw.replace(old, new, 1)
    with open(fpath, "wb") as f:
        f.write(new_raw)
    print("OK: patched use_fallback (Bug #2)")
    sys.exit(0)
else:
    print("ERROR: pattern not found - already patched or file changed")
    idx = raw.find(b"use_fallback = not main_node_id")
    print(repr(raw[max(0, idx - 200) : idx + 150]))
    sys.exit(1)
