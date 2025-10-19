from backend.api.routers.live import _parse_xpending_item

failures = 0

def assert_eq(a,b):
    global failures
    if a!=b:
        print('ASSERT FAIL:', a, '!=', b)
        failures += 1

# test_parse_list_shape_bytes
try:
    item = [b'1760814457087-0', b'consumer1', b'120000', b'1']
    eid, owner, idle = _parse_xpending_item(item)
    assert_eq(eid, '1760814457087-0')
    assert_eq(owner, 'consumer1')
    assert_eq(type(idle), int)
    assert_eq(idle, 120000)
    print('test_parse_list_shape_bytes OK')
except Exception as e:
    print('test_parse_list_shape_bytes ERROR', e)
    failures += 1

# test_parse_list_shape_mixed
try:
    item = ['1760814457088-0', 'consumer-2', 50000, 2]
    eid, owner, idle = _parse_xpending_item(item)
    assert_eq(eid, '1760814457088-0')
    assert_eq(owner, 'consumer-2')
    assert_eq(idle, 50000)
    print('test_parse_list_shape_mixed OK')
except Exception as e:
    print('test_parse_list_shape_mixed ERROR', e)
    failures += 1

# test_parse_dict_shape_bytes_keys
try:
    item = {b'id': b'1760814457089-0', b'consumer': b'c3', b'idle': b'60000'}
    eid, owner, idle = _parse_xpending_item(item)
    assert_eq(eid, '1760814457089-0')
    assert_eq(owner, 'c3')
    assert_eq(idle, 60000)
    print('test_parse_dict_shape_bytes_keys OK')
except Exception as e:
    print('test_parse_dict_shape_bytes_keys ERROR', e)
    failures += 1

# test_parse_dict_shape_strings
try:
    item = {'id': '1760814457090-0', 'consumer': 'c4', 'idle': 70000}
    eid, owner, idle = _parse_xpending_item(item)
    assert_eq(eid, '1760814457090-0')
    assert_eq(owner, 'c4')
    assert_eq(idle, 70000)
    print('test_parse_dict_shape_strings OK')
except Exception as e:
    print('test_parse_dict_shape_strings ERROR', e)
    failures += 1

# test_parse_unexpected
import traceback
try:
    try:
        _parse_xpending_item(None)
        print('test_parse_unexpected None did NOT raise')
        failures += 1
    except ValueError:
        print('test_parse_unexpected None OK')
    try:
        _parse_xpending_item(123)
        print('test_parse_unexpected int did NOT raise')
        failures += 1
    except ValueError:
        print('test_parse_unexpected int OK')
except Exception as e:
    print('test_parse_unexpected ERROR', e)
    traceback.print_exc()
    failures += 1

print('\nTOTAL FAILURES:', failures)
if failures:
    raise SystemExit(1)
else:
    print('ALL XPENDING PARSER TESTS PASSED')
