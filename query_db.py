import json
import sqlite3

DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Step 1: List all tables
print("=" * 60)
print("STEP 1: ALL TABLES")
print("=" * 60)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
for t in tables:
    print(f"  {t[0]}")

# Step 2: List columns for each table
print("\n" + "=" * 60)
print("STEP 2: TABLE COLUMNS")
print("=" * 60)
for t in tables:
    table_name = t[0]
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = cursor.fetchall()
    print(f"\n  Table: {table_name}")
    for col in cols:
        print(f"    [{col['cid']}] {col['name']} ({col['type']})")

# Step 3: Find strategy named "Strategy_MACD_04"
print("\n" + "=" * 60)
print("STEP 3: STRATEGY 'Strategy_MACD_04'")
print("=" * 60)

# Try the strategies table
strategy_id = None
for t in tables:
    table_name = t[0]
    if "strateg" in table_name.lower():
        try:
            cursor.execute(f"SELECT * FROM {table_name} WHERE name LIKE '%MACD_04%' OR name LIKE '%Strategy_MACD_04%'")
            rows = cursor.fetchall()
            if rows:
                print(f"\nFound in table: {table_name}")
                for row in rows:
                    d = dict(row)
                    strategy_id = d.get("id")
                    for k, v in d.items():
                        if v is not None and str(v) != "":
                            val_str = str(v)
                            if len(val_str) > 500:
                                val_str = val_str[:500] + "... [TRUNCATED]"
                            print(f"  {k}: {val_str}")
                    print()
        except Exception as e:
            print(f"  Error querying {table_name}: {e}")

# Also search all tables
if strategy_id is None:
    print("Searching all tables for Strategy_MACD_04...")
    for t in tables:
        table_name = t[0]
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            cols = cursor.fetchall()
            col_names = [c["name"] for c in cols]
            if "name" in col_names:
                cursor.execute(f"SELECT * FROM {table_name} WHERE name LIKE '%MACD_04%'")
                rows = cursor.fetchall()
                if rows:
                    print(f"\nFound in table: {table_name}")
                    for row in rows:
                        d = dict(row)
                        strategy_id = d.get("id")
                        for k, v in d.items():
                            val_str = str(v)
                            if len(val_str) > 300:
                                val_str = val_str[:300] + "..."
                            print(f"  {k}: {val_str}")
        except Exception:
            pass

# Step 4: Find all backtests for this strategy
print("\n" + "=" * 60)
print("STEP 4: BACKTESTS FOR Strategy_MACD_04")
print("=" * 60)

backtest_rows = []
for t in tables:
    table_name = t[0]
    if "backtest" in table_name.lower():
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            cols = cursor.fetchall()
            col_names = [c["name"] for c in cols]
            print(f"\n  Backtest table: {table_name}, columns: {col_names}")

            # Try to find by strategy_id
            if strategy_id and "strategy_id" in col_names:
                cursor.execute(f"SELECT * FROM {table_name} WHERE strategy_id = ?", (strategy_id,))
                rows = cursor.fetchall()
                print(f"  Rows with strategy_id={strategy_id}: {len(rows)}")
                backtest_rows.extend([(table_name, dict(row)) for row in rows])

            # Also try searching by strategy name in any text columns
            for col in col_names:
                if col in ("strategy_name", "name", "config", "parameters", "result"):
                    try:
                        cursor.execute(f"SELECT * FROM {table_name} WHERE {col} LIKE '%MACD_04%'")
                        rows = cursor.fetchall()
                        if rows:
                            print(f"  Found {len(rows)} rows via column '{col}'")
                            backtest_rows.extend([(table_name, dict(row)) for row in rows])
                    except:
                        pass
        except Exception as e:
            print(f"  Error: {e}")

# Step 5: Print full backtest results
print("\n" + "=" * 60)
print("STEP 5: FULL BACKTEST RESULTS")
print("=" * 60)

seen_ids = set()
for table_name, row in backtest_rows:
    row_id = row.get("id", id(row))
    if row_id in seen_ids:
        continue
    seen_ids.add(row_id)

    print(f"\n--- Backtest ID: {row.get('id')} (from table: {table_name}) ---")
    for k, v in row.items():
        if v is None:
            continue
        val_str = str(v)
        # Try to pretty-print JSON fields
        if isinstance(v, str) and len(v) > 10 and (v.startswith("{") or v.startswith("[")):
            try:
                parsed = json.loads(v)
                val_str = json.dumps(parsed, indent=2)
                print(f"\n  [{k}]:")
                print(val_str)
                continue
            except:
                pass
        if len(val_str) > 2000:
            print(f"\n  [{k}] (first 2000 chars):")
            print(val_str[:2000])
            print("  ... [TRUNCATED - full length:", len(val_str), "]")
        else:
            print(f"  {k}: {val_str}")

conn.close()
print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
