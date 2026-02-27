# Cloud-to-LARK File Transfer Service

A VPS-hosted Python web app that transfers large print files (1–4 GB) from customer cloud storage (Google Drive, Dropbox, OneDrive) to LARK Drive — without going through the shop's slow local connection.

## Status
Design approved. Implementation plan TBD.

## Key Design Decisions
- VPS handles all transfers (datacenter bandwidth, not shop connection)
- Tailscale for access control (no public-facing ports)
- Processing pipeline between download and upload (e.g. TIFF layer flattening)
- LARK folder structure: `{order_number}/{YYYY-MM-DD}/`

## Docs
- Design: `docs/plans/2026-02-27-cloud-to-lark-transfer-design.md`
