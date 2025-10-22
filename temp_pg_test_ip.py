import sys
import traceback

import psycopg2

try:
    conn = psycopg2.connect(
        dbname="test", user="test", password="test", host="172.17.0.3", port=5432
    )
    print("connected OK to container IP")
    conn.close()
except Exception:
    traceback.print_exc()
    sys.exit(2)
