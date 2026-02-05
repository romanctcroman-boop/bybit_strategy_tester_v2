"""
Compare Our Engine Trades with TradingView Trades
"""

import pandas as pd

# Load TV export
tv_df = pd.read_csv(r'd:\TV\RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT_2026-01-21 (1).csv')

# Separate entries from exits
entries = tv_df[tv_df['Type'].str.contains('Entry', na=False)].copy()
entries = entries.reset_index(drop=True)

print("="*70)
print("📊 TRADINGVIEW TRADE LIST")
print("="*70)
print(f"Total rows in CSV: {len(tv_df)}")
print(f"Total ENTRIES (trades): {len(entries)}")

# Parse datetime
entries['datetime'] = pd.to_datetime(entries['Date and time'])

print("\n📍 Entries around Trade #24:")
print("-"*70)
for i in range(20, min(30, len(entries))):
    row = entries.iloc[i]
    direction = "LONG" if "long" in row['Type'].lower() else "SHORT"
    print(f"  Trade #{i+1}: {row['datetime']} | {direction} | Entry: ${row['Price USDT']:.2f}")

# Find Trade #24
if len(entries) >= 24:
    trade_24 = entries.iloc[23]  # 0-indexed
    print("\n" + "="*70)
    print("🎯 TRADINGVIEW TRADE #24 DETAILS")
    print("="*70)
    print("  Index:     23 (0-based) / #24")
    print(f"  Type:      {trade_24['Type']}")
    print(f"  Signal:    {trade_24['Signal']}")
    print(f"  DateTime:  {trade_24['datetime']}")
    print(f"  Price:     ${trade_24['Price USDT']:.2f}")

    # Now find corresponding exit
    trade_num = trade_24['Trade #']
    exit_row = tv_df[(tv_df['Trade #'] == trade_num) & (tv_df['Type'].str.contains('Exit', na=False))]
    if not exit_row.empty:
        exit_info = exit_row.iloc[0]
        print("\n  Exit Info:")
        print(f"    Exit Signal: {exit_info['Signal']}")
        print(f"    Exit Time:   {exit_info['Date and time']}")
        print(f"    Exit Price:  ${exit_info['Price USDT']:.2f}")
        print(f"    Net P&L:     ${exit_info['Net P&L USDT']:.2f}")

print("\n" + "="*70)
print("📅 COMPARISON: Our Signal #24 vs TV Trade #24")
print("="*70)
print("""
Our Engine Signal #24:
  Bar Index: 1957
  Datetime:  2025-10-21 06:15:00 UTC
  RSI:       21.45 → 31.62 (clear crossover above 30)
  Close:     $107,985.90
  
TradingView Trade #24:
  DateTime:  2025-10-11 00:45 (10 days earlier!)
  Price:     $110,971.80
  
⚠️ ISSUE: We're comparing different trade sequences!
   - TV trade numbering includes Entry+Exit pairs
   - Our signal might need different counting
""")
