#!/usr/bin/env python
"""Fix the final remaining Mojibake issues in backtest_results.js"""

import os

filepath = r'd:\bybit_strategy_tester_v2\frontend\js\pages\backtest_results.js'

# Read file in binary mode
with open(filepath, 'rb') as f:
    content = f.read()

# Store original for comparison
original = content

# Byte-level replacements
replacements = [
    # En-dash in date range (line 1718)
    (b'\xd0\xb2\xd0\x82\xe2\x80\x9d', b'\xe2\x80\x93'),  # Mojibake -> en-dash
    
    # Orange diamond emoji 🔶 (lines 2935, 2959)
    (b'\xd1\x80\xd1\x9f\xe2\x80\x9d\xc2\xb6', b'\xf0\x9f\x94\xb6'),
    
    # Warning emoji ⚠️ (lines 2937, 2943, 2953)
    (b'\xd0\xb2\xd1\x99\xc2\xa0\xd0\xbf\xd1\x91\xd0\x8f', b'\xe2\x9a\xa0\xef\xb8\x8f'),
    
    # Red circle emoji 🔴 (line 2949)
    (b'\xd1\x80\xd1\x9f\xe2\x80\x9d\xd2\x91', b'\xf0\x9f\x94\xb4'),
]

# Apply all replacements
for old, new in replacements:
    count = content.count(old)
    if count > 0:
        print(f"Replacing {count} occurrence(s) of {old!r} -> {new!r}")
        content = content.replace(old, new)
    else:
        print(f"Pattern not found: {old!r}")

# Write back if changes were made
if content != original:
    with open(filepath, 'wb') as f:
        f.write(content)
    print(f"\n✅ Fixed {len(original) - len(content)} bytes of Mojibake")
else:
    print("\n⚠️ No changes made - patterns not found")
