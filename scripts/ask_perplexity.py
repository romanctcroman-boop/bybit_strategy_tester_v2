import os
import sys
import requests
import json

# Set API key
api_key = "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"

# Question about Windows console encoding issue with Python
question = """
I have a Python FastMCP server that fails to start on Windows with this error:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\\U0001f680' in position 0: 
character maps to <undefined>
```

The error occurs when trying to print Unicode emoji characters (🚀, 📁, ✅, etc.) to Windows console.

**My Python code:**
```python
def main():
    print("=" * 80)
    print("🚀 BYBIT STRATEGY TESTER MCP SERVER v2.0")
    print("=" * 80)
    print(f"\\n📁 Project root: {project_root}")
    # ... more prints with emojis
```

**What I tried (FAILED):**
1. Setting UTF-8 encoding with io.TextIOWrapper:
```python
import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```
But the process still hangs or doesn't output anything when redirected to a file.

**Context:**
- Windows 11, Python 3.13
- Starting process with PowerShell: `Start-Process -RedirectStandardOutput log.txt -RedirectStandardError err.log`
- The MCP server uses stdio transport (reads from stdin, writes to stdout)
- Need the server to start successfully without Unicode encoding errors

**Question:**
What's the BEST way to fix this for Windows console + file redirection that:
1. Allows the server to start without crashing
2. Works with PowerShell file redirection
3. Preserves stdio communication for MCP protocol (JSON-RPC over stdin/stdout)
4. Doesn't break on emoji characters

Should I:
A) Use ASCII-safe characters instead of emojis?
B) Configure Windows console encoding differently?
C) Use a different approach for logging (separate file, not stdout)?
D) Something else?
"""

try:
    response = requests.post(
        'https://api.perplexity.ai/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'sonar',
            'messages': [
                {
                    'role': 'user',
                    'content': question
                }
            ]
        },
        timeout=30
    )
    
    response.raise_for_status()
    result = response.json()
    
    if 'choices' in result and len(result['choices']) > 0:
        answer = result['choices'][0]['message']['content']
        print("\n" + "="*80)
        print("PERPLEXITY AI RESPONSE:")
        print("="*80 + "\n")
        print(answer)
        print("\n" + "="*80)
    else:
        print("Error: Unexpected response format")
        print(json.dumps(result, indent=2))
        
except requests.exceptions.RequestException as e:
    print(f"Request error: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response: {e.response.text}")
except Exception as e:
    print(f"Error: {e}")
