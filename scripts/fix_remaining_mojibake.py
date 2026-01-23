# -*- coding: utf-8 -*-
"""
FIX: Remaining 2 issues - AI emojis and waterfall dataset labels
"""
import re

file_path = r"d:\bybit_strategy_tester_v2\frontend\js\pages\backtest_results.js"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("=== FIXING REMAINING 2 ISSUES ===\n")

# Correct text
ITOGO_PRIBYL = '\u0418\u0442\u043e\u0433\u043e \u043f\u0440\u0438\u0431\u044b\u043b\u044c'
ITOGO_UBYTOK = '\u0418\u0442\u043e\u0433\u043e \u0443\u0431\u044b\u0442\u043e\u043a'
EMOJI_WARNING = '\u26A0\uFE0F'  # ⚠️
EMOJI_ORANGE = '\U0001F536'  # 🔶
EMOJI_RED = '\U0001F534'  # 🔴

changes = 0
lines = content.split('\n')

for i, line in enumerate(lines):
    original = line
    
    # Fix waterfall 4-column dataset labels (lines 2703, 2714 area)
    if "label: '" in line and i >= 2700 and i <= 2740:
        # Check for broken Итого прибыль
        if 'label:' in line:
            match = re.search(r"label: '([^']+)'", line)
            if match:
                broken_label = match.group(1)
                # Check if it's broken (contains Р at start)
                if broken_label.startswith('\u0420'):
                    # Determine which label based on context
                    # Look at next lines for clues
                    if i < len(lines) - 5:
                        next_lines = ''.join(lines[i:i+5])
                        if 'level0, level1' in next_lines or 'grossProfit' in next_lines:
                            lines[i] = line.replace(broken_label, ITOGO_PRIBYL)
                            changes += 1
                            print(f"Line {i+1}: Fixed 'Итого прибыль' dataset label")
                        elif 'level2, level1' in next_lines or ('grossLoss' in next_lines and 'level1' in next_lines):
                            lines[i] = line.replace(broken_label, ITOGO_UBYTOK)
                            changes += 1
                            print(f"Line {i+1}: Fixed 'Итого убыток' dataset label")
    
    # Fix AI Analysis emojis (lines 2933-2960)
    if i >= 2930 and i <= 2960 and 'insights.push' in line:
        # Fix broken warning emoji
        if '\u0432\u043b ' in line:
            lines[i] = re.sub(r'\u0432\u043b [^\s]+', EMOJI_WARNING, line)
            if lines[i] != original:
                changes += 1
                print(f"Line {i+1}: Fixed warning emoji")
                original = lines[i]
        
        # Fix broken orange diamond emoji
        if '\u0440\u0437"' in line or 'рџ"¶' in line:
            lines[i] = re.sub(r'рџ"¶', EMOJI_ORANGE, line)
            if lines[i] != original:
                changes += 1
                print(f"Line {i+1}: Fixed orange diamond emoji")
                original = lines[i]
        
        # Fix broken red circle emoji
        if '\u0440\u0437"' in line or 'рџ"ґ' in line:
            lines[i] = re.sub(r'рџ"ґ', EMOJI_RED, line)
            if lines[i] != original:
                changes += 1
                print(f"Line {i+1}: Fixed red circle emoji")

if changes > 0:
    content = '\n'.join(lines)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n=== TOTAL: {changes} fixes ===")
else:
    print("\nNo changes made. Scanning for issues...")
    for i, line in enumerate(lines):
        if i >= 2700 and i <= 2740:
            if "label:" in line:
                print(f"Line {i+1}: {repr(line[:60])}...")
        if i >= 2930 and i <= 2960:
            if "insights" in line:
                print(f"Line {i+1}: {line[:60]}...")

print("\nDone!")
