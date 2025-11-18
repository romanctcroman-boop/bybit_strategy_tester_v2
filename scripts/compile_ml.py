import py_compile, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
errors = []
for p in (root / 'backend' / 'ml').glob('*.py'):
    try:
        py_compile.compile(str(p), doraise=True)
    except Exception as e:
        errors.append((p, e))
if errors:
    print('FAIL')
    for p,e in errors:
        print(f'{p}: {e}')
    sys.exit(1)
print('OK')
