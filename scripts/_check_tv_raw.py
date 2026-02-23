
for fname in ["1.csv", "2.csv"]:
    print(f"\n=== {fname} ===")
    try:
        with open(rf"C:\Users\roman\Downloads\{fname}", encoding="utf-8-sig") as f:
            content = f.read()
        print("First 500 chars:", repr(content[:500]))
        print("Lines:", content.count("\n"))
    except Exception as e:
        print(f"Error: {e}")
