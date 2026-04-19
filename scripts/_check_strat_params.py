import json
import sqlite3

DB = r"d:\bybit_strategy_tester_v2\data.sqlite3"
conn = sqlite3.connect(DB)
for sid in ["9a4d45bc-0f41-484e-bfee-40a15011c729", "5c03fd86-a821-4a62-a783-4d617bf25bc7"]:
    cur = conn.cursor()
    cur.execute("SELECT id, name, timeframe, parameters, builder_blocks FROM strategies WHERE id=?", (sid,))
    row = cur.fetchone()
    if not row:
        print("NOT FOUND:", sid)
        continue
    sid2, name, tf, pr, br = row
    p = json.loads(pr) if isinstance(pr, str) else (pr or {})
    bl = json.loads(br) if isinstance(br, str) else (br or [])
    sltp_block: dict[str, object] = next((b for b in bl if b.get("type") == "static_sltp"), {})
    raw_params = sltp_block.get("params")
    sltp: dict[str, object] = raw_params if isinstance(raw_params, dict) else {}
    print(f"--- {name} ({sid2[:8]}) TF={tf}")
    print(
        f"    commission={p.get('_commission', '?')}  slippage={p.get('_slippage', '?')}  leverage={p.get('_leverage', '?')}  pyramiding={p.get('_pyramiding', '?')}"
    )
    print(f"    TP={sltp.get('take_profit_percent', '?')}%  SL={sltp.get('stop_loss_percent', '?')}%")
    print()
conn.close()
