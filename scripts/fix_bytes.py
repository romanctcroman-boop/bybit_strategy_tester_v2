# -*- coding: utf-8 -*-
"""
Fix mojibake in backtest_results.js
The file has double-encoded UTF-8 text that appears as garbage.
"""

import sys

def fix_file(filepath):
    # Mapping of corrupted bytes to correct UTF-8
    # These are found by examining the actual byte sequences in the file
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    original_size = len(data)
    
    # Replace byte sequences (mojibake -> correct UTF-8)
    # These patterns were identified from the garbled output
    
    replacements = [
        # Label strings
        (b"\xd0\xa0\xd0\x86\xd0\xa1\xe2\x80\xb0\xd0\xa0\xc2\xb5\xd0\xa0\xc2\xb3\xd0\xa0\xc2\xbe \xd0\xa1\xc3\x91\xd0\xa0\xc2\xb4\xd0\xa0\xc2\xb5\xd0\xa0\xc2\xbb\xd0\xa0\xc2\xbe\xd0\xa0\xc2\xba", b"\xd0\x92\xd1\x81\xd0\xb5\xd0\xb3\xd0\xbe \xd1\x81\xd0\xb4\xd0\xb5\xd0\xbb\xd0\xbe\xd0\xba"),
    ]
    
    for old_bytes, new_bytes in replacements:
        if old_bytes in data:
            data = data.replace(old_bytes, new_bytes)
            print(f"Fixed: {len(old_bytes)} bytes -> {len(new_bytes)} bytes")
    
    # Write back
    with open(filepath, 'wb') as f:
        f.write(data)
    
    print(f"Original size: {original_size}, New size: {len(data)}")
    return True

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    fix_file(filepath)
