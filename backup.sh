#!/bin/bash
# Backup hebdomadaire cabinet.db — samedi 1h du matin
# Cron : 0 1 * * 6

set -euo pipefail

BACKUP_DIR="/home/ubuntu/cabinet-juridique/backups"
DATE=$(date +%Y%m%d_%H%M)
FILENAME="cabinet_${DATE}.db.gz"
LOG="/home/ubuntu/cabinet-juridique/backups/backup.log"

mkdir -p "$BACKUP_DIR"

# Copie cohérente depuis le conteneur (évite les locks SQLite)
docker exec cabinet-juridique-app-1 cp /data/cabinet.db /tmp/cabinet_backup.db

# Extraction + compression
docker cp cabinet-juridique-app-1:/tmp/cabinet_backup.db - | gzip > "$BACKUP_DIR/$FILENAME"

# Nettoyage fichier temporaire dans le conteneur
docker exec cabinet-juridique-app-1 rm -f /tmp/cabinet_backup.db

# Rotation : conserver les 8 derniers backups (8 semaines)
ls -t "$BACKUP_DIR"/cabinet_*.db.gz 2>/dev/null | tail -n +9 | xargs -r rm --

echo "[$(date '+%Y-%m-%d %H:%M')] Backup OK : $FILENAME ($(du -h "$BACKUP_DIR/$FILENAME" | cut -f1))" >> "$LOG"
