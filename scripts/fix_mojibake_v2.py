"""
Fix double-encoded UTF-8 (mojibake) by trying to decode byte sequences as cp1251->utf8.
This handles cases where UTF-8 text was interpreted as Windows-1251 and re-encoded as UTF-8.
"""

import sys
import re

def try_fix_sequence(text):
    """Try to fix a sequence of potentially mojibake text."""
    try:
        # The characteristic of double-encoded UTF-8:
        # - Original UTF-8 bytes were read as if they were Windows-1251 characters
        # - Those "characters" were then encoded as UTF-8
        # To reverse: encode as cp1251 (getting original UTF-8 bytes), then decode as UTF-8
        fixed = text.encode('cp1251', errors='strict').decode('utf-8', errors='strict')
        
        # Sanity check: the fixed text should look like valid Russian
        if any(c.isalpha() for c in fixed):
            return fixed, True
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text, False

def is_mojibake_char(char):
    """Check if a character looks like part of mojibake."""
    code = ord(char)
    # Typical mojibake uses characters in the 0x0400-0x04FF range (Cyrillic block)
    # but in patterns that don't make sense as Russian
    # Also check for common mojibake indicator characters
    if code >= 0x0400 and code <= 0x04FF:
        # Some mojibake-specific characters from double-encoding
        # These are uppercase Cyrillic that appear when lower Latin/Cyrillic is double-encoded
        return char in '\u0420\u0421\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419\u041a\u041b\u041c\u041d\u041e\u041f'
    # Latin1 supplement characters that appear in mojibake
    if code >= 0x00A0 and code <= 0x00FF:
        return True
    # Special characters that appear in emoji mojibake
    if char in '\u0440\u0441\u043f\u045f\u0491\u0451':
        return True
    return False

def fix_mojibake_file(filepath):
    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"Original length: {len(text)} chars")
    
    # Look for sequences that might be mojibake
    fixed_count = 0
    output_parts = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # Check if this looks like the start of a mojibake sequence
        if is_mojibake_char(char):
            # Collect the potential mojibake sequence
            seq_start = i
            while i < len(text) and (is_mojibake_char(text[i]) or 
                                      (text[i] in ' \t' and i + 1 < len(text) and is_mojibake_char(text[i+1])) or
                                      text[i] in '\u2019\u201a\u2020\u2021\u2030\u0192\u02c6\u2039\xab\xbb\u0153'):
                i += 1
            
            seq = text[seq_start:i]
            fixed_seq, was_fixed = try_fix_sequence(seq)
            
            if was_fixed:
                output_parts.append(fixed_seq)
                fixed_count += 1
            else:
                output_parts.append(seq)
        else:
            output_parts.append(char)
            i += 1
    
    fixed_text = ''.join(output_parts)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(fixed_text)
    
    print(f"Fixed {fixed_count} mojibake sequences")
    print(f"New length: {len(fixed_text)} chars")
    return fixed_count

def run_multiple_passes(filepath, max_passes=5):
    """Run multiple passes until no more fixes are found."""
    total_fixed = 0
    for pass_num in range(1, max_passes + 1):
        print(f"\n=== Pass {pass_num} ===")
        fixed = fix_mojibake_file(filepath)
        total_fixed += fixed
        if fixed == 0:
            print("No more fixes needed!")
            break
    print(f"\n=== Total fixed across all passes: {total_fixed} ===")

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    run_multiple_passes(filepath)
