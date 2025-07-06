#!/usr/bin/env bash
set -e  # Exit on any error

# Apply migrations
python webnovel/manage.py migrate

# Create superuser (interactive, see note below)
python webnovel/manage.py createsuperuser

# Load initial data (user first, then books)
python webnovel/manage.py loaddata webnovel/webnovel/fixtures/books_complete.json

# Load llm providers
python webnovel/manage.py setup_llm_providers

echo "Project initialized!"