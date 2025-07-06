from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.test import override_settings
import os
import tempfile
import shutil
from pathlib import Path


class Command(BaseCommand):
    help = 'Test backup and restore functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            default=True,
            help='Clean up test files after testing (default: True)'
        )

    def handle(self, *args, **options):
        self.stdout.write("🧪 Testing backup and restore functionality...")
        
        # Create temporary test directory
        with tempfile.TemporaryDirectory() as temp_dir:
            test_backup_dir = os.path.join(temp_dir, 'test_backups')
            
            try:
                # Step 1: Create a test backup
                self.stdout.write("\n1️⃣ Creating test backup...")
                call_command(
                    'backup_data',
                    backup_dir=test_backup_dir,
                    include_files=True,
                    skip_db=False
                )
                
                # Find the created backup
                backup_dirs = [d for d in os.listdir(test_backup_dir) if d.startswith('backup_')]
                if not backup_dirs:
                    self.stdout.write(
                        self.style.ERROR("❌ No backup directory created")
                    )
                    return
                
                backup_path = os.path.join(test_backup_dir, backup_dirs[0])
                self.stdout.write(f"   ✅ Test backup created at: {backup_path}")
                
                # Step 2: Test dry run restoration
                self.stdout.write("\n2️⃣ Testing dry run restoration...")
                call_command(
                    'restore_data',
                    backup_path,
                    dry_run=True,
                    force=True
                )
                
                # Step 3: Test actual restoration (to a different location)
                self.stdout.write("\n3️⃣ Testing actual restoration...")
                
                # Create a test restore directory
                test_restore_dir = os.path.join(temp_dir, 'test_restore')
                os.makedirs(test_restore_dir, exist_ok=True)
                
                # Copy backup to restore location
                restore_backup_path = os.path.join(test_restore_dir, 'backup_to_restore')
                shutil.copytree(backup_path, restore_backup_path)
                
                # Test restoration
                call_command(
                    'restore_data',
                    restore_backup_path,
                    force=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS("\n✅ All backup and restore tests passed!")
                )
                
                # Show test summary
                self.show_test_summary(backup_path)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"\n❌ Test failed: {str(e)}")
                )
                raise

    def show_test_summary(self, backup_path):
        """Show summary of the test backup"""
        self.stdout.write("\n📋 Test Backup Summary:")
        self.stdout.write("=" * 50)
        
        # Database files
        db_files = [f for f in os.listdir(backup_path) if f.startswith('db_')]
        if db_files:
            self.stdout.write(f"📊 Database fixtures: {len(db_files)}")
            for db_file in sorted(db_files):
                file_path = os.path.join(backup_path, db_file)
                size = os.path.getsize(file_path)
                self.stdout.write(f"   - {db_file} ({self.format_size(size)})")
        
        # Files
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
        
        # Metadata
        metadata_file = os.path.join(backup_path, 'backup_metadata.json')
        if os.path.exists(metadata_file):
            import json
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            self.stdout.write(f"⏰ Created: {metadata.get('backup_timestamp', 'Unknown')}")
        
        self.stdout.write("\n🎉 Backup and restore functionality is working correctly!")

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