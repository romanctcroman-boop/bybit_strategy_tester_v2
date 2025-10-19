import os, sys, importlib, importlib.util
print('cwd=', os.getcwd())
print('sys.path[0]=', repr(sys.path[0]))
print('\nProject root listing:')
for p in sorted(os.listdir('.')):
    print('  ', p)
print('\nfind_spec(backend)=', importlib.util.find_spec('backend'))
print('find_spec(backend.api)=', importlib.util.find_spec('backend.api'))
print('\nTrying import backend:')
try:
    import backend
    print('backend ->', getattr(backend, '__file__', None), 'pkgpath', getattr(backend, '__path__', None))
except Exception as e:
    print('import backend failed:', e)
    import traceback; traceback.print_exc()
print('\nTrying import backend.api.routers.live:')
try:
    import backend.api.routers.live as m
    print('live ->', getattr(m, '__file__', None))
except Exception as e:
    print('import live failed:', e)
    import traceback; traceback.print_exc()
