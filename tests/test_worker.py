import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from transfer.worker import run_job
from transfer.models import JobStore, JobStatus

@pytest.fixture
async def store(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    await store.init()
    yield store
    await store.close()

async def test_run_job_success(store, tmp_path):
    job_id = await store.create_job("ORD-001", "https://www.dropbox.com/s/abc/file.tif?dl=0")

    fake_downloaded = [tmp_path / "file.tif"]
    fake_downloaded[0].write_bytes(b"TIFF")
    fake_processed = tmp_path / "file_flat.tif"
    fake_processed.write_bytes(b"FLAT")

    with patch("transfer.worker.DropboxDownloader") as MockDbox, \
         patch("transfer.worker.ProcessingPipeline") as MockPipeline, \
         patch("transfer.worker.LarkClient") as MockLark:

        MockDbox.return_value.download = AsyncMock(return_value=fake_downloaded)
        MockPipeline.return_value.process = AsyncMock(return_value=fake_processed)
        MockLark.return_value.ensure_folder = AsyncMock(return_value="fldChild")
        MockLark.return_value.upload_file = AsyncMock(return_value="file_tok_123")

        from transfer.config import Settings
        settings = Settings.__new__(Settings)
        settings.lark_app_id = "x"
        settings.lark_app_secret = "x"
        settings.lark_root_folder_token = "fldRoot"
        settings.temp_dir = str(tmp_path)

        await run_job(job_id, store, settings)

    job = await store.get_job(job_id)
    assert job["status"] == JobStatus.DONE.value

async def test_run_job_marks_failed_on_exception(store, tmp_path):
    job_id = await store.create_job("ORD-002", "https://www.dropbox.com/s/abc/file.tif?dl=0")

    with patch("transfer.worker.DropboxDownloader") as MockDbox:
        MockDbox.return_value.download = AsyncMock(side_effect=RuntimeError("Link expired"))
        from transfer.config import Settings
        settings = Settings.__new__(Settings)
        settings.lark_app_id = "x"
        settings.lark_app_secret = "x"
        settings.lark_root_folder_token = "fldRoot"
        settings.temp_dir = str(tmp_path)

        await run_job(job_id, store, settings)

    job = await store.get_job(job_id)
    assert job["status"] == JobStatus.FAILED.value
    assert "Link expired" in job["error"]
