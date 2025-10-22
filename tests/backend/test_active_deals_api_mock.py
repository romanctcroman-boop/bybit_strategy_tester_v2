import os, sys, importlib
from fastapi.testclient import TestClient

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

app = importlib.import_module('backend.api.app').app


def test_active_deals_list_with_pagination():
    client = TestClient(app)
    r = client.get('/api/v1/active-deals', params={'limit': 1, 'offset': 0})
    assert r.status_code == 200
    data = r.json()
    assert 'items' in data and 'total' in data
    assert len(data['items']) <= 1


def test_active_deals_actions():
    client = TestClient(app)
    # get one deal id
    r = client.get('/api/v1/active-deals', params={'limit': 10, 'offset': 0})
    assert r.status_code == 200
    deals = r.json()['items']
    assert deals, 'expected at least one mock deal'
    deal_id = deals[0]['id']

    # average adjusts entry price (server-side, if current present)
    ravg = client.post(f'/api/v1/active-deals/{deal_id}/average')
    assert ravg.status_code == 200
    assert ravg.json()['ok'] is True

    # close removes the deal
    rclose = client.post(f'/api/v1/active-deals/{deal_id}/close')
    assert rclose.status_code == 200
    assert rclose.json()['ok'] is True

    # now deal should be gone
    r2 = client.get('/api/v1/active-deals')
    ids = [d['id'] for d in r2.json()['items']]
    assert deal_id not in ids
