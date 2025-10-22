import os
import sys
import traceback

import psycopg2

print("PGCLIENTENCODING=", os.environ.get("PGCLIENTENCODING"))
try:
    conn = psycopg2.connect(
        dbname="test",
        user="test",
        password="test",
        host="127.0.0.1",
        port=5433,
        options="-c client_encoding=UTF8",
    )
    print("connected OK")
    conn.close()
except Exception:
    traceback.print_exc()
    sys.exit(2)
