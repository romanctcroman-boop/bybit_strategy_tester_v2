import pandas as pd

df = pd.read_csv(r"d:\bybit_strategy_tester_v2\data\eth_30m_cache.csv")
df["time"] = pd.to_datetime(df["timestamp"])

# Look at bars around index 4930-4940
print("Bars 4930-4945:")
print(df.iloc[4930:4945][["time", "open", "high", "low", "close"]].to_string())

print()
print("Bars 13890-13900:")
print(df.iloc[13890:13900][["time", "open", "high", "low", "close"]].to_string())
