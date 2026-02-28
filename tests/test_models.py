import pytest
import aiosqlite
from transfer.models import JobStatus, JobStore

@pytest.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = JobStore(db_path)
    await store.init()
    yield store
    await store.close()

async def test_create_and_get_job(store):
    job_id = await store.create_job(order_number="ORD-001", source_url="https://drive.google.com/x")
    job = await store.get_job(job_id)
    assert job["order_number"] == "ORD-001"
    assert job["source_url"] == "https://drive.google.com/x"
    assert job["status"] == JobStatus.QUEUED.value

async def test_update_status(store):
    job_id = await store.create_job(order_number="ORD-002", source_url="https://example.com")
    await store.update_status(job_id, JobStatus.DOWNLOADING, progress="10%")
    job = await store.get_job(job_id)
    assert job["status"] == JobStatus.DOWNLOADING.value
    assert job["progress"] == "10%"

async def test_update_error(store):
    job_id = await store.create_job(order_number="ORD-003", source_url="https://example.com")
    await store.update_status(job_id, JobStatus.FAILED, error="Link expired")
    job = await store.get_job(job_id)
    assert job["status"] == JobStatus.FAILED.value
    assert job["error"] == "Link expired"
