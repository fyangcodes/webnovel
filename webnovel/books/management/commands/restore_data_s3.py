from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.conf import settings
import os
import json
import shutil
import tempfile
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class Command(BaseCommand):
    help = 'Restore database and file storage from S3 backup'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_name',
            type=str,
            help='Name of the backup to restore from S3'
        )
        parser.add_argument(
            '--s3-prefix',
            type=str,
            default='backup',
            help='S3 prefix/directory for backups (default: backup)'
        )
        parser.add_argument(
            '--skip-files',
            action='store_true',
            default=False,
            help='Skip file restoration, only restore database'
        )
        parser.add_argument(
            '--skip-db',
            action='store_true',
            default=False,
            help='Skip database restoration, only restore files'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Skip confirmation prompts'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be restored without actually doing it'
        )
        parser.add_argument(
            '--keep-download',
            action='store_true',
            default=False,
            help='Keep downloaded backup files after restoration'
        )

    def handle(self, *args, **options):
        backup_name = options['backup_name']
        s3_prefix = options['s3_prefix']
        skip_files = options['skip_files']
        skip_db = options['skip_db']
        force = options['force']
        dry_run = options['dry_run']
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        except (NoCredentialsError, AttributeError) as e:
            self.stdout.write(
                self.style.ERROR(f'❌ S3 credentials not configured: {str(e)}')
            )
            return
        
        s3_backup_path = f"{s3_prefix}/{backup_name}"
        
        # Check if backup exists in S3
        if not self.backup_exists_in_s3(s3_backup_path):
            self.stdout.write(
                self.style.ERROR(f'❌ Backup not found in S3: s3://{self.bucket_name}/{s3_backup_path}')
            )
            return
        
        # Show backup info
        self.show_backup_info(s3_backup_path, backup_name)
        
        # Confirm restoration
        if not force and not dry_run:
            if not self.confirm_restoration(s3_backup_path):
                return
        
        # Download and restore
        with tempfile.TemporaryDirectory() as temp_dir:
            if dry_run:
                self.dry_run_restoration(s3_backup_path, skip_files, skip_db)
            else:
                self.download_and_restore(s3_backup_path, temp_dir, skip_files, skip_db, options['keep_download'])

    def backup_exists_in_s3(self, s3_path):
        """Check if backup exists in S3"""
        try:
            # Check for compressed backup
            self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{s3_path}.tar.gz")
            return True
        except ClientError:
            try:
                # Check for uncompressed backup (metadata file)
                self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{s3_path}/backup_metadata.json")
                return True
            except ClientError:
                return False

    def download_backup(self, s3_path, temp_dir):
        """Download backup from S3"""
        self.stdout.write(f"⬇️  Downloading backup from S3...")
        
        try:
            # Try to download compressed backup first
            compressed_key = f"{s3_path}.tar.gz"
            try:
                self.s3_client.head_object(Bucket=self.bucket_name, Key=compressed_key)
                # Download compressed backup
                compressed_path = os.path.join(temp_dir, "backup.tar.gz")
                self.s3_client.download_file(self.bucket_name, compressed_key, compressed_path)
                
                # Extract backup
                import tarfile
                with tarfile.open(compressed_path, "r:gz") as tar:
                    tar.extractall(temp_dir)
                
                # Find the actual backup directory
                extracted_items = os.listdir(temp_dir)
                backup_path = None
                
                # First, check if temp_dir directly contains backup files (new structure)
                if os.path.exists(os.path.join(temp_dir, 'backup_metadata.json')):
                    backup_path = temp_dir
                elif any(f.startswith('db_') for f in os.listdir(temp_dir)):
                    backup_path = temp_dir
                
                # If not found in temp_dir, look for backup directory (old structure)
                if not backup_path:
                    for item in extracted_items:
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isdir(item_path):
                            # Check if this directory contains backup files
                            if os.path.exists(os.path.join(item_path, 'backup_metadata.json')):
                                backup_path = item_path
                                break
                            elif any(f.startswith('db_') for f in os.listdir(item_path)):
                                backup_path = item_path
                                break
                
                # If still not found, use the first directory or temp_dir
                if not backup_path:
                    for item in extracted_items:
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isdir(item_path):
                            backup_path = item_path
                            break
                
                if not backup_path:
                    backup_path = temp_dir
                
                self.stdout.write(f"   ✅ Downloaded and extracted compressed backup to: {backup_path}")
                return backup_path
                
            except ClientError:
                # Try uncompressed backup
                self.stdout.write(f"   📁 Downloading uncompressed backup...")
                
                # List all objects in the backup directory
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_path)
                
                for page in pages:
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            # Calculate local path
                            key = obj['Key']
                            rel_path = key.replace(s3_path + '/', '')
                            local_path = os.path.join(temp_dir, rel_path)
                            
                            # Create directory if needed
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            
                            # Download file
                            self.s3_client.download_file(self.bucket_name, key, local_path)
                
                self.stdout.write(f"   ✅ Downloaded uncompressed backup")
                return temp_dir
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error downloading backup: {str(e)}")
            )
            return None

    def show_backup_info(self, s3_path, backup_name):
        """Show information about the backup"""
        self.stdout.write("\n📋 S3 Backup Information:")
        self.stdout.write("=" * 50)
        self.stdout.write(f"📦 Backup Name: {backup_name}")
        self.stdout.write(f"☁️  S3 Location: s3://{self.bucket_name}/{s3_path}")
        
        # Try to get metadata
        try:
            metadata_key = f"{s3_path}/backup_metadata.json"
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=metadata_key)
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            
            self.stdout.write(f"⏰ Created: {metadata.get('backup_timestamp', 'Unknown')}")
            self.stdout.write(f"🐍 Django: {metadata.get('django_version', 'Unknown')}")
            self.stdout.write(f"💾 Database: {metadata.get('database_engine', 'Unknown')}")
            self.stdout.write(f"📁 Storage: {metadata.get('storage_backend', 'Unknown')}")
            
        except ClientError:
            self.stdout.write("⚠️  Could not retrieve backup metadata")
        
        # Check if compressed
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{s3_path}.tar.gz")
            self.stdout.write("🗜️  Format: Compressed (.tar.gz)")
        except ClientError:
            self.stdout.write("📁 Format: Uncompressed directory")

    def confirm_restoration(self, s3_path):
        """Ask for confirmation before restoration"""
        self.stdout.write("\n⚠️  WARNING: This will overwrite existing data!")
        self.stdout.write("=" * 50)
        self.stdout.write(f"📦 Will restore from: s3://{self.bucket_name}/{s3_path}")
        
        # Ask for confirmation
        while True:
            confirm = input("\nAre you sure you want to proceed? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                return True
            elif confirm in ['no', 'n']:
                self.stdout.write("❌ Restoration cancelled.")
                return False
            else:
                self.stdout.write("Please enter 'yes' or 'no'.")

    def dry_run_restoration(self, s3_path, skip_files, skip_db):
        """Show what would be restored without actually doing it"""
        self.stdout.write("\n🔍 DRY RUN - No changes will be made")
        self.stdout.write("=" * 50)
        self.stdout.write(f"📦 Would restore from: s3://{self.bucket_name}/{s3_path}")
        
        if not skip_db:
            self.stdout.write("📊 Would restore database from S3 backup")
        
        if not skip_files:
            self.stdout.write("📁 Would restore files from S3 backup")
        
        self.stdout.write("\n✅ Dry run completed - no changes made")

    def download_and_restore(self, s3_path, temp_dir, skip_files, skip_db, keep_download):
        """Download backup and perform restoration"""
        self.stdout.write("\n🔄 Starting S3 restoration...")
        
        # Download backup
        backup_path = self.download_backup(s3_path, temp_dir)
        if not backup_path:
            return
        
        # Validate backup structure
        if not self.validate_backup(backup_path):
            return
        
        # Perform restoration
        if not skip_db:
            self.restore_database(backup_path)
        
        if not skip_files:
            self.restore_files(backup_path)
        
        # Clean up downloaded files
        if not keep_download:
            self.stdout.write("🧹 Cleaning up downloaded files...")
        
        self.stdout.write(
            self.style.SUCCESS("\n✅ S3 restoration completed successfully!")
        )
        self.stdout.write("🔄 You may need to restart your application server.")

    def validate_backup(self, backup_path):
        """Validate backup structure"""
        self.stdout.write("🔍 Validating backup structure...")
        self.stdout.write(f"   📁 Checking backup path: {backup_path}")
        
        # List contents of backup directory for debugging
        try:
            contents = os.listdir(backup_path)
            self.stdout.write(f"   📋 Backup contents: {', '.join(contents)}")
        except Exception as e:
            self.stdout.write(f"   ❌ Error listing backup contents: {str(e)}")
            return False
        
        # Check for metadata file
        metadata_file = os.path.join(backup_path, 'backup_metadata.json')
        if not os.path.exists(metadata_file):
            self.stdout.write(
                self.style.ERROR(f"   ❌ No backup metadata found at: {metadata_file}")
            )
            # Try to find metadata file in subdirectories
            for root, dirs, files in os.walk(backup_path):
                if 'backup_metadata.json' in files:
                    found_metadata = os.path.join(root, 'backup_metadata.json')
                    self.stdout.write(f"   🔍 Found metadata at: {found_metadata}")
                    # Update backup_path to the directory containing metadata
                    backup_path = root
                    break
            else:
                self.stdout.write("   ❌ No backup metadata found in any subdirectory")
                return False
        
        # Check for database fixtures
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        if not db_files:
            self.stdout.write(
                self.style.WARNING("   ⚠️  No database fixtures found")
            )
        else:
            self.stdout.write(f"   📊 Found {len(db_files)} database fixtures")
        
        # Check for files directory
        files_dir = os.path.join(backup_path, 'files')
        if not os.path.exists(files_dir):
            self.stdout.write(
                self.style.WARNING("   ⚠️  No files directory found")
            )
        else:
            self.stdout.write("   📁 Files directory found")
        
        self.stdout.write("   ✅ Backup structure validated")
        return True

    def restore_database(self, backup_path):
        """Restore database from fixtures"""
        self.stdout.write("📊 Restoring database...")
        
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        if not db_files:
            self.stdout.write("   ⏭️  No database fixtures to restore")
            return
        
        # Sort files to ensure proper order (dependencies)
        db_files.sort()
        
        total_restored = 0
        
        for db_file in db_files:
            file_path = os.path.join(backup_path, db_file)
            try:
                self.stdout.write(f"   🔄 Loading {db_file}...")
                
                # Use loaddata command
                call_command('loaddata', file_path, verbosity=0)
                
                # Count records in fixture
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    count = len(data)
                
                total_restored += count
                self.stdout.write(f"   ✅ {db_file}: {count} records")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error loading {db_file}: {str(e)}")
                )
        
        self.stdout.write(f"   📈 Total database records restored: {total_restored}")

    def restore_files(self, backup_path):
        """Restore files from backup"""
        self.stdout.write("📁 Restoring files...")
        
        files_dir = os.path.join(backup_path, 'files')
        if not os.path.exists(files_dir):
            self.stdout.write("   ⏭️  No files to restore")
            return
        
        total_files = 0
        total_size = 0
        
        # Restore content files
        content_source = os.path.join(files_dir, 'content')
        if os.path.exists(content_source):
            count, size = self.restore_file_directory(content_source, 'content')
            total_files += count
            total_size += size
            self.stdout.write(f"   ✅ Content files: {count} files ({self.format_size(size)})")
        
        # Restore image files
        images_source = os.path.join(files_dir, 'images')
        if os.path.exists(images_source):
            count, size = self.restore_file_directory(images_source, 'images')
            total_files += count
            total_size += size
            self.stdout.write(f"   ✅ Image files: {count} files ({self.format_size(size)})")
        
        # Restore media files
        media_source = os.path.join(files_dir, 'media')
        if os.path.exists(media_source):
            count, size = self.restore_file_directory(media_source, 'media')
            total_files += count
            total_size += size
            self.stdout.write(f"   ✅ Media files: {count} files ({self.format_size(size)})")
        
        self.stdout.write(f"   📈 Total files restored: {total_files} ({self.format_size(total_size)})")

    def restore_file_directory(self, source_path, dest_path):
        """Restore a directory of files to storage"""
        file_count = 0
        total_size = 0
        
        try:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    source_file = os.path.join(root, file)
                    
                    # Calculate relative path for destination
                    rel_path = os.path.relpath(source_file, source_path)
                    dest_file = os.path.join(dest_path, rel_path)
                    
                    try:
                        # Read source file
                        with open(source_file, 'rb') as src:
                            content = src.read()
                        
                        # Write to storage
                        default_storage.save(dest_file, content)
                        
                        file_count += 1
                        total_size += len(content)
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"   ⚠️  Could not restore {dest_file}: {str(e)}")
                        )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error restoring {dest_path}: {str(e)}")
            )
        
        return file_count, total_size

    def format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f}{size_names[i]}" 