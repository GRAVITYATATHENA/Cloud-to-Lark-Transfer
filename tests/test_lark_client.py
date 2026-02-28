import pytest
import respx
import httpx
from transfer.lark_client import LarkClient

TOKEN_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
FOLDER_URL = "https://open.larksuite.com/open-apis/drive/v1/files/create_folder"
LIST_URL = "https://open.larksuite.com/open-apis/drive/v1/files"

@pytest.fixture
def client():
    return LarkClient(app_id="cli_test", app_secret="secret", root_folder_token="fldRoot")

@respx.mock
async def test_get_token(client):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "tenant_access_token": "tok123", "expire": 7200
    }))
    token = await client.get_access_token()
    assert token == "tok123"

@respx.mock
async def test_ensure_folder_creates_if_missing(client):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "tenant_access_token": "tok123", "expire": 7200
    }))
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "data": {"files": [], "has_more": False}
    }))
    respx.post(FOLDER_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "data": {"token": "fldNew123", "url": "https://lark.example.com/folder"}
    }))
    token = await client.ensure_folder("fldRoot", "ORD-001")
    assert token == "fldNew123"

@respx.mock
async def test_ensure_folder_reuses_existing(client):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "tenant_access_token": "tok123", "expire": 7200
    }))
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "data": {
            "files": [{"name": "ORD-001", "token": "fldExist", "type": "folder"}],
            "has_more": False
        }
    }))
    token = await client.ensure_folder("fldRoot", "ORD-001")
    assert token == "fldExist"
