import os
import sys
import traceback


def main():
    url = os.environ.get("DATABASE_URL")
    print("DATABASE_URL repr:", repr(url))
    if url is None:
        print("DATABASE_URL is not set")
        sys.exit(2)
    try:
        b = url.encode("utf-8")
    except Exception as e:
        print("Error encoding URL to UTF-8:", e)
        b = None
    print("len:", len(url))
    print("utf-8 bytes:", b)
    print("utf-8 hex:", b.hex() if b else None)

    try:
        import psycopg2

        print("\nAttempting psycopg2.connect()")
        conn = psycopg2.connect(url)
        print("connect succeeded:", conn)
        conn.close()
    except Exception:
        print("connect failed:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
