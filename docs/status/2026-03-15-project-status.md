# Cloud-to-LARK Transfer — Project Status
*Last updated: 2026-03-15*

## Goal
A VPS-hosted web app so shop staff can paste a customer's cloud storage link + order number into a form. The VPS (datacenter bandwidth) downloads the files and uploads them to the correct LARK Drive folder — bypassing the shop's slow local connection.

---

## What's Done

The full application is **built, tested (36/36 passing), and pushed to GitHub** at `GRAVITYATATHENA/Cloud-to-Lark-Transfer`.

| Component | Status |
|---|---|
| Web form UI (paste link + order number, live status polling) | Done |
| Google Drive downloader | Done |
| Dropbox downloader | Done |
| OneDrive/SharePoint downloader | Done |
| TIFF layer flattening processor | Done |
| LARK Drive client (auth, folders, chunked upload) | Done |
| Background job worker (download → process → upload) | Done |
| SQLite job tracking | Done |
| VPS systemd service + setup.sh | Done |
| API base fixed for international Lark (larksuite.com) | Done |

---

## What Remains

Everything left is **configuration and deployment**, not code.

### Step 1 — Lark App Credentials
Create an internal app at https://open.larksuite.com:
- `LARK_APP_ID` — from the app's Credentials page (looks like `cli_xxxx`)
- `LARK_APP_SECRET` — same page
- `LARK_ROOT_FOLDER_TOKEN` — open a dedicated "Print Transfers" folder in Lark Drive; the token is in the URL (looks like `fldcnxxxx`)

Permissions needed: `drive:drive` and `drive:file` (read + write).

**Note on isolation:** The app authenticates as itself (not as any user), so no existing user accounts are affected. Recommend creating a dedicated "Print Transfers" folder and granting the app access only to that folder.

### Step 2 — Write the .env File
Once credentials are in hand, fill in `.env` from `.env.example`. Public Dropbox and Google Drive links need no extra credentials. OneDrive requires Azure app registration.

### Step 3 — VPS Provisioning
- Spin up a VPS (DigitalOcean, Hetzner, etc.)
- Install Tailscale: `tailscale up --authkey=<key>`
- Run `setup.sh` as root — it installs dependencies, creates the service user, sets up systemd
- Set `HOST` in `.env` to the VPS's Tailscale IP (so it's only reachable inside your Tailscale network)

### Step 4 — Live End-to-End Test
Submit a real job through the form and confirm files land in the correct Lark Drive folder under `{order_number}/{YYYY-MM-DD}/`.

---

## Shortest Path to Done
Get the Lark app credentials → fill `.env` → run `setup.sh` on a VPS → test.
