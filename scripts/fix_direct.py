"""
Fix known mojibake patterns by direct string replacement.
All patterns are expressed as Unicode escapes to avoid encoding issues in the source file.
"""

import sys

def fix_mojibake_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"Original length: {len(text)} chars")
    
    # Dictionary of mojibake -> correct text
    # Using Unicode escapes to avoid source file encoding issues
    replacements = {
        # "Капитал стратегии"
        '\u0420\u043b\u0420\u0430\u0420\u0457\u0420\u0451\u0421\u201a\u0420\u0430\u0420\u0273 \u0421\u0403\u0421\u201a\u0421\u0402\u0420\u0430\u0421\u201a\u0420\u0435\u0420\u0456\u0420\u0451\u0420\u0451': '\u041a\u0430\u043f\u0438\u0442\u0430\u043b \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0438',
        
        # "Покупка и удержание"
        '\u0420\u0457\u0420\u0455\u0420\u0454\u0421\u0453\u0420\u0457\u0420\u0454\u0420\u0430 \u0420\u0451 \u0421\u0453\u0420\u0434\u0420\u0435\u0421\u0402\u0420\u0436\u0420\u0430\u0420\u0273\u0420\u0451\u0420\u0435': '\u041f\u043e\u043a\u0443\u043f\u043a\u0430 \u0438 \u0443\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0435',
        
        # "Победы"
        '\u0420\u0457\u0420\u0455\u0420\u0431\u0420\u0435\u0420\u0434\u0421\u2039': '\u041f\u043e\u0431\u0435\u0434\u044b',
        
        # "Убытки"
        '\u0420\u0403\u0420\u0431\u0421\u2039\u0421\u201a\u0420\u0454\u0420\u0451': '\u0423\u0431\u044b\u0442\u043a\u0438',
        
        # "Безубыточность"
        '\u0420\u0411\u0420\u0435\u0420\u0437\u0421\u0453\u0420\u0431\u0421\u2039\u0421\u201a\u0420\u0455\u0421\u2021\u0420\u0273\u0420\u0455\u0421\u0403\u0421\u201a\u0421\u0459': '\u0411\u0435\u0437\u0443\u0431\u044b\u0442\u043e\u0447\u043d\u043e\u0441\u0442\u044c',
        
        # "Всего сделок"
        '\u0420\u0411\u0421\u0403\u0420\u0435\u0420\u0456\u0420\u0455 \u0421\u0403\u0420\u0434\u0420\u0435\u0420\u0273\u0420\u0455\u0420\u0454': '\u0412\u0441\u0435\u0433\u043e \u0441\u0434\u0435\u043b\u043e\u043a',
        
        # Green emoji (file emoji etc are less critical for now)
        '\u0440\u0457\u0437\u0421\u0453': '\U0001F7E2',  # 🟢
        '\u0440\u0457"\u0434': '\U0001F534',  # 🔴
        '\u0440\u0457"\u0404': '\U0001F4C4',  # 📄
        
        # Bullet point
        '\u0432\u2019\u201a\u0421\u0453': '\u2022',
    }
    
    count = 0
    for old, new in replacements.items():
        if old in text:
            occurrences = text.count(old)
            text = text.replace(old, new)
            count += occurrences
            print(f"Replaced {occurrences}x: ... -> {new}")
    
    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    
    print(f"\nTotal replacements: {count}")
    print(f"New length: {len(text)} chars")
    return count

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    fix_mojibake_file(filepath)
