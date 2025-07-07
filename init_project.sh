#!/usr/bin/env bash
set -e  # Exit on any error

# Apply migrations
python webnovel/manage.py migrate

# Load backup data
python webnovel/manage.py restore_data webnovel/backups/backup_20250707_095633

# Load llm providers
python webnovel/manage.py setup_llm_providers

echo "Project initialized!"