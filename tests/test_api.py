import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from transfer.models import JobStore

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "x")
    monkeypatch.setenv("LARK_APP_SECRET", "x")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "x")
    monkeypatch.setenv("TEMP_DIR", str(tmp_path))

    # Pre-initialize the store before entering the ASGI transport context
    # (aiosqlite hangs when opened from inside httpx's ASGITransport)
    store = JobStore(str(tmp_path / "test.db"))
    await store.init()

    from transfer.app import create_app
    app = create_app(store=store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await store.close()

async def test_get_root_returns_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

async def test_post_job_returns_job_id(client):
    with patch("transfer.app.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: coro.close() or None
        resp = await client.post("/jobs", data={
            "order_number": "ORD-001",
            "source_url": "https://www.dropbox.com/s/abc/file.tif?dl=0"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data

async def test_get_job_status(client):
    with patch("transfer.app.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: coro.close() or None
        post = await client.post("/jobs", data={
            "order_number": "ORD-002",
            "source_url": "https://www.dropbox.com/s/abc/file.tif?dl=0"
        })
    job_id = post.json()["job_id"]
    resp = await client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("queued", "downloading", "processing", "uploading", "done", "failed")

async def test_get_nonexistent_job_returns_404(client):
    resp = await client.get("/jobs/nonexistent-id")
    assert resp.status_code == 404
