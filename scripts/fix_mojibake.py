#!/usr/bin/env python3
"""Fix mojibake (corrupted Cyrillic encoding) in JavaScript files."""

import sys

def fix_mojibake(filepath):
    """Fix double-encoded UTF-8 text (mojibake) in a file."""
    
    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Replacements map for mojibake -> correct Russian
    replacements = {
        'РљР°РїРёС‚Р°Р» СЃС‚СЂР°С‚РµРіРёРё': 'Капитал стратегии',
        'РџРѕРєСѓРїРєР° Рё СѓРґРµСЂР¶Р°РЅРёРµ': 'Покупка и удержание',
        'РџРѕР±РµРґС‹': 'Победы',
        'РЈР±С‹С‚РєРё': 'Убытки',
        'Р'РµР·СѓР±С‹С‚РѕС‡РЅРѕСЃС‚СЊ': 'Безубыточность',
        'Р'СЃРµРіРѕ СЃРґРµР»РѕРє': 'Всего сделок',
        'РС‚РѕРіРѕ РїСЂРёР±С‹Р»СЊ': 'Итого прибыль',
        'РћС‚РєСЂС‹С‚С‹Рµ РџР /РЈР'': 'Открытые ПР/УБ',
        'РС‚РѕРіРѕ СѓР±С‹С‚РѕРє': 'Итого убыток',
        'РћР±С‰РёРµ РџР /РЈР'': 'Общие ПР/УБ',
        'РЎРѕРІРѕРєСѓРїРЅС‹Рµ РџР /РЈР' ': 'Совокупные ПР/УБ ',
        'РџСЂРёР±С‹Р»СЊ РїСЂРё РїРѕРєСѓРїРєРµ Рё СѓРґРµСЂР¶Р°РЅРёРё': 'Прибыль при покупке и удержании',
        'РџСЂРёР±С‹Р»СЊРЅРѕСЃС‚СЊ СЃС‚СЂР°С‚РµРіРёРё': 'Прибыльность стратегии',
        'РЈР±С‹С‚РѕРє': 'Убыток',
        'РџСЂРёР±С‹Р»СЊ': 'Прибыль',
        'Р"РёР°РїР°Р·РѕРЅ': 'Диапазон',
        'РўРµРєСѓС‰. С†РµРЅР°': 'Текущ. цена',
        'РџР /РЈР' ': 'ПР/УБ ',
        'рџ"„': '📄',
        'рџџў': '🟢',
        'рџ"ґ': '🔴',
        'вЂў': '•',
        'РљРѕРјРёСЃСЃРёСЏ': 'Комиссия',
    }
    
    count = 0
    for old, new in replacements.items():
        if old in content:
            occurrences = content.count(old)
            content = content.replace(old, new)
            count += occurrences
            print(f'Replaced {occurrences}x: "{old[:40]}..." -> "{new}"')
    
    if content != original_content:
        # Write back with explicit UTF-8 encoding
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        print(f'\n✅ Total replacements made: {count}')
        print(f'File saved: {filepath}')
    else:
        print('No replacements needed - file is already correct.')
    
    return count

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    fix_mojibake(filepath)
