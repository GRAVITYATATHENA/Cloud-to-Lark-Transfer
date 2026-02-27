# Cloud-to-LARK File Transfer Service — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a VPS-hosted Python web app that accepts a customer cloud storage link + order number, downloads the files on the VPS (fast bandwidth), runs a processing pipeline (e.g. TIFF flattening), and uploads results to the correct LARK Drive folder.

**Architecture:** FastAPI app with a background job worker. Jobs are persisted in SQLite. The UI polls `/jobs/{id}` for live status. The app binds only to the Tailscale network interface so it is never reachable from the public internet.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, aiosqlite, gdown (Google Drive), dropbox SDK, httpx + msal (OneDrive), Pillow (TIFF), lark-oapi (LARK Drive API), Jinja2, pytest, respx

---

## Project Structure

```
transfer/
  __init__.py
  config.py          # env-var settings
  models.py          # SQLite job CRUD
  sources/
    __init__.py      # URL detection + base class
    gdrive.py        # Google Drive downloader
    dropbox_.py      # Dropbox downloader
    onedrive.py      # OneDrive/SharePoint downloader
  processors/
    __init__.py      # pipeline runner
    tiff.py          # TIFF layer flattening
  lark_client.py     # LARK Drive auth + folder + upload
  worker.py          # orchestrates download → process → upload
  app.py             # FastAPI routes
templates/
  index.html
tests/
  conftest.py
  test_models.py
  test_sources.py
  test_processors.py
  test_lark_client.py
  test_worker.py
  test_api.py
.env.example
requirements.txt
setup.sh
systemd/transfer.service
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `transfer/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

**Step 1: Create `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
aiosqlite==0.20.0
python-dotenv==1.0.0
pillow==11.0.0
gdown==5.2.0
dropbox==12.0.2
msal==1.31.0
lark-oapi==1.3.4
jinja2==3.1.4
python-multipart==0.0.12

# dev/test
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
anyio==4.6.0
```

**Step 2: Create `.env.example`**

```bash
# LARK
LARK_APP_ID=cli_xxxxxxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LARK_ROOT_FOLDER_TOKEN=fldcnxxxxxxxxxxxxxx

# Google Drive (optional - needed only if customer links require auth)
GOOGLE_API_KEY=

# Dropbox (optional - public shared links work without credentials)
DROPBOX_APP_KEY=
DROPBOX_APP_SECRET=
DROPBOX_REFRESH_TOKEN=

# OneDrive / SharePoint
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=

# App
TEMP_DIR=/tmp/transfer-jobs
HOST=100.x.x.x   # Tailscale IP — set after installing Tailscale
PORT=8000
```

**Step 3: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

**Step 4: Create `transfer/__init__.py`** (empty)

**Step 5: Create `tests/conftest.py`**

```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_path_custom(tmp_path):
    return tmp_path
```

**Step 6: Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without errors.

**Step 7: Commit**

```bash
git add requirements.txt .env.example pytest.ini transfer/__init__.py tests/conftest.py
git commit -m "chore: project scaffolding and dependencies"
```

---

## Task 2: Configuration

**Files:**
- Create: `transfer/config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest
from transfer.config import Settings

def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "secret123")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "fldcnABC")
    s = Settings()
    assert s.lark_app_id == "cli_test"
    assert s.lark_app_secret == "secret123"
    assert s.lark_root_folder_token == "fldcnABC"
    assert s.temp_dir == "/tmp/transfer-jobs"  # default

def test_settings_custom_temp_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("LARK_APP_ID", "x")
    monkeypatch.setenv("LARK_APP_SECRET", "x")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "x")
    monkeypatch.setenv("TEMP_DIR", str(tmp_path))
    s = Settings()
    assert s.temp_dir == str(tmp_path)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'transfer.config'`

**Step 3: Write `transfer/config.py`**

