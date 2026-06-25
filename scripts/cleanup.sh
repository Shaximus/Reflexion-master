#!/bin/bash
# Reflexion Cleanup Script
# Removes old cache, compresses logs, backs up databases

echo "Starting Reflexion cleanup..."

# Remove cache older than 7 days
find cache/ -type f -mtime +7 -delete 2>/dev/null
echo "  [OK] Cleared old cache files"

# Compress old logs
find logs/ -name "*.log" -mtime +30 -exec gzip {} \; 2>/dev/null
echo "  [OK] Compressed old logs"

# Backup databases
cp souls.db "data/memory_backups/souls_$(date +%Y%m%d).db" 2>/dev/null
cp accounts.db "data/memory_backups/accounts_$(date +%Y%m%d).db" 2>/dev/null
echo "  [OK] Backed up databases"

# Remove old screenshots
find logs/screenshots/ -name "*.png" -mtime +7 -delete 2>/dev/null
echo "  [OK] Cleared old screenshots"

echo "Cleanup complete!"
