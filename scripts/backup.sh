#!/bin/bash
# Reflexion Backup Script
# Creates timestamped backup of all critical data

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/reflexion_$TIMESTAMP"

echo "Starting Reflexion backup..."

mkdir -p "$BACKUP_DIR"

# Backup databases
cp souls.db "$BACKUP_DIR/" 2>/dev/null
cp accounts.db "$BACKUP_DIR/" 2>/dev/null
cp viral_performance.db "$BACKUP_DIR/" 2>/dev/null

# Backup state
cp -r state/ "$BACKUP_DIR/" 2>/dev/null

# Backup souls data
cp -r data/souls/ "$BACKUP_DIR/" 2>/dev/null

# Backup metrics
cp -r metrics/ "$BACKUP_DIR/" 2>/dev/null

# Compress backup
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "[OK] Backup complete: $BACKUP_DIR.tar.gz"