```python
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    lark_app_id: str = field(default_factory=lambda: os.environ["LARK_APP_ID"])
    lark_app_secret: str = field(default_factory=lambda: os.environ["LARK_APP_SECRET"])
    lark_root_folder_token: str = field(default_factory=lambda: os.environ["LARK_ROOT_FOLDER_TOKEN"])
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    dropbox_app_key: str = field(default_factory=lambda: os.getenv("DROPBOX_APP_KEY", ""))
    dropbox_app_secret: str = field(default_factory=lambda: os.getenv("DROPBOX_APP_SECRET", ""))
    dropbox_refresh_token: str = field(default_factory=lambda: os.getenv("DROPBOX_REFRESH_TOKEN", ""))
    microsoft_client_id: str = field(default_factory=lambda: os.getenv("MICROSOFT_CLIENT_ID", ""))
    microsoft_client_secret: str = field(default_factory=lambda: os.getenv("MICROSOFT_CLIENT_SECRET", ""))
    microsoft_tenant_id: str = field(default_factory=lambda: os.getenv("MICROSOFT_TENANT_ID", ""))
    temp_dir: str = field(default_factory=lambda: os.getenv("TEMP_DIR", "/tmp/transfer-jobs"))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

settings = Settings()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/config.py tests/test_config.py
git commit -m "feat: configuration from environment variables"
```

---

## Task 3: Job State Model (SQLite)

**Files:**
- Create: `transfer/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/models.py`**

```python
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
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add transfer/models.py tests/test_models.py
git commit -m "feat: SQLite job state model with status tracking"
```

---

## Task 4: Source URL Detection

**Files:**
- Create: `transfer/sources/__init__.py`

**Step 1: Write the failing test**

Create `tests/test_sources.py` (will grow with later tasks):

```python
from transfer.sources import detect_source, SourceType

def test_detect_google_drive_file():
    url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view"
    assert detect_source(url) == SourceType.GOOGLE_DRIVE

def test_detect_google_drive_folder():
    url = "https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    assert detect_source(url) == SourceType.GOOGLE_DRIVE

def test_detect_dropbox():
    url = "https://www.dropbox.com/s/abc123/myfile.tif?dl=0"
    assert detect_source(url) == SourceType.DROPBOX

def test_detect_dropbox_folder():
    url = "https://www.dropbox.com/sh/abc123/AABcdef/folder"
    assert detect_source(url) == SourceType.DROPBOX

def test_detect_onedrive():
    url = "https://1drv.ms/u/s!Abc123"
    assert detect_source(url) == SourceType.ONEDRIVE

def test_detect_sharepoint():
    url = "https://contoso.sharepoint.com/sites/team/Shared%20Documents/order.tif"
    assert detect_source(url) == SourceType.ONEDRIVE

def test_detect_unknown():
    url = "https://example.com/file.tif"
    assert detect_source(url) is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_sources.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/sources/__init__.py`**

```python
from enum import Enum
from urllib.parse import urlparse

class SourceType(Enum):
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"

def detect_source(url: str) -> SourceType | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "drive.google.com" in host or "docs.google.com" in host:
        return SourceType.GOOGLE_DRIVE
    if "dropbox.com" in host:
        return SourceType.DROPBOX
    if "1drv.ms" in host or "onedrive.live.com" in host or "sharepoint.com" in host:
        return SourceType.ONEDRIVE
    return None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_sources.py -v
```

Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add transfer/sources/__init__.py tests/test_sources.py
git commit -m "feat: cloud source URL detection"
```

---

## Task 5: Google Drive Downloader

**Files:**
- Create: `transfer/sources/gdrive.py`

**Step 1: Write the failing test**

Add to `tests/test_sources.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from transfer.sources.gdrive import GoogleDriveDownloader

@pytest.fixture
def gdrive():
    return GoogleDriveDownloader()

def test_extract_file_id_from_view_url(gdrive):
    url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view"
    assert gdrive.extract_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

def test_extract_folder_id(gdrive):
    url = "https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    fid, is_folder = gdrive.extract_id_and_type(url)
    assert fid == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74Og"
    assert is_folder is True

def test_extract_file_id_and_type(gdrive):
    url = "https://drive.google.com/file/d/ABC123/view"
    fid, is_folder = gdrive.extract_id_and_type(url)
    assert fid == "ABC123"
    assert is_folder is False

async def test_download_file_calls_gdown(gdrive, tmp_path):
    with patch("transfer.sources.gdrive.gdown.download") as mock_dl:
        mock_dl.return_value = str(tmp_path / "file.tif")
        paths = await gdrive.download("https://drive.google.com/file/d/ABC/view", tmp_path)
        assert len(paths) == 1
        mock_dl.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_sources.py::test_extract_file_id_from_view_url -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/sources/gdrive.py`**

```python
import re
from pathlib import Path
import gdown
from urllib.parse import urlparse, parse_qs

