import os, sys, importlib, traceback, importlib.util
print('cwd=', os.getcwd())
print('sys.path[0]=', repr(sys.path[0]))
print('full sys.path:')
for p in sys.path:
    print('  ', repr(p))
print('\nimportlib.util.find_spec(backend)=', importlib.util.find_spec('backend'))
print('importlib.util.find_spec(backend.api)=', importlib.util.find_spec('backend.api'))
try:
    m = importlib.import_module('backend.api.routers.live')
    print('\nimport ok ->', getattr(m, '__file__', None))
except Exception:
    print('\nimport failed:')
    traceback.print_exc()
