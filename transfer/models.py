import aiosqlite
from enum import Enum
from datetime import datetime, timezone

class JobStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    UPLOADING = "uploading"
    DONE = "done"
    FAILED = "failed"

class JobStore:
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                order_number TEXT NOT NULL,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress TEXT DEFAULT '',
                error TEXT DEFAULT '',
                lark_folder_url TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def create_job(self, order_number: str, source_url: str) -> str:
        import uuid
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
            (job_id, order_number, source_url, JobStatus.QUEUED.value, "", "", "", now, now)
        )
        await self._db.commit()
        return job_id

    async def get_job(self, job_id: str) -> dict | None:
        async with self._db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: str = "",
        error: str = "",
        lark_folder_url: str = "",
    ):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """UPDATE jobs SET status=?, progress=?, error=?, lark_folder_url=?, updated_at=?
               WHERE id=?""",
            (status.value, progress, error, lark_folder_url, now, job_id)
        )
        await self._db.commit()
