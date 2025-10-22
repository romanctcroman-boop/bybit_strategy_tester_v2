import os, sys, importlib
from fastapi.testclient import TestClient

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

app = importlib.import_module('backend.api.app').app


def test_bots_list_pagination():
    client = TestClient(app)
    r = client.get('/api/v1/bots', params={'limit': 2, 'offset': 0})
    assert r.status_code == 200
    data = r.json()
    assert 'items' in data and 'total' in data
    assert len(data['items']) <= 2
    total = data['total']

    # page 2
    r2 = client.get('/api/v1/bots', params={'limit': 2, 'offset': 2})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2['total'] == total


def test_bots_actions_start_stop_delete():
    client = TestClient(app)
    # pick first bot
    r = client.get('/api/v1/bots', params={'limit': 1, 'offset': 0})
    bot = r.json()['items'][0]
    bot_id = bot['id']

    rs = client.post(f'/api/v1/bots/{bot_id}/start')
    assert rs.status_code == 200
    assert rs.json()['ok'] is True

    rt = client.post(f'/api/v1/bots/{bot_id}/stop')
    assert rt.status_code == 200
    assert rt.json()['ok'] is True

    rd = client.post(f'/api/v1/bots/{bot_id}/delete')
    assert rd.status_code == 200
    assert rd.json()['ok'] is True

    # ensure not found afterwards
    rnf = client.get(f'/api/v1/bots/{bot_id}')
    assert rnf.status_code == 404