class GoogleDriveDownloader:

    def extract_id(self, url: str) -> str:
        # /file/d/{id}/view or /file/d/{id}
        m = re.search(r"/file/d/([^/?#]+)", url)
        if m:
            return m.group(1)
        # open?id={id}
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "id" in qs:
            return qs["id"][0]
        raise ValueError(f"Cannot extract file ID from: {url}")

    def extract_id_and_type(self, url: str) -> tuple[str, bool]:
        # /drive/folders/{id}
        m = re.search(r"/drive/folders/([^/?#]+)", url)
        if m:
            return m.group(1), True
        return self.extract_id(url), False

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_id, is_folder = self.extract_id_and_type(url)

        if is_folder:
            output = str(dest_dir)
            gdown.download_folder(
                id=file_id,
                output=output,
                quiet=False,
                use_cookies=False,
            )
            return list(dest_dir.iterdir())
        else:
            output_path = str(dest_dir / f"{file_id}_download")
            result = gdown.download(id=file_id, output=output_path, quiet=False)
            return [Path(result)] if result else []
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_sources.py -k "gdrive or extract" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/sources/gdrive.py tests/test_sources.py
git commit -m "feat: Google Drive downloader"
```

---

## Task 6: Dropbox Downloader

**Files:**
- Create: `transfer/sources/dropbox_.py`

**Step 1: Write the failing test**

Add to `tests/test_sources.py`:

```python
from transfer.sources.dropbox_ import DropboxDownloader
import respx
import httpx

@pytest.fixture
def dbox():
    return DropboxDownloader()

def test_make_direct_url(dbox):
    url = "https://www.dropbox.com/s/abc123/file.tif?dl=0"
    assert dbox.make_direct_url(url) == "https://www.dropbox.com/s/abc123/file.tif?dl=1"

def test_make_direct_url_already_dl1(dbox):
    url = "https://www.dropbox.com/s/abc123/file.tif?dl=1"
    assert dbox.make_direct_url(url) == "https://www.dropbox.com/s/abc123/file.tif?dl=1"

def test_extract_filename(dbox):
    url = "https://www.dropbox.com/s/abc123/myprint.tif?dl=0"
    assert dbox.extract_filename(url) == "myprint.tif"

@respx.mock
async def test_download_single_file(dbox, tmp_path):
    direct_url = "https://www.dropbox.com/s/abc123/test.tif?dl=1"
    respx.get(direct_url).mock(return_value=httpx.Response(200, content=b"TIFFDATA"))
    paths = await dbox.download("https://www.dropbox.com/s/abc123/test.tif?dl=0", tmp_path)
    assert len(paths) == 1
    assert paths[0].read_bytes() == b"TIFFDATA"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_sources.py -k "dropbox or dbox" -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/sources/dropbox_.py`**

Note: file is named `dropbox_.py` (with underscore) to avoid shadowing the `dropbox` package.

```python
import re
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
import httpx

class DropboxDownloader:

    def make_direct_url(self, url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs["dl"] = ["1"]
        new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
        return urlunparse(parsed._replace(query=new_query))

    def extract_filename(self, url: str) -> str:
        path = urlparse(url).path
        return path.split("/")[-1] or "download"

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        direct_url = self.make_direct_url(url)
        filename = self.extract_filename(url)
        dest_path = dest_dir / filename

        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            async with client.stream("GET", direct_url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)

        return [dest_path]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_sources.py -k "dropbox or dbox" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/sources/dropbox_.py tests/test_sources.py
git commit -m "feat: Dropbox downloader (direct URL streaming)"
```

---

## Task 7: OneDrive/SharePoint Downloader

**Files:**
- Create: `transfer/sources/onedrive.py`

**Step 1: Write the failing test**

Add to `tests/test_sources.py`:

```python
from transfer.sources.onedrive import OneDriveDownloader

@pytest.fixture
def onedrive():
    return OneDriveDownloader(
        client_id="test_client_id",
        client_secret="test_secret",
        tenant_id="common",
    )

def test_onedrive_encode_sharing_url(onedrive):
    url = "https://1drv.ms/u/s!Abc123"
    encoded = onedrive.encode_sharing_url(url)
    # Should be base64url encoded with u! prefix
    assert encoded.startswith("u!")

@respx.mock
async def test_onedrive_download_file(onedrive, tmp_path):
    # Mock the token endpoint
    respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "token_type": "Bearer"})
    )
    sharing_url = "https://1drv.ms/u/s!TestFile"
    encoded = onedrive.encode_sharing_url(sharing_url)
    api_url = f"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem"

    respx.get(api_url).mock(return_value=httpx.Response(200, json={
        "name": "test.tif",
        "@microsoft.graph.downloadUrl": "https://download.example.com/test.tif"
    }))
    respx.get("https://download.example.com/test.tif").mock(
        return_value=httpx.Response(200, content=b"TIFFBYTES")
    )
    paths = await onedrive.download(sharing_url, tmp_path)
    assert len(paths) == 1
    assert paths[0].read_bytes() == b"TIFFBYTES"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_sources.py -k "onedrive" -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/sources/onedrive.py`**

```python
import base64
from pathlib import Path
import httpx

