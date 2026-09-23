#!/usr/bin/env bash
# Nightly backup. Add to the host's crontab, for example:
#   15 2 * * * /opt/groundwork/deploy/backup.sh >> /var/log/groundwork-backup.log 2>&1
# Then copy data/backups/ somewhere off this machine (NAS, cloud storage, rsync over Tailscale).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T app python -m app.backup
