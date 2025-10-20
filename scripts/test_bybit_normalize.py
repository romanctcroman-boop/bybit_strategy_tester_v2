"""Simple test runner to verify Bybit kline normalization.

Run with the project venv python:
  D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe scripts/test_bybit_normalize.py
"""
import importlib
import pprint
import os
import sys


def main():
  # ensure project root is on sys.path so 'backend' package can be imported
  project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
  if project_root not in sys.path:
    sys.path.insert(0, project_root)

  try:
    m = importlib.import_module('backend.services.adapters.bybit')
  except Exception as e:
    print('Failed to import backend.services.adapters.bybit:', e)
    raise
    print('BybitAdapter present:', hasattr(m, 'BybitAdapter'))
    b = m.BybitAdapter()
    print('Adapter instantiated')
    sample = ['1670608800000','17071','17073','17027','17055.5','268611','15.74462667']
    parsed = b._normalize_kline_row(sample)
    print('Parsed sample kline:')
    pprint.pprint(parsed)


if __name__ == '__main__':
    main()
