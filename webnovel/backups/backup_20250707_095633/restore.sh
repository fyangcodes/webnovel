#!/bin/bash
# Restoration script for backup 20250707_095633
# Generated on 2025-07-07 09:56:33
# Usage: ./restore.sh [--skip-files] [--force]

set -e

BACKUP_DIR="$(dirname "$0")"
SKIP_FILES=false
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-files)
            SKIP_FILES=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-files] [--force]"
            exit 1
            ;;
    esac
done

echo "🔄 Starting restoration from backup 20250707_095633..."

# Check if backup exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# Confirm restoration
if [ "$FORCE" != "true" ]; then
    read -p "Are you sure you want to restore from $BACKUP_DIR? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Restoration cancelled."
        exit 0
    fi
fi

# 1. Restore database
echo "📊 Restoring database..."
if [ -d "$BACKUP_DIR/db_*.json" ]; then
    python manage.py loaddata $BACKUP_DIR/db_*.json
    echo "✅ Database restored successfully"
else
    echo "⚠️  No database fixtures found"
fi

# 2. Restore files
if [ "$SKIP_FILES" != "true" ] && [ -d "$BACKUP_DIR/files" ]; then
    echo "📁 Restoring files..."
    
    # Restore content files
    if [ -d "$BACKUP_DIR/files/content" ]; then
        cp -r $BACKUP_DIR/files/content/* media/content/ 2>/dev/null || mkdir -p media/content && cp -r $BACKUP_DIR/files/content/* media/content/
        echo "✅ Content files restored"
    fi
    
    # Restore image files
    if [ -d "$BACKUP_DIR/files/images" ]; then
        cp -r $BACKUP_DIR/files/images/* media/images/ 2>/dev/null || mkdir -p media/images && cp -r $BACKUP_DIR/files/images/* media/images/
        echo "✅ Image files restored"
    fi
    
    # Restore media files
    if [ -d "$BACKUP_DIR/files/media" ]; then
        cp -r $BACKUP_DIR/files/media/* media/ 2>/dev/null || mkdir -p media && cp -r $BACKUP_DIR/files/media/* media/
        echo "✅ Media files restored"
    fi
else
    echo "⏭️  Skipping file restoration"
fi

echo "✅ Restoration completed successfully!"
echo "🔄 You may need to restart your application server."
