from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.conf import settings
import os
import json
import shutil
from pathlib import Path


class Command(BaseCommand):
    help = 'Restore database and file storage from backup'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_path',
            type=str,
            help='Path to backup directory or compressed archive'
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

    def handle(self, *args, **options):
        backup_path = options['backup_path']
        skip_files = options['skip_files']
        skip_db = options['skip_db']
        force = options['force']
        dry_run = options['dry_run']
        
        # Check if backup exists
        if not os.path.exists(backup_path):
            self.stdout.write(
                self.style.ERROR(f'❌ Backup not found: {backup_path}')
            )
            return
        
        # Handle compressed backups
        if backup_path.endswith('.tar.gz'):
            backup_path = self.extract_backup(backup_path)
        
        # Validate backup structure
        if not self.validate_backup(backup_path):
            return
        
        # Show backup info
        self.show_backup_info(backup_path)
        
        # Confirm restoration
        if not force and not dry_run:
            if not self.confirm_restoration(backup_path):
                return
        
        # Perform restoration
        if dry_run:
            self.dry_run_restoration(backup_path, skip_files, skip_db)
        else:
            self.perform_restoration(backup_path, skip_files, skip_db)

    def extract_backup(self, archive_path):
        """Extract compressed backup"""
        self.stdout.write(f"🗜️  Extracting backup from: {archive_path}")
        
        try:
            import tarfile
            
            # Create extraction directory
            extract_dir = archive_path.replace('.tar.gz', '_extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            # Extract archive
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(extract_dir)
            
            # Find the actual backup directory
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                backup_path = os.path.join(extract_dir, extracted_items[0])
            else:
                backup_path = extract_dir
            
            self.stdout.write(f"   ✅ Extracted to: {backup_path}")
            return backup_path
            
        except ImportError:
            self.stdout.write(
                self.style.ERROR("   ❌ tarfile module not available")
            )
            return None
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error extracting backup: {str(e)}")
            )
            return None

    def validate_backup(self, backup_path):
        """Validate backup structure"""
        self.stdout.write("🔍 Validating backup structure...")
        
        # Check for metadata file
        metadata_file = os.path.join(backup_path, 'backup_metadata.json')
        if not os.path.exists(metadata_file):
            self.stdout.write(
                self.style.ERROR("   ❌ No backup metadata found")
            )
            return False
        
        # Check for database fixtures
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        if not db_files:
            self.stdout.write(
                self.style.WARNING("   ⚠️  No database fixtures found")
            )
        
        # Check for files directory
        files_dir = os.path.join(backup_path, 'files')
        if not os.path.exists(files_dir):
            self.stdout.write(
                self.style.WARNING("   ⚠️  No files directory found")
            )
        
        self.stdout.write("   ✅ Backup structure validated")
        return True

    def show_backup_info(self, backup_path):
        """Show information about the backup"""
        self.stdout.write("\n📋 Backup Information:")
        self.stdout.write("=" * 50)
        
        # Load metadata
        metadata_file = os.path.join(backup_path, 'backup_metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            self.stdout.write(f"⏰ Created: {metadata.get('backup_timestamp', 'Unknown')}")
            self.stdout.write(f"🐍 Django: {metadata.get('django_version', 'Unknown')}")
            self.stdout.write(f"💾 Database: {metadata.get('database_engine', 'Unknown')}")
            self.stdout.write(f"📁 Storage: {metadata.get('storage_backend', 'Unknown')}")
        
        # Database summary
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        if db_files:
            self.stdout.write(f"📊 Database: {len(db_files)} model fixtures")
            for db_file in sorted(db_files):
                self.stdout.write(f"   - {db_file}")
        
        # Files summary
        files_dir = os.path.join(backup_path, 'files')
        if os.path.exists(files_dir):
            total_files = 0
            total_size = 0
            
            for root, dirs, files in os.walk(files_dir):
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            self.stdout.write(f"📁 Files: {total_files} files ({self.format_size(total_size)})")
            
            # Show file categories
            for subdir in ['content', 'images', 'media']:
                subdir_path = os.path.join(files_dir, subdir)
                if os.path.exists(subdir_path):
                    count = sum([len(files) for r, d, files in os.walk(subdir_path)])
                    self.stdout.write(f"   - {subdir}: {count} files")

    def confirm_restoration(self, backup_path):
        """Ask for confirmation before restoration"""
        self.stdout.write("\n⚠️  WARNING: This will overwrite existing data!")
        self.stdout.write("=" * 50)
        
        # Show what will be restored
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        files_dir = os.path.join(backup_path, 'files')
        
        if db_files:
            self.stdout.write("📊 Database will be restored from:")
            for db_file in sorted(db_files):
                self.stdout.write(f"   - {db_file}")
        
        if os.path.exists(files_dir):
            self.stdout.write("📁 Files will be restored from:")
            for subdir in ['content', 'images', 'media']:
                subdir_path = os.path.join(files_dir, subdir)
                if os.path.exists(subdir_path):
                    count = sum([len(files) for r, d, files in os.walk(subdir_path)])
                    self.stdout.write(f"   - {subdir}: {count} files")
        
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

    def dry_run_restoration(self, backup_path, skip_files, skip_db):
        """Show what would be restored without actually doing it"""
        self.stdout.write("\n🔍 DRY RUN - No changes will be made")
        self.stdout.write("=" * 50)
        
        if not skip_db:
            self.stdout.write("📊 Would restore database from:")
            db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
            for db_file in sorted(db_files):
                self.stdout.write(f"   - {db_file}")
        
        if not skip_files:
            files_dir = os.path.join(backup_path, 'files')
            if os.path.exists(files_dir):
                self.stdout.write("📁 Would restore files from:")
                for subdir in ['content', 'images', 'media']:
                    subdir_path = os.path.join(files_dir, subdir)
                    if os.path.exists(subdir_path):
                        count = sum([len(files) for r, d, files in os.walk(subdir_path)])
                        size = sum([os.path.getsize(os.path.join(r, f)) for r, d, files in os.walk(subdir_path) for f in files])
                        self.stdout.write(f"   - {subdir}: {count} files ({self.format_size(size)})")
        
        self.stdout.write("\n✅ Dry run completed - no changes made")

    def perform_restoration(self, backup_path, skip_files, skip_db):
        """Perform the actual restoration"""
        self.stdout.write("\n🔄 Starting restoration...")
        
        # 1. Restore database
        if not skip_db:
            self.restore_database(backup_path)
        
        # 2. Restore files
        if not skip_files:
            self.restore_files(backup_path)
        
        self.stdout.write(
            self.style.SUCCESS("\n✅ Restoration completed successfully!")
        )
        self.stdout.write("🔄 You may need to restart your application server.")

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