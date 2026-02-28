# Cloud-to-LARK File Transfer Service

A VPS-hosted Python web app that transfers large print files (1–4 GB) from customer cloud storage (Google Drive, Dropbox, OneDrive) to LARK Drive — without going through the shop's slow local connection.

## Status
**Implemented.** All 36 tests passing. Ready for VPS deployment.

## Key Design Decisions
- VPS handles all transfers (datacenter bandwidth, not shop connection)
- Tailscale for access control (no public-facing ports)
- Processing pipeline between download and upload (e.g. TIFF layer flattening)
- LARK folder structure: `{order_number}/{YYYY-MM-DD}/`
- SQLite job store with lazy init (aiosqlite hangs if initialized inside httpx ASGITransport)
- `create_app()` accepts optional `store=` param for testability

## Project Structure
```
transfer/
  config.py          # env-var Settings dataclass
  models.py          # SQLite job CRUD (JobStore, JobStatus)
  sources/
    __init__.py      # URL detection + SourceType enum
    gdrive.py        # Google Drive downloader (gdown)
    dropbox_.py      # Dropbox downloader (httpx streaming)
    onedrive.py      # OneDrive/SharePoint via Microsoft Graph API
  processors/
    __init__.py      # ProcessingPipeline
    tiff.py          # TIFF layer flattening (Pillow)
  lark_client.py     # LARK Drive auth + folder + chunked upload
  worker.py          # orchestrates download → process → upload
  app.py             # FastAPI routes (create_app factory)
templates/
  index.html         # form + live status polling UI
tests/               # 36 tests, all passing
setup.sh             # VPS setup script
systemd/transfer.service
```

## Running
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
uvicorn transfer.app:app --host <tailscale-ip> --port 8000
```

## Deployment
See `setup.sh` for automated VPS setup (Ubuntu 22.04/Debian 12).
See `docs/plans/` for design documents.

## Docs
- Design: `docs/plans/2026-02-27-cloud-to-lark-transfer-design.md`
- Implementation plan: `docs/plans/2026-02-27-cloud-to-lark-transfer.md`
