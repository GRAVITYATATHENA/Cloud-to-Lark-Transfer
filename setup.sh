#!/bin/bash
set -e

# Run as root on a fresh Ubuntu 22.04 / Debian 12 VPS
# Usage: sudo bash setup.sh

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
