#!/usr/bin/env python
"""
Статистика по тестам проекта
"""
import subprocess
import re

test_groups = {
    'Charts & Reports': [
        'tests/test_charts_api.py',
        'tests/test_report_generator.py'
    ],
    'Backend Services': [
        'tests/backend/'
    ],
    'Database Shims': [
        'tests/test_backtest_task.py',
        'tests/test_backtest_task_errors.py',
        'tests/test_backtest_task_nodata.py',
        'tests/test_stale_idempotency.py',
        'tests/test_pydantic_validation.py'
    ],
    'MTF & Engine': [
        'tests/test_mtf_engine.py',
        'tests/test_walk_forward.py'
    ],
    'Tasks': [
        'tests/test_optimize_tasks.py'
    ],
    'Multi-Timeframe Real': [
        'tests/test_multi_timeframe_real.py'
    ],
}

print('=' * 70)
print('TEST SUITE SUMMARY')
print('=' * 70)

total_passed = 0
total_failed = 0
total_errors = 0

for name, paths in test_groups.items():
    cmd = ['py', '-3.13', '-m', 'pytest'] + paths + ['--tb=no', '-q']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        
        # Parse результатов
        passed_match = re.search(r'(\d+)\s+passed', output)
        failed_match = re.search(r'(\d+)\s+failed', output)
        error_match = re.search(r'(\d+)\s+error', output)
        
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        errors = int(error_match.group(1)) if error_match else 0
        
        total_passed += passed
        total_failed += failed
        total_errors += errors
        
        status = '✓' if (failed == 0 and errors == 0 and passed > 0) else ('⚠' if failed > 0 else '✗')
        print(f'{status} {name:30} {passed:3} passed, {failed:2} failed, {errors:2} errors')
        
    except Exception as e:
        print(f'✗ {name:30} ERROR: {str(e)[:30]}')

print('=' * 70)
print(f'TOTAL: {total_passed} passed, {total_failed} failed, {total_errors} errors')
print(f'Pass rate: {total_passed / (total_passed + total_failed + total_errors) * 100:.1f}%' if (total_passed + total_failed + total_errors) > 0 else 'N/A')
print('=' * 70)
