import sys, os
# Ensure repo root is on sys.path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
print('Inserted root into sys.path:', root)
print('sys.path[0]=', sys.path[0])

import pytest
exit_code = pytest.main(['-q', 'tests/test_xpending_parser.py'])
print('pytest exit code:', exit_code)
sys.exit(exit_code)
