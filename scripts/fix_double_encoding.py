"""Fix double-encoded UTF-8 (mojibake) by detecting and correcting the encoding."""

import sys

def fix_mojibake_file(filepath):
    # Read as bytes
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"Original size: {len(data)} bytes")
    
    # Try to decode as UTF-8 (which is how the mojibake is stored)
    try:
        text = data.decode('utf-8')
    except:
        print("File is not valid UTF-8")
        return
    
    # The problem: Russian text was UTF-8, then interpreted as Windows-1251, then encoded as UTF-8 again
    # To fix: We need to encode as Windows-1251 (reversing the last step), then decode as UTF-8 (fixing the interpretation)
    
    # But we can't do the whole file - only the corrupted parts
    # Let's try character-by-character detection and fixing
    
    # Alternative: Use simple string replacements since we know the patterns
    replacements = {
        # These are the exact strings as they appear in the text view
        '\u0420\u043b\u0420\u0430\u0420\u0457\u0420\u0451\u0421\u201a\u0420\u0431\u0420\u0273 \u0421\u0403\u0421\u201a\u0421\u0402\u0420\u0431\u0421\u201a\u0420\u0435\u0420\u0273\u0420\u0451\u0420\u0451': 'Capitalize strategi',
    }
    
    # Actually, let's try a different approach:
    # Look for the specific byte patterns that represent mojibake
    
    # The string "Капитал стратегии" in UTF-8 is:
    # \xd0\x9a\xd0\xb0\xd0\xbf\xd0\xb8\xd1\x82\xd0\xb0\xd0\xbb \xd1\x81\xd1\x82\xd1\x80\xd0\xb0\xd1\x82\xd0\xb5\xd0\xb3\xd0\xb8\xd0\xb8
    
    # When this is interpreted as Windows-1251 and re-encoded as UTF-8:
    # Each byte becomes a Windows-1251 character, which when UTF-8 encoded becomes 2 bytes
    
    # To reverse: encode the text to Windows-1251 (which will fail for valid UTF-8 text but work for the mojibake),
    # then decode as UTF-8
    
    fixed_count = 0
    output = []
    i = 0
    
    while i < len(text):
        # Try to detect mojibake by looking for characteristic Unicode characters
        # that shouldn't appear in Russian text
        char = text[i]
        
        # These are common mojibake characters that appear when UTF-8 Russian is misinterpreted
        if char in '\u0420\u0421\u0410\u0411\u0412\u0413\u0414\u0415\u0416':
            # This might be mojibake - try to collect a sequence and fix it
            seq_start = i
            seq = []
            while i < len(text) and ord(text[i]) >= 0x0400:  # Cyrillic range
                seq.append(text[i])
                i += 1
            
            seq_text = ''.join(seq)
            try:
                # Try to reverse the double encoding
                fixed = seq_text.encode('cp1251').decode('utf-8')
                output.append(fixed)
                fixed_count += 1
            except:
                # Not mojibake, keep original
                output.append(seq_text)
        else:
            output.append(char)
            i += 1
    
    fixed_text = ''.join(output)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(fixed_text)
    
    print(f"Fixed {fixed_count} mojibake sequences")
    print("Done!")

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/js/pages/backtest_results.js'
    fix_mojibake_file(filepath)
