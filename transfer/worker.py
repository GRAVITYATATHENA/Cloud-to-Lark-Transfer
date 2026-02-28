import shutil
from datetime import datetime, timezone
from pathlib import Path
from transfer.models import JobStore, JobStatus
from transfer.sources import detect_source, SourceType
from transfer.sources.gdrive import GoogleDriveDownloader
from transfer.sources.dropbox_ import DropboxDownloader
from transfer.sources.onedrive import OneDriveDownloader
from transfer.processors import ProcessingPipeline
from transfer.lark_client import LarkClient

async def run_job(job_id: str, store: JobStore, settings) -> None:
    job = await store.get_job(job_id)
    source_url = job["source_url"]
    order_number = job["order_number"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    tmp_dir = Path(settings.temp_dir) / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Download
        await store.update_status(job_id, JobStatus.DOWNLOADING, progress="Downloading files...")
        source_type = detect_source(source_url)
        downloader = _make_downloader(source_type, settings)
        downloaded = await downloader.download(source_url, tmp_dir / "raw")

        # 2. Process
        await store.update_status(job_id, JobStatus.PROCESSING, progress="Processing files...")
        pipeline = ProcessingPipeline()
        processed = []
        for file_path in downloaded:
            result = await pipeline.process(file_path)
            processed.append(result)

        # 3. Upload to LARK
        await store.update_status(job_id, JobStatus.UPLOADING, progress="Uploading to LARK...")
        lark = LarkClient(
            app_id=settings.lark_app_id,
            app_secret=settings.lark_app_secret,
            root_folder_token=settings.lark_root_folder_token,
        )
        order_folder = await lark.ensure_folder(settings.lark_root_folder_token, order_number)
        date_folder = await lark.ensure_folder(order_folder, today)

        for i, file_path in enumerate(processed, 1):
            await store.update_status(
                job_id, JobStatus.UPLOADING,
                progress=f"Uploading file {i}/{len(processed)}: {file_path.name}"
            )
            await lark.upload_file(date_folder, file_path)

        await store.update_status(job_id, JobStatus.DONE, progress="Complete")

    except Exception as e:
        await store.update_status(job_id, JobStatus.FAILED, error=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _make_downloader(source_type: SourceType | None, settings):
    if source_type == SourceType.GOOGLE_DRIVE:
        return GoogleDriveDownloader()
    if source_type == SourceType.DROPBOX:
        return DropboxDownloader()
    if source_type == SourceType.ONEDRIVE:
        return OneDriveDownloader(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            tenant_id=settings.microsoft_tenant_id,
        )
    raise ValueError("Unsupported or unrecognised source URL")
