for fname in ["1.csv", "2.csv", "3.csv"]:
    print(f"\n=== {fname} ===")
    try:
        with open(rf"C:\Users\roman\Downloads\{fname}", encoding="utf-8-sig") as f:
            content = f.read()
        for line in content.split("\n"):
            if (
                "run" in line.lower()
                or "drawdown" in line.lower()
                or "макс" in line.lower()
                or "просад" in line.lower()
            ):
                print(f"  {line}")
    except Exception as e:
        print(f"Error: {e}")
