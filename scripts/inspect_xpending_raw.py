import redis
import pprint

r = redis.Redis()
stream = 'stream:candles:BTCUSDT:1'
group = 'live_group'
try:
    resp = r.execute_command('XPENDING', stream, group, '-', '+', 50)
    print('XPENDING (raw execute_command) type:', type(resp))
    pprint.pprint(resp)
    print('\nDetailed element info:')
    for i, item in enumerate(resp):
        print(f'[{i}] type={type(item)} repr=')
        pprint.pprint(item)
        if isinstance(item, (list, tuple)):
            print('  element types:', [type(x) for x in item])
        elif isinstance(item, dict):
            print('  dict keys:', list(item.keys()))
        print('---')
except Exception as e:
    print('XPENDING execute_command raised:', repr(e))
