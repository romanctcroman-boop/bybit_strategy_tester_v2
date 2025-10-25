import os, time, sys
try:
    import psycopg
except Exception as e:
    print("psycopg import failed:", e)
    sys.exit(3)

url = os.environ.get("DATABASE_URL")
deadline = time.time() + 40.0
last_err = None
while time.time() < deadline:
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        sys.exit(0)
    except Exception as e:
        last_err = e
        time.sleep(1.0)
print("DB probe failed:", repr(last_err))
sys.exit(2)
