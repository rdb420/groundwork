#!/usr/bin/env bash
# Nightly backup. Add to the host's crontab, for example:
#   15 2 * * * /opt/groundwork/deploy/backup.sh >> /var/log/groundwork-backup.log 2>&1
#
# Encryption: set GW_BACKUP_AGE_RECIPIENTS in .env to one or more age public keys. Make a key pair
# on a machine that is NOT this host (age-keygen -o groundwork-backup.key), keep the private key
# there and in your password manager, and put only the public key (age1...) in .env.
#
# Off-host copy: set GW_BACKUP_COPY_TO in .env to an rsync destination this host can write to,
# for example nas:/volume1/groundwork-backups/ or /mnt/offsite/groundwork/.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T app python -m app.backup

setting() { grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true; }
copy_to="${GW_BACKUP_COPY_TO:-$(setting GW_BACKUP_COPY_TO)}"
if [ -n "$copy_to" ]; then
  if [ -z "$(setting GW_BACKUP_AGE_RECIPIENTS)" ]; then
    echo "Refusing to copy unencrypted backups off the host. Set GW_BACKUP_AGE_RECIPIENTS first." >&2
    exit 1
  fi
  rsync -a data/backups/ "$copy_to"
  echo "Copied backups to $copy_to"
else
  echo "Backups are on this host only. Set GW_BACKUP_COPY_TO to copy them somewhere else." >&2
fi
