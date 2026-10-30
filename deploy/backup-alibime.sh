#!/usr/bin/env bash
# Nightly database dump. The ledger holds paid credits, so this is not
# optional. Keeps 14 days locally; copy BACKUP_DIR off the server as well
# (see DEPLOY-CHECKLIST.md), a backup on the same disk doesn't survive the disk.
#
# Run by alibime-backup.timer as the alibime user. Postgres: needs a role for
# alibime that can read the database (peer auth on the local socket).
set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-/var/backups/alibime}
DB_NAME=${DB_NAME:-alibime}
KEEP_DAYS=${KEEP_DAYS:-14}
stamp=$(date +%Y-%m-%d_%H%M)

mkdir -p "$BACKUP_DIR"
umask 077
pg_dump --format=custom --file="$BACKUP_DIR/alibime_$stamp.dump" "$DB_NAME"
find "$BACKUP_DIR" -name 'alibime_*.dump' -mtime +"$KEEP_DAYS" -delete
echo "backup: $BACKUP_DIR/alibime_$stamp.dump"