class OneDriveDownloader:

    def __init__(self, client_id: str, client_secret: str, tenant_id: str = "common"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._token: str | None = None

    def encode_sharing_url(self, url: str) -> str:
        """Encode a sharing URL as a base64url string for the Graph API."""
        b64 = base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        return f"u!{b64}"

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            })
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
            return self._token

    async def download(self, url: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        token = await self._get_token()
        encoded = self.encode_sharing_url(url)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
            # Resolve the sharing link to get the download URL and filename
            meta_resp = await client.get(
                f"https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem",
                headers=headers,
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            # Handle folder vs file
            if "folder" in meta:
                return await self._download_folder(meta, dest_dir, client, headers)

            download_url = meta.get("@microsoft.graph.downloadUrl")
            filename = meta.get("name", "download")
            dest_path = dest_dir / filename

            async with client.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(8 * 1024 * 1024):
                        f.write(chunk)

            return [dest_path]

    async def _download_folder(self, folder_meta: dict, dest_dir: Path,
                                client: httpx.AsyncClient, headers: dict) -> list[Path]:
        children_url = folder_meta.get("@microsoft.graph.downloadUrl") or \
                       f"https://graph.microsoft.com/v1.0/drives/{folder_meta['parentReference']['driveId']}" \
                       f"/items/{folder_meta['id']}/children"
        resp = await client.get(children_url, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        paths = []
        for item in items:
            if "file" in item:
                dl_url = item.get("@microsoft.graph.downloadUrl")
                dest_path = dest_dir / item["name"]
                async with client.stream("GET", dl_url) as r:
                    r.raise_for_status()
                    with open(dest_path, "wb") as f:
                        async for chunk in r.aiter_bytes(8 * 1024 * 1024):
                            f.write(chunk)
                paths.append(dest_path)
        return paths
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_sources.py -k "onedrive" -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/sources/onedrive.py tests/test_sources.py
git commit -m "feat: OneDrive/SharePoint downloader via Microsoft Graph API"
```

---

## Task 8: Processing Pipeline Infrastructure

**Files:**
- Create: `transfer/processors/__init__.py`
- Create: `tests/test_processors.py`

**Step 1: Write the failing test**

Create `tests/test_processors.py`:

```python
import pytest
from pathlib import Path
from transfer.processors import ProcessingPipeline

async def test_pipeline_passes_through_unknown_extension(tmp_path):
    # A .pdf file with no registered processor should be returned unchanged
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    pipeline = ProcessingPipeline()
    result = await pipeline.process(test_file)
    assert result == test_file

async def test_pipeline_calls_processor_for_tiff(tmp_path, monkeypatch):
    from transfer.processors import ProcessingPipeline
    test_file = tmp_path / "test.tif"
    test_file.write_bytes(b"fake tiff")
    output_file = tmp_path / "test_processed.tif"
    output_file.write_bytes(b"processed")

    async def fake_process(path):
        return output_file

    pipeline = ProcessingPipeline()
    monkeypatch.setitem(pipeline.processors, ".tif", fake_process)
    result = await pipeline.process(test_file)
    assert result == output_file
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_processors.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/processors/__init__.py`**

```python
from pathlib import Path
from typing import Callable, Awaitable

ProcessorFn = Callable[[Path], Awaitable[Path]]

class ProcessingPipeline:
    def __init__(self):
        self.processors: dict[str, ProcessorFn] = {}
        self._register_defaults()

    def _register_defaults(self):
        from transfer.processors.tiff import flatten_tiff
        self.processors[".tif"] = flatten_tiff
        self.processors[".tiff"] = flatten_tiff

    async def process(self, file_path: Path) -> Path:
        ext = file_path.suffix.lower()
        processor = self.processors.get(ext)
        if processor:
            return await processor(file_path)
        return file_path
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_processors.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/processors/__init__.py tests/test_processors.py
git commit -m "feat: pluggable processing pipeline infrastructure"
```

---

## Task 9: TIFF Processor (Flatten Layers)

**Files:**
- Create: `transfer/processors/tiff.py`

**Step 1: Write the failing test**

Add to `tests/test_processors.py`:

```python
from PIL import Image
import io

def make_tiff_with_alpha(path: Path):
    """Create a simple RGBA TIFF to simulate a layered file."""
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    img.save(path, format="TIFF")

async def test_flatten_tiff_removes_alpha(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "layered.tif"
    make_tiff_with_alpha(src)

    result = await flatten_tiff(src)

    out_img = Image.open(result)
    assert out_img.mode == "RGB"  # alpha channel removed

async def test_flatten_tiff_output_path(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "input.tif"
    make_tiff_with_alpha(src)

    result = await flatten_tiff(src)
    # Output should be in same directory, different name
    assert result.parent == src.parent
    assert result != src

async def test_flatten_tiff_rgb_passthrough(tmp_path):
    from transfer.processors.tiff import flatten_tiff
    src = tmp_path / "flat.tif"
    img = Image.new("RGB", (10, 10), (100, 100, 100))
    img.save(src, format="TIFF")

    result = await flatten_tiff(src)
    out_img = Image.open(result)
    assert out_img.mode == "RGB"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_processors.py -k "tiff" -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/processors/tiff.py`**

```python
from pathlib import Path
from PIL import Image
import asyncio

async def flatten_tiff(path: Path) -> Path:
    """
    Flatten a TIFF file by compositing any alpha channel onto a white background
    and converting to RGB. Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _flatten_sync, path)

def _flatten_sync(path: Path) -> Path:
    img = Image.open(path)
    if img.mode == "RGB":
        # Already flat — save a copy so the pipeline always returns a new file
        out_path = path.with_name(path.stem + "_flat" + path.suffix)
        img.save(out_path, format="TIFF", compression="tiff_lzw")
        return out_path

    # Composite onto white background
    background = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ("RGBA", "LA", "PA"):
        background.paste(img, mask=img.split()[-1])  # use alpha as mask
    else:
        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])

    out_path = path.with_name(path.stem + "_flat" + path.suffix)
    background.save(out_path, format="TIFF", compression="tiff_lzw")
    return out_path
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_processors.py -v
```

Expected: PASS (all processor tests)

**Step 5: Commit**

```bash
git add transfer/processors/tiff.py tests/test_processors.py
git commit -m "feat: TIFF layer flattening processor using Pillow"
```

---

## Task 10: LARK Drive Client

**Files:**
- Create: `transfer/lark_client.py`
- Create: `tests/test_lark_client.py`

**Step 1: Write the failing test**

Create `tests/test_lark_client.py`:

```python
import pytest
import respx
import httpx
from transfer.lark_client import LarkClient

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FOLDER_URL = "https://open.feishu.cn/open-apis/drive/v1/files/create_folder"
LIST_URL = "https://open.feishu.cn/open-apis/drive/v1/files"

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
    # List returns empty
    respx.get(LIST_URL).mock(return_value=httpx.Response(200, json={
        "code": 0, "data": {"files": [], "has_more": False}
    }))
    # Create folder
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_lark_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/lark_client.py`**

```python
import time
from pathlib import Path
import httpx

LARK_BASE = "https://open.feishu.cn/open-apis"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks for large file upload

class LarkClient:
    def __init__(self, app_id: str, app_secret: str, root_folder_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.root_folder_token = root_folder_token
        self._token: str | None = None
        self._token_expiry: float = 0

    async def get_access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK auth failed: {data}")
            self._token = data["tenant_access_token"]
            self._token_expiry = time.time() + data["expire"]
            return self._token

    async def _headers(self) -> dict:
        return {"Authorization": f"Bearer {await self.get_access_token()}"}

    async def list_folder(self, folder_token: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{LARK_BASE}/drive/v1/files",
                params={"folder_token": folder_token},
                headers=await self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK list folder failed: {data}")
            return data["data"]["files"]

    async def create_folder(self, parent_token: str, name: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LARK_BASE}/drive/v1/files/create_folder",
                json={"name": name, "folder_token": parent_token},
                headers=await self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK create folder failed: {data}")
            return data["data"]

    async def ensure_folder(self, parent_token: str, name: str) -> str:
        """Return token of named subfolder, creating it if it doesn't exist."""
        items = await self.list_folder(parent_token)
        for item in items:
            if item.get("name") == name and item.get("type") == "folder":
                return item["token"]
        result = await self.create_folder(parent_token, name)
        return result["token"]

    async def upload_file(self, folder_token: str, file_path: Path) -> str:
        """Upload a file to a LARK folder. Returns the file token."""
        size = file_path.stat().st_size
        if size <= 20 * 1024 * 1024:
            return await self._upload_small(folder_token, file_path)
        return await self._upload_large(folder_token, file_path, size)

    async def _upload_small(self, folder_token: str, file_path: Path) -> str:
        headers = await self._headers()
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    f"{LARK_BASE}/drive/v1/medias/upload_all",
                    headers=headers,
                    data={
                        "file_name": file_path.name,
                        "parent_type": "explorer",
                        "parent_node": folder_token,
                        "size": str(file_path.stat().st_size),
                    },
                    files={"file": (file_path.name, f, "application/octet-stream")},
                )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != 0:
                raise RuntimeError(f"LARK upload failed: {data}")
            return data["data"]["file_token"]

    async def _upload_large(self, folder_token: str, file_path: Path, size: int) -> str:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=None) as client:
            # Step 1: prepare
            prep = await client.post(
                f"{LARK_BASE}/drive/v1/medias/upload_prepare",
                headers=headers,
                json={
                    "file_name": file_path.name,
                    "parent_type": "explorer",
                    "parent_node": folder_token,
                    "size": size,
                    "block_size": CHUNK_SIZE,
                },
            )
            prep.raise_for_status()
            prep_data = prep.json()
            if prep_data["code"] != 0:
                raise RuntimeError(f"LARK upload_prepare failed: {prep_data}")
            upload_id = prep_data["data"]["upload_id"]
            block_num = prep_data["data"]["block_num"]

            # Step 2: upload parts
            with open(file_path, "rb") as f:
                for seq in range(block_num):
                    chunk = f.read(CHUNK_SIZE)
                    part_resp = await client.post(
                        f"{LARK_BASE}/drive/v1/medias/upload_part",
                        headers=headers,
                        data={"upload_id": upload_id, "seq": str(seq), "size": str(len(chunk))},
                        files={"file": (file_path.name, chunk, "application/octet-stream")},
                    )
                    part_resp.raise_for_status()
                    if part_resp.json()["code"] != 0:
                        raise RuntimeError(f"LARK upload_part failed: {part_resp.json()}")

            # Step 3: finish
            finish = await client.post(
                f"{LARK_BASE}/drive/v1/medias/upload_finish",
                headers=headers,
                json={"upload_id": upload_id, "block_num": block_num},
            )
            finish.raise_for_status()
            finish_data = finish.json()
            if finish_data["code"] != 0:
                raise RuntimeError(f"LARK upload_finish failed: {finish_data}")
            return finish_data["data"]["file_token"]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_lark_client.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/lark_client.py tests/test_lark_client.py
git commit -m "feat: LARK Drive client (auth, folder management, chunked upload)"
```

---

## Task 11: Background Worker

**Files:**
- Create: `transfer/worker.py`
- Create: `tests/test_worker.py`

**Step 1: Write the failing test**

Create `tests/test_worker.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/worker.py`**

```python
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
        raise
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
    raise ValueError(f"Unsupported or unrecognised source URL")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_worker.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/worker.py tests/test_worker.py
git commit -m "feat: background job worker orchestrating download→process→upload"
```

---

## Task 12: FastAPI Routes

**Files:**
- Create: `transfer/app.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing test**

Create `tests/test_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LARK_APP_ID", "x")
    monkeypatch.setenv("LARK_APP_SECRET", "x")
    monkeypatch.setenv("LARK_ROOT_FOLDER_TOKEN", "x")
    monkeypatch.setenv("TEMP_DIR", str(tmp_path))

    from transfer.app import create_app
    app = create_app(db_path=str(tmp_path / "test.db"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_api.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write `transfer/app.py`**

```python
import asyncio
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from transfer.models import JobStore
from transfer.worker import run_job
from transfer.config import settings as default_settings

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def create_app(db_path: str = "jobs.db") -> FastAPI:
    app = FastAPI(title="Cloud→LARK Transfer")
    store = JobStore(db_path)

    @app.on_event("startup")
    async def startup():
        await store.init()

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.post("/jobs")
    async def create_job(
        order_number: str = Form(...),
        source_url: str = Form(...),
    ):
        job_id = await store.create_job(order_number=order_number, source_url=source_url)
        asyncio.create_task(run_job(job_id, store, default_settings))
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = await store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    return app

app = create_app()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_api.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add transfer/app.py tests/test_api.py
git commit -m "feat: FastAPI routes for job submission and status polling"
```

---

## Task 13: HTML UI

**Files:**
- Create: `templates/index.html`

No automated test for the template — verify manually by running the server.

**Step 1: Create `templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cloud → LARK Transfer</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
        h1 { font-size: 1.4rem; margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 4px; font-weight: bold; font-size: 0.9rem; }
        input[type=text] { width: 100%; padding: 8px; font-size: 1rem; box-sizing: border-box; margin-bottom: 1rem; }
        button { padding: 10px 24px; font-size: 1rem; cursor: pointer; background: #1a73e8; color: white; border: none; border-radius: 4px; }
        button:disabled { background: #aaa; cursor: default; }
        #status-box { margin-top: 1.5rem; padding: 12px; border-radius: 4px; display: none; }
        .queued, .downloading, .processing, .uploading { background: #e8f0fe; border: 1px solid #1a73e8; }
        .done { background: #e6f4ea; border: 1px solid #34a853; }
        .failed { background: #fce8e6; border: 1px solid #ea4335; }
        #progress { font-size: 0.9rem; color: #555; margin-top: 6px; }
        #error-msg { color: #ea4335; font-size: 0.9rem; margin-top: 6px; }
    </style>
</head>
<body>
    <h1>Cloud → LARK Transfer</h1>
    <form id="transfer-form">
        <label for="order_number">Order Number</label>
        <input type="text" id="order_number" name="order_number" placeholder="ORD-12345" required>

        <label for="source_url">Customer Cloud Link</label>
        <input type="text" id="source_url" name="source_url"
               placeholder="https://drive.google.com/... or dropbox.com/... or 1drv.ms/..." required>

        <button type="submit" id="submit-btn">Start Transfer</button>
    </form>

    <div id="status-box">
        <strong id="status-label">Status: queued</strong>
        <div id="progress"></div>
        <div id="error-msg"></div>
    </div>

    <script>
        const form = document.getElementById('transfer-form');
        const btn = document.getElementById('submit-btn');
        const box = document.getElementById('status-box');
        const label = document.getElementById('status-label');
        const progressEl = document.getElementById('progress');
        const errorEl = document.getElementById('error-msg');
        let pollInterval = null;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            btn.disabled = true;
            errorEl.textContent = '';

            const fd = new FormData(form);
            const resp = await fetch('/jobs', { method: 'POST', body: fd });
            const data = await resp.json();

            if (!resp.ok) {
                errorEl.textContent = data.detail || 'Error submitting job.';
                btn.disabled = false;
                return;
            }

            box.style.display = 'block';
            poll(data.job_id);
        });

        function poll(jobId) {
            pollInterval = setInterval(async () => {
                const resp = await fetch(`/jobs/${jobId}`);
                const job = await resp.json();

                box.className = job.status;
                label.textContent = `Status: ${job.status.toUpperCase()}`;
                progressEl.textContent = job.progress || '';
                errorEl.textContent = job.error || '';

                if (job.status === 'done' || job.status === 'failed') {
                    clearInterval(pollInterval);
                    btn.disabled = false;
                    if (job.status === 'done') {
                        form.reset();
                    }
                }
            }, 2000);
        }
    </script>
</body>
</html>
```

**Step 2: Smoke test manually**

```bash
cp .env.example .env
# Edit .env with real credentials
source .venv/bin/activate
uvicorn transfer.app:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000` in a browser. Form should appear. Submit a test job and watch status update.

**Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: web UI with job submission form and live status polling"
```

---

## Task 14: Deployment on VPS

**Files:**
- Create: `setup.sh`
- Create: `systemd/transfer.service`

**Step 1: Create `systemd/transfer.service`**

```ini
[Unit]
Description=Cloud to LARK Transfer Service
After=network.target

[Service]
Type=simple
User=transfer
WorkingDirectory=/opt/transfer
EnvironmentFile=/opt/transfer/.env
ExecStart=/opt/transfer/.venv/bin/uvicorn transfer.app:app --host ${HOST} --port ${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Step 2: Create `setup.sh`**

```bash
#!/bin/bash
set -e

# Run as root on a fresh Ubuntu 22.04 / Debian 12 VPS
# Usage: curl -sSL https://your-vps/setup.sh | sudo bash
#   or:  sudo bash setup.sh

echo "=== Installing system dependencies ==="
apt-get update -qq
apt-get install -y python3.12 python3.12-venv python3-pip git libtiff-dev

echo "=== Installing Tailscale ==="
curl -fsSL https://tailscale.com/install.sh | sh
echo "Run: tailscale up --authkey=<your-auth-key>"

echo "=== Creating service user ==="
useradd --system --home /opt/transfer --shell /usr/sbin/nologin transfer || true
mkdir -p /opt/transfer
chown transfer:transfer /opt/transfer

echo "=== Deploying app ==="
# Copy repo to /opt/transfer (run from repo root):
# rsync -av --exclude='.git' --exclude='.venv' ./ transfer@your-vps:/opt/transfer/
# Then SSH in and run:

echo "=== Creating virtualenv ==="
sudo -u transfer python3.12 -m venv /opt/transfer/.venv
sudo -u transfer /opt/transfer/.venv/bin/pip install -r /opt/transfer/requirements.txt

echo "=== Creating temp dir ==="
mkdir -p /tmp/transfer-jobs
chown transfer:transfer /tmp/transfer-jobs

echo "=== Installing systemd service ==="
cp /opt/transfer/systemd/transfer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable transfer
systemctl start transfer

echo ""
echo "=== Done ==="
echo "Next steps:"
echo "  1. Edit /opt/transfer/.env with real credentials"
echo "  2. Run: tailscale up --authkey=<key>"
echo "  3. Run: systemctl restart transfer"
echo "  4. Access via Tailscale IP on port 8000"
```

**Step 3: Make setup.sh executable and commit**

```bash
chmod +x setup.sh
git add systemd/transfer.service setup.sh
git commit -m "feat: VPS deployment scripts (systemd service + setup.sh)"
```

---

## Task 15: Final Smoke Test & Full Test Suite Run

**Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All tests PASS.

**Step 2: If any test fails, fix it before proceeding.**

**Step 3: Verify coverage of all major paths**

```bash
pip install pytest-cov
pytest --cov=transfer --cov-report=term-missing
```

Check that all source downloaders, the processor, lark client, worker, and API routes have coverage.

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: verified full test suite passes"
```

**Step 5: Push**

```bash
git push origin main
```

---

## Setup Reference: API Credentials

After deployment, you need credentials for each source. Do these once:

### LARK App
1. Go to [open.feishu.cn](https://open.feishu.cn) → Create app
2. Enable "Drive" permissions: `drive:drive`, `drive:file`
3. Copy App ID and App Secret to `.env`
4. Get root folder token: open LARK Drive in browser, the folder token is in the URL

### Google Drive
- For public shared links, `gdown` works without credentials
- For restricted links: create a Google Cloud project, enable Drive API, create an API key

### Dropbox
- For public shared links (`/s/` URLs), no credentials needed
- For private files: create a Dropbox app at [dropbox.com/developers](https://dropbox.com/developers)

### OneDrive / SharePoint
1. Go to [portal.azure.com](https://portal.azure.com) → Azure Active Directory → App registrations
2. Register new app → add `Files.Read.All` (Microsoft Graph) permission
3. Create a client secret
4. Copy client ID, secret, and tenant ID to `.env`
