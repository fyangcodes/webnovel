# S3 Backup and Restore Commands

This document describes the S3-based backup and restore functionality for the WebNovel application.

## Overview

The S3 backup system provides cloud-based backup storage for your database and file storage, making it easy to create and restore backups from Amazon S3.

## Prerequisites

1. **AWS Credentials**: Ensure your AWS credentials are configured in your environment:
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_S3_REGION_NAME=your_region
   export AWS_STORAGE_BUCKET_NAME=your_bucket
   ```

2. **Dependencies**: The required packages are already included in `requirements.txt`:
   - `boto3` - AWS SDK for Python
   - `django-storages` - Django storage backends

## Commands

### 1. S3 Backup Command

**Command**: `python manage.py backup_data_s3`

Creates a complete backup of your database and file storage, then uploads it to S3.

#### Options

- `--backup-name NAME`: Custom name for the backup (default: auto-generated timestamp)
- `--s3-prefix PREFIX`: S3 prefix/directory for backups (default: `backup`)
- `--include-files`: Include file storage backup (default: True)
- `--skip-files`: Skip file storage backup
- `--models MODEL1 MODEL2`: Specific models to backup (default: all)
- `--compress`: Compress backup files (default: True)
- `--skip-db`: Skip database backup, only backup files
- `--keep-local`: Keep local backup files after uploading to S3

#### Examples

```bash
# Create a backup with custom name
python manage.py backup_data_s3 --backup-name "production_backup_2024"

# Create backup without files
python manage.py backup_data_s3 --skip-files

# Create backup with specific models
python manage.py backup_data_s3 --models books.Book books.Chapter

# Create uncompressed backup
python manage.py backup_data_s3 --compress false
```

### 2. S3 Restore Command

**Command**: `python manage.py restore_data_s3 BACKUP_NAME`

Downloads a backup from S3 and restores your database and file storage.

#### Options

- `--s3-prefix PREFIX`: S3 prefix/directory for backups (default: `backup`)
- `--skip-files`: Skip file restoration, only restore database
- `--skip-db`: Skip database restoration, only restore files
- `--force`: Skip confirmation prompts
- `--dry-run`: Show what would be restored without actually doing it
- `--keep-download`: Keep downloaded backup files after restoration

#### Examples

```bash
# Restore from a specific backup
python manage.py restore_data_s3 production_backup_2024

# Dry run to see what would be restored
python manage.py restore_data_s3 production_backup_2024 --dry-run

# Restore only database
python manage.py restore_data_s3 production_backup_2024 --skip-files

# Force restore without confirmation
python manage.py restore_data_s3 production_backup_2024 --force
```

## S3 Storage Structure

Backups are stored in your S3 bucket with the following structure:

```
s3://your-bucket/
└── backup/
    ├── backup_20241201_143022/
    │   ├── backup_metadata.json
    │   ├── db_001_accounts_user.json
    │   ├── db_002_books_language.json
    │   ├── db_003_books_author.json
    │   ├── ...
    │   ├── files/
    │   │   ├── content/
    │   │   ├── images/
    │   │   └── media/
    │   └── restore_s3.sh
    └── backup_20241201_143022.tar.gz (compressed version)
```

## Backup Contents

### Database Fixtures
- All Django models are backed up as JSON fixtures
- Files are numbered to ensure proper restoration order
- Includes: User accounts, Books, Chapters, Media, Collaborators, etc.

### File Storage
- **Content files**: Book content and text files
- **Image files**: Book covers, user avatars, etc.
- **Media files**: Other uploaded files

### Metadata
- Backup timestamp and Django version
- Storage backend and database engine information
- Backup options and configuration

## Restoration Process

1. **Download**: Backup is downloaded from S3 to a temporary directory
2. **Validation**: Backup structure and metadata are validated
3. **Database**: JSON fixtures are loaded using Django's `loaddata` command
4. **Files**: Files are restored to the configured storage backend
5. **Cleanup**: Temporary files are removed (unless `--keep-download` is used)

## Security Considerations

1. **AWS IAM**: Use IAM roles with minimal required permissions
2. **Encryption**: Enable S3 server-side encryption for your bucket
3. **Access Control**: Configure bucket policies to restrict access
4. **Credentials**: Never commit AWS credentials to version control

## Troubleshooting

### Common Issues

1. **S3 Credentials Not Configured**
   ```
   ❌ S3 credentials not configured: NoCredentialsError
   ```
   **Solution**: Ensure AWS credentials are properly configured in your environment.

2. **Backup Not Found**
   ```
   ❌ Backup not found in S3: s3://bucket/backup/backup_name
   ```
   **Solution**: Verify the backup name and S3 prefix are correct.

3. **Permission Denied**
   ```
   ❌ S3 upload error: AccessDenied
   ```
   **Solution**: Check IAM permissions for S3 read/write access.

### Debugging

- Use `--dry-run` to see what would be restored without making changes
- Use `--keep-download` to inspect downloaded backup files
- Check S3 bucket logs for detailed error information

## Migration from Local Backups

If you have existing local backups created with `backup_data`, you can:

1. Upload them to S3 manually
2. Use the S3 restore command with the uploaded backup
3. Or continue using the local backup/restore commands

## Best Practices

1. **Regular Backups**: Set up automated backups using cron or Celery
2. **Backup Rotation**: Implement a policy to delete old backups
3. **Testing**: Regularly test restoration from backups
4. **Monitoring**: Monitor backup sizes and S3 costs
5. **Documentation**: Keep track of backup names and purposes

## Integration with CI/CD

You can integrate S3 backups into your deployment pipeline:

```bash
# Pre-deployment backup
python manage.py backup_data_s3 --backup-name "pre_deploy_$(date +%Y%m%d_%H%M%S)"

# Post-deployment verification
python manage.py restore_data_s3 backup_name --dry-run
```

## Cost Considerations

- S3 storage costs depend on backup size and retention period
- Consider using S3 lifecycle policies to move old backups to cheaper storage tiers
- Monitor data transfer costs for large backups 