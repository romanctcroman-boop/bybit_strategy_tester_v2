"""
Complete mojibake fix for backtest_results.js
Using manual replacements based on known patterns.
"""

import sys

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    original_len = len(text)
    
    # Complete list of replacements (mojibake -> correct Russian)
    # Each tuple: (corrupted, correct)
    replacements = [
        # Donut chart labels
        ("'\u0420\u045f\u0420\u0455\u0420\u00b1\u0420\u00b5\u0420\u0491\u0421\u2039'", "'\u041f\u043e\u0431\u0435\u0434\u044b'"),
        ("'\u0420\u0408\u0420\u00b1\u0421\u2039\u0421\u201a\u0420\u0454\u0420\u0451'", "'\u0423\u0431\u044b\u0442\u043a\u0438'"),
        ("'\u0420'\u0420\u00b5\u0420\u00b7\u0421\u0453\u0420\u00b1\u0421\u2039\u0421\u201a\u0420\u0455\u0421\u2021\u0420\u0405\u0420\u0455\u0421\u0403\u0421\u201a\u0421\u040a'", "'\u0411\u0435\u0437\u0443\u0431\u044b\u0442\u043e\u0447\u043d\u043e\u0441\u0442\u044c'"),
        
        # Center label
        ("'\u0420'\u0421\u0403\u0420\u00b5\u0420\u0456\u0420\u0455 \u0421\u0403\u0420\u0491\u0420\u00b5\u0420\u00bb\u0420\u0455\u0420\u0454'", "'\u0412\u0441\u0435\u0433\u043e \u0441\u0434\u0435\u043b\u043e\u043a'"),
        
        # Waterfall labels
        ("'\u0420\u0406\u0421\u201a\u0420\u0455\u0420\u0456\u0420\u0455 \u0420\u0457\u0421\u0402\u0420\u0451\u0420\u00b1\u0421\u2039\u0420\u00bb\u0421\u040a'", "'\u0418\u0442\u043e\u0433\u043e \u043f\u0440\u0438\u0431\u044b\u043b\u044c'"),
        ("'\u0420\u045e\u0421\u201a\u0420\u0454\u0421\u0402\u0421\u2039\u0421\u201a\u0421\u2039\u0420\u00b5 \u0420\u045f\u0420\u00a0/\u0420\u0408\u0420''", "'\u041e\u0442\u043a\u0440\u044b\u0442\u044b\u0435 \u041f\u0420/\u0423\u0411'"),
        ("'\u0420\u0406\u0421\u201a\u0420\u0455\u0420\u0456\u0420\u0455 \u0421\u0453\u0420\u00b1\u0421\u2039\u0421\u201a\u0420\u0455\u0420\u0454'", "'\u0418\u0442\u043e\u0433\u043e \u0443\u0431\u044b\u0442\u043e\u043a'"),
        ("'\u0420\u045e\u0420\u00b1\u0421\u2030\u0420\u0451\u0420\u00b5 \u0420\u045f\u0420\u00a0/\u0420\u0408\u0420''", "'\u041e\u0431\u0449\u0438\u0435 \u041f\u0420/\u0423\u0411'"),
        
        # Trade distribution labels
        ("'\u0420\u0408\u0420\u00b1\u0421\u2039\u0421\u201a\u0420\u0455\u0420\u0454'", "'\u0423\u0431\u044b\u0442\u043e\u043a'"),
        ("'\u0420\u045f\u0421\u0402\u0420\u0451\u0420\u00b1\u0421\u2039\u0420\u00bb\u0421\u040a'", "'\u041f\u0440\u0438\u0431\u044b\u043b\u044c'"),
        
        # Benchmarking labels
        ("'\u0420\u045f\u0421\u0402\u0420\u0451\u0420\u00b1\u0421\u2039\u0420\u00bb\u0421\u040a \u0420\u0457\u0421\u0402\u0420\u0451 \u0420\u0457\u0420\u0455\u0420\u0454\u0421\u0453\u0420\u0457\u0420\u0454\u0420\u00b5 \u0420\u0451 \u0421\u0453\u0420\u0491\u0420\u00b5\u0421\u0402\u0420\u00b6\u0420\u00b0\u0420\u0405\u0420\u0451\u0420\u0451'", "'\u041f\u0440\u0438\u0431\u044b\u043b\u044c \u043f\u0440\u0438 \u043f\u043e\u043a\u0443\u043f\u043a\u0435 \u0438 \u0443\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0438'"),
        ("'\u0420\u045f\u0421\u0402\u0420\u0451\u0420\u00b1\u0421\u2039\u0420\u00bb\u0421\u040a\u0420\u0405\u0420\u0455\u0421\u0403\u0421\u201a\u0421\u040a \u0421\u0403\u0421\u201a\u0421\u0402\u0420\u00b0\u0421\u201a\u0420\u00b5\u0420\u0456\u0420\u0451\u0420\u0451'", "'\u041f\u0440\u0438\u0431\u044b\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0438'"),
        
        # Chart axis labels
        ("'\u0420\u201d\u0420\u0451\u0420\u00b0\u0420\u0457\u0420\u00b0\u0420\u00b7\u0420\u0455\u0420\u0405'", "'\u0414\u0438\u0430\u043f\u0430\u0437\u043e\u043d'"),
        ("'\u0420\u0162\u0420\u00b5\u0420\u0454\u0421\u0453\u0421\u2030. \u0421\u2020\u0420\u00b5\u0420\u0405\u0420\u00b0'", "'\u0422\u0435\u043a\u0443\u0449. \u0446\u0435\u043d\u0430'"),
        
        # Tooltip labels
        ("'\u0420\u040e\u0420\u0455\u0420\u0406\u0420\u0455\u0420\u0454\u0421\u0453\u0420\u0457\u0420\u0405\u0421\u2039\u0420\u00b5 \u0420\u045f\u0420\u00a0/\u0420\u0408\u0420' '", "'\u0421\u043e\u0432\u043e\u043a\u0443\u043f\u043d\u044b\u0435 \u041f\u0420/\u0423\u0411 '"),
        
        # Emojis
        ("'\u0440\u045f\u045f\u045e'", "'\U0001F7E2'"),  # green
        ("'\u0440\u045f\"\u0491'", "'\U0001F534'"),  # red
        ("'\u0440\u045f\"\u0404'", "'\U0001F4C4'"),  # file
        
        # Bullet
        ("'\u0432\u2019\u201a\u045e'", "'\u2022'"),
        
        # ПР/УБ variations
        ("\u0420\u045f\u0420\u00a0/\u0420\u0408\u0420'", "\u041f\u0420/\u0423\u0411"),
        ("\u0420\u045f\u0420\u00a0/\u0420\u0408\u0420' ", "\u041f\u0420/\u0423\u0411 "),
    ]
    
    count = 0
    for old, new in replacements:
        if old in text:
            occ = text.count(old)
            text = text.replace(old, new)
            count += occ
            # Show what we fixed
            display_new = new[:30] + '...' if len(new) > 30 else new
            print(f"Fixed {occ}x: -> {display_new}")
    
    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    
    print(f"\nTotal: {count} replacements")
    print(f"Size: {original_len} -> {len(text)} chars")
    return count

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    
    # Run multiple passes
    total = 0  
    for i in range(5):
        print(f"\n=== Pass {i+1} ===")
        fixed = fix_file(filepath)
        total += fixed
        if fixed == 0:
            break
    
    print(f"\n=== Grand total: {total} fixes ===")
