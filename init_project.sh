#!/usr/bin/env bash
set -e  # Exit on any error

# Apply migrations
python webnovel/manage.py migrate

# Load initial data
python webnovel/manage.py loaddata webnovel/fixtures/books_complete.json

# Load llm providers
python webnovel/manage.py setup_llm_providers

# Create superuser (interactive, see note below)
python webnovel/manage.py createsuperuser

echo "Project initialized!"