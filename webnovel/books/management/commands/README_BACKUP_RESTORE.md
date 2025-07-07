# Backup and Restore Commands

This document describes the backup and restore functionality for the webnovel platform.

## Commands Overview

### 1. `backup_data` - Create Complete Backup
Creates a comprehensive backup of both database and file storage.

### 2. `restore_data` - Restore from Backup
Restores database and file storage from a previously created backup.

### 3. `test_backup_restore` - Test Functionality
Tests the backup and restore functionality to ensure it works correctly.

## Usage Examples

### Creating Backups

```bash
# Basic backup (database + files)
python manage.py backup_data

# Backup to specific directory
python manage.py backup_data --backup-dir /path/to/backups

# Backup only database (skip files)
python manage.py backup_data --skip-files

# Backup only files (skip database)
python manage.py backup_data --skip-db

# Backup specific models only
python manage.py backup_data --models books.Book books.Chapter accounts.User

# Compress backup
python manage.py backup_data --compress

# Backup files only
python manage.py backup_data --skip-db --include-files
```

### Restoring from Backups

```bash
# Restore from backup directory
python manage.py restore_data /path/to/backup_20241201_143022

# Restore from compressed backup
python manage.py restore_data /path/to/backup_20241201_143022.tar.gz

# Dry run (show what would be restored)
python manage.py restore_data /path/to/backup --dry-run

# Force restore (skip confirmation)
python manage.py restore_data /path/to/backup --force

# Restore only database
python manage.py restore_data /path/to/backup --skip-files

# Restore only files
python manage.py restore_data /path/to/backup --skip-db
```

### Testing the Commands

```bash
# Test backup and restore functionality
python manage.py test_backup_restore
```

## Backup Structure

Each backup creates a directory with the following structure:

```
backup_YYYYMMDD_HHMMSS/
├── backup_metadata.json          # Backup metadata and options
├── restore.sh                    # Shell script for restoration
├── db_books_language.json        # Database fixtures
├── db_books_author.json
├── db_accounts_user.json
├── db_books_book.json
├── db_books_chapter.json
├── db_books_chaptermedia.json
├── db_books_bookfile.json
├── db_books_changelog.json
├── db_accounts_bookcollaborator.json
├── db_accounts_translationassignment.json
└── files/                        # File storage backup
    ├── content/                  # Chapter content JSON files
    ├── images/                   # Chapter images
    └── media/                    # Other media files
```

## Backup Metadata

The `backup_metadata.json` file contains:

```json
{
  "backup_timestamp": "2024-12-01T14:30:22.123456",
  "django_version": "4.2.0",
  "backup_options": {
    "include_files": true,
    "skip_db": false,
    "compress": false,
    "models": "all"
  },
  "storage_backend": "FileSystemStorage",
  "database_engine": "django.db.backends.sqlite3"
}
```

## Models Backed Up

The backup includes all models in dependency order:

### Books App
- `Language` - Book languages
- `Author` - Book authors
- `Book` - Books
- `Chapter` - Book chapters
- `ChapterMedia` - Chapter media (images, audio, video, documents)
- `BookFile` - Book files
- `ChangeLog` - Chapter change logs

### Accounts App
- `User` - User accounts
- `BookCollaborator` - Book collaborators
- `TranslationAssignment` - Translation assignments

## File Storage Backup

The backup handles different storage backends:

### Local File System
- Copies files directly from the filesystem
- Maintains directory structure
- Preserves file permissions

### S3/Cloud Storage
- Downloads files from cloud storage
- Stores locally in backup
- Compatible with Django's storage abstraction

## Restoration Process

### Database Restoration
1. Validates backup structure
2. Loads fixtures in dependency order
3. Handles foreign key relationships
4. Reports success/failure for each model

### File Restoration
1. Creates necessary directories
2. Copies files to storage backend
3. Maintains original file structure
4. Handles different storage backends

## Safety Features

### Confirmation Prompts
- Restore commands ask for confirmation by default
- Use `--force` to skip confirmation
- Use `--dry-run` to preview without changes

### Validation
- Validates backup structure before restoration
- Checks for required metadata
- Verifies file integrity

### Error Handling
- Graceful handling of missing files
- Detailed error reporting
- Continues restoration on partial failures

## Best Practices

### Regular Backups
```bash
# Create daily backup
python manage.py backup_data --backup-dir /backups/daily --compress

# Create weekly backup
python manage.py backup_data --backup-dir /backups/weekly --compress
```

### Automated Backups
Add to crontab for automated backups:

```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/webnovel && python manage.py backup_data --backup-dir /backups/daily --compress

# Weekly backup on Sunday at 3 AM
0 3 * * 0 cd /path/to/webnovel && python manage.py backup_data --backup-dir /backups/weekly --compress
```

### Testing Restorations
```bash
# Test restoration in development environment
python manage.py restore_data /path/to/backup --dry-run

# Test actual restoration
python manage.py restore_data /path/to/backup --force
```

### Backup Rotation
Implement backup rotation to manage disk space:

```bash
# Keep only last 7 daily backups
find /backups/daily -name "backup_*" -type d -mtime +7 -exec rm -rf {} \;

# Keep only last 4 weekly backups
find /backups/weekly -name "backup_*" -type d -mtime +28 -exec rm -rf {} \;
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   # Fix permissions
   chmod -R 755 /path/to/backup
   ```

2. **Storage Backend Issues**
   ```bash
   # Test storage access
   python manage.py shell
   >>> from django.core.files.storage import default_storage
   >>> default_storage.exists('content')
   ```

3. **Database Connection Issues**
   ```bash
   # Test database connection
   python manage.py dbshell
   ```

4. **Insufficient Disk Space**
   ```bash
   # Check available space
   df -h /path/to/backup
   ```

### Recovery Procedures

1. **Partial Backup Failure**
   - Check error logs
   - Retry with specific models
   - Verify storage permissions

2. **Restoration Failure**
   - Use `--dry-run` to identify issues
   - Check backup integrity
   - Restore in stages (db first, then files)

3. **Data Corruption**
   - Use previous backup
   - Verify backup integrity
   - Test restoration in isolated environment

## Integration with CI/CD

### Pre-deployment Backup
```yaml
# In your deployment pipeline
- name: Create backup before deployment
  run: |
    python manage.py backup_data --backup-dir /backups/pre-deploy
    python manage.py test_backup_restore
```

### Post-deployment Verification
```yaml
# Verify backup functionality after deployment
- name: Test backup functionality
  run: python manage.py test_backup_restore
```

## Monitoring and Alerts

### Backup Monitoring
- Monitor backup completion
- Check backup size and duration
- Alert on backup failures

### Storage Monitoring
- Monitor backup storage usage
- Implement backup rotation
- Alert on disk space issues

## Security Considerations

### Backup Security
- Encrypt sensitive backups
- Secure backup storage
- Implement access controls

### Restoration Security
- Validate backup sources
- Test restorations in isolation
- Document restoration procedures 