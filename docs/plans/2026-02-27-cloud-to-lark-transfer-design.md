# Cloud-to-LARK File Transfer Service — Design

**Date:** 2026-02-27
**Status:** Approved

## Problem

Customers send 1–4 GB print files via Google Drive, Dropbox, or OneDrive/SharePoint links. The current workflow — download to local machine, then upload to LARK Drive — is slow because the shop's internet connection is the bottleneck in both directions.

## Goal

A web-based tool where staff paste a source link and an order number. The tool downloads the files to a VPS (fast datacenter bandwidth), runs a processing pipeline, then uploads to the correct LARK Drive folder — without ever touching the shop's local connection.

## Architecture

```
[Customer Cloud Storage]
   Google Drive / Dropbox / OneDrive
          ↓  (download via API, VPS bandwidth)
     [VPS Temp Storage]
          ↓  (processing pipeline — e.g. flatten TIFF layers)
     [VPS Temp Storage]
          ↓  (upload via LARK Drive API)
     [LARK Drive]
   /{order_number}/{YYYY-MM-DD}/filename.tif
```

## Components

### 1. Web UI
- Single-page form: order number + source link
- Shows live job progress: downloading / processing / uploading / done / error
- Accessible only via Tailscale private network (never exposed to public internet)
- Backend: Python / FastAPI

### 2. Source Downloaders
One handler per source, auto-detected from the URL:

| Source | Method |
|--------|--------|
| Google Drive | `gdown` library or Google Drive API (handles shared folders and individual files) |
| Dropbox | Dropbox SDK or direct `dl.dropboxusercontent.com` URL |
| OneDrive / SharePoint | Microsoft Graph API (requires one-time app registration) |

### 3. Processing Pipeline
Pluggable chain of per-filetype processors. Each processor receives an input path and returns an output path.

- `processors/tiff.py` — flatten layers (Pillow or ImageMagick/wand)
- Additional processors added as needed (PDF, JPEG, etc.)
- If a processor fails, the original unprocessed file is uploaded as a fallback and a warning is logged.

### 4. LARK Uploader
- Uses LARK Drive API
- Creates `{order_number}/` folder if it does not exist
- Creates `{YYYY-MM-DD}/` subfolder
- Uploads each processed file using resumable chunked upload (required for files >1 GB)

### 5. Job Manager
- Tracks state per job: queued → downloading → processing → uploading → done / error
- Displayed in the UI with per-file progress
- State stored in SQLite (simple, no extra services required)
- Background worker: `asyncio` tasks (or `rq` + Redis if job queue complexity grows)

## Security

**Tailscale private network:**
- Tailscale installed on each staff Mac and the VPS
- The app binds to the Tailscale network interface only — the port is never reachable from the public internet
- Staff access the app via Tailscale hostname, e.g. `http://transfer-vps:8000`
- Tailscale free tier covers up to 100 devices

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Download fails (expired link, permissions, quota) | Job marked failed immediately; clear error shown in UI |
| Processing fails (corrupt file, unsupported variant) | File skipped with warning; other files in batch continue; original uploaded as fallback |
| LARK upload fails | Retry with exponential backoff (3 attempts); job marked failed if all attempts fail |
| VPS disk full | Checked before download starts; job rejected with warning |
| Any failure | Temp files always cleaned up |

## Deployment

| Item | Choice |
|------|--------|
| VPS | Hetzner CX22 (~€4/mo) or DigitalOcean Basic ($6/mo): 2 vCPU, 4 GB RAM, 40–80 GB SSD, ~1 Gbps |
| Language | Python 3.12 |
| Framework | FastAPI + uvicorn |
| Process manager | systemd (auto-restart on reboot) |
| Temp storage | `/tmp/transfer-jobs/`, cleaned after each job |
| Network | Tailscale — app binds to Tailscale interface only |

## One-Time Setup Required

- Google OAuth app (or service account) for Drive API
- Dropbox app registration for Dropbox API
- Microsoft Azure app registration for Graph API (OneDrive/SharePoint)
- LARK app with Drive read/write permissions
- Tailscale account; install on VPS + each staff Mac

## Future Extensions

- Additional file processors (PDF processing, color profile conversion, etc.)
- Per-job audit log (who submitted, when, what files, processing applied)
- Email/LARK notification when a job completes
- Customer self-upload via LARK external upload link (for customers who prefer to push directly)
