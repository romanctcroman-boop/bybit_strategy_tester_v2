import pytest
from backend.api.routers.live import _parse_xpending_item


def test_parse_list_shape_bytes():
    item = [b'1760814457087-0', b'consumer1', b'120000', b'1']
    eid, owner, idle = _parse_xpending_item(item)
    assert eid == '1760814457087-0'
    assert owner == 'consumer1'
    assert isinstance(idle, int) and idle == 120000


def test_parse_list_shape_mixed():
    item = ['1760814457088-0', 'consumer-2', 50000, 2]
    eid, owner, idle = _parse_xpending_item(item)
    assert eid == '1760814457088-0'
    assert owner == 'consumer-2'
    assert idle == 50000


def test_parse_dict_shape_bytes_keys():
    item = {b'id': b'1760814457089-0', b'consumer': b'c3', b'idle': b'60000'}
    eid, owner, idle = _parse_xpending_item(item)
    assert eid == '1760814457089-0'
    assert owner == 'c3'
    assert idle == 60000


def test_parse_dict_shape_strings():
    item = {'id': '1760814457090-0', 'consumer': 'c4', 'idle': 70000}
    eid, owner, idle = _parse_xpending_item(item)
    assert eid == '1760814457090-0'
    assert owner == 'c4'
    assert idle == 70000


def test_parse_unexpected():
    with pytest.raises(ValueError):
        _parse_xpending_item(None)
    with pytest.raises(ValueError):
        _parse_xpending_item(123)
