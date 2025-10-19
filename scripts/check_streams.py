"""Check Redis streams in local Redis for development.

Usage (PowerShell):
  . .\.venv\Scripts\Activate.ps1
  python scripts\check_streams.py --redis redis://localhost:6379/0 --count 5
"""
import argparse
import redis

parser = argparse.ArgumentParser()
parser.add_argument('--redis', default=None)
parser.add_argument('--count', type=int, default=5)
args = parser.parse_args()

redis_url = args.redis or ("redis://localhost:6379/0")

r = redis.Redis.from_url(redis_url, decode_responses=True)

keys = r.keys('stream:*')
print('Found stream keys:', keys)

for k in keys:
    print('\nStream:', k)
    try:
        items = r.xrevrange(k, count=args.count)
        if not items:
            print('  (no entries)')
        for entry_id, fields in items:
            print('  id=', entry_id)
            for f,v in fields.items():
                print('    ', f, ':', v[:400])
    except Exception as e:
        print('  Error reading stream', e)
