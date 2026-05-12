import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import server


@pytest.fixture()
def client(tmp_path, monkeypatch):
    funds_path = tmp_path / 'funds.json'
    funds_path.write_text(json.dumps({
        'funds': [
            {'code': '513100', 'name': '国泰纳斯达克100ETF(QDII)'},
            {'code': '888888', 'name': '自定义测试基金', 'isUserAdded': True}
        ],
        'config': {
            'api': {'backendUrl': 'http://127.0.0.1:8088/api/funds', 'requestTimeout': 20000, 'userAgent': 'test'},
            'proxy': [],
            'request': {'proxyTimeout': 3000, 'chunkSize': 20, 'scriptTimeout': 4000},
            'dataSourceUrls': {'eastmoneyApi': '', 'fundDetail': ''},
            'server': {'host': '127.0.0.1', 'port': 8088}
        }
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    monkeypatch.setattr(server, 'Path', Path)
    original_open = open

    def open_patched(path, *args, **kwargs):
      target = Path(path)
      if target == Path(server.__file__).parent / 'data' / 'funds.json':
          return original_open(funds_path, *args, **kwargs)
      return original_open(path, *args, **kwargs)

    monkeypatch.setattr('builtins.open', open_patched)
    monkeypatch.setattr(server.data.funds_loader, 'QDII_FUNDS', [
        {'code': '513100', 'name': '国泰纳斯达克100ETF(QDII)'},
        {'code': '888888', 'name': '自定义测试基金', 'isUserAdded': True}
    ])
    monkeypatch.setattr('data.funds_loader.reload_funds', lambda: None)

    return TestClient(server.app), funds_path


def test_preset_fund_cannot_be_deleted(client):
    test_client, funds_path = client

    response = test_client.delete('/api/fund/513100')
    assert response.status_code == 200
    assert response.json()['success'] is False
    assert '预设基金' in response.json()['message']

    data = json.loads(funds_path.read_text(encoding='utf-8'))
    codes = [fund['code'] for fund in data['funds']]
    assert '513100' in codes


def test_user_added_fund_can_be_deleted(client):
    test_client, funds_path = client

    response = test_client.delete('/api/fund/888888')
    assert response.status_code == 200
    assert response.json()['success'] is True

    data = json.loads(funds_path.read_text(encoding='utf-8'))
    codes = [fund['code'] for fund in data['funds']]
    assert '888888' not in codes
