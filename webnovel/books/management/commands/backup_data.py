from django.core.management.base import BaseCommand
from django.core import serializers
from django.core.files.storage import default_storage
from django.conf import settings
import django
import os
import json
import shutil
from datetime import datetime
from pathlib import Path


class Command(BaseCommand):
    help = "Create complete backup of database and file storage"

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-dir",
            type=str,
            default="backups",
            help="Directory to store backups (default: backups)",
        )
        parser.add_argument(
            "--include-files",
            action="store_true",
            default=True,
            help="Include file storage backup (default: True)",
        )
        parser.add_argument(
            "--skip-files",
            action="store_true",
            default=False,
            help="Skip file storage backup (overrides --include-files)",
        )
        parser.add_argument(
            "--models", nargs="+", help="Specific models to backup (default: all)"
        )
        parser.add_argument(
            "--compress",
            action="store_true",
            default=False,
            help="Compress backup files",
        )
        parser.add_argument(
            "--skip-db",
            action="store_true",
            default=False,
            help="Skip database backup, only backup files",
        )

    def handle(self, *args, **options):
        backup_dir = options["backup_dir"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/backup_{timestamp}"

        self.stdout.write(f"Creating backup at: {backup_path}")

        # Create backup directory
        os.makedirs(backup_path, exist_ok=True)

        # 1. Backup database as fixture
        if not options["skip_db"]:
            self.backup_database(backup_path, options["models"])

        # 2. Backup file storage
        if options["include_files"] and not options["skip_files"]:
            self.backup_files(backup_path)

        # 3. Create metadata file
        self.create_metadata(backup_path, options)

        # 4. Create restoration script
        self.create_restore_script(backup_path, timestamp, options)

        # 5. Compress if requested
        if options["compress"]:
            self.compress_backup(backup_path)

        self.stdout.write(
            self.style.SUCCESS(f"✅ Backup created successfully at: {backup_path}")
        )

        # Show backup summary
        self.show_backup_summary(backup_path)

    def backup_database(self, backup_path, specific_models=None):
        """Backup database as fixture"""
        self.stdout.write("📊 Backing up database...")

        # Define models to backup (in dependency order)
        from books.models import (
            Language,
            Author,
            Book,
            Chapter,
            ChapterMedia,
            BookFile,
            ChangeLog,
        )
        from accounts.models import User
        from collaboration.models import BookCollaborator, TranslationAssignment

        all_models = [
            (User, "accounts"),
            (Language, "books"),
            (Author, "books"),
            (Book, "books"),
            (Chapter, "books"),
            (ChapterMedia, "books"),
            (BookFile, "books"),
            (ChangeLog, "books"),
            (BookCollaborator, "collaboration"),
            (TranslationAssignment, "collaboration"),
        ]

        # Filter models if specific ones requested
        if specific_models:
            filtered_models = []
            for model, app in all_models:
                model_name = f"{app}.{model._meta.model_name}"
                if (
                    model_name in specific_models
                    or model._meta.model_name in specific_models
                ):
                    filtered_models.append((model, app))
            all_models = filtered_models

        total_records = 0

        for idx, (model, app) in enumerate(all_models, start=1):
            try:
                count = model.objects.count()
                if count == 0:
                    self.stdout.write(
                        f"   ⏭️  Skipping {model._meta.model_name} (no records)"
                    )
                    continue

                # Add numeric prefix to filename for dependency order
                filename = f"{backup_path}/db_{idx:03d}_{app}_{model._meta.model_name}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    serializers.serialize(
                        "json", model.objects.all(), stream=f, indent=2
                    )

                total_records += count
                self.stdout.write(f"   ✅ {model._meta.model_name}: {count} records")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Error backing up {model._meta.model_name}: {str(e)}"
                    )
                )

        self.stdout.write(f"   📈 Total database records: {total_records}")

    def backup_files(self, backup_path):
        """Backup file storage"""
        self.stdout.write("📁 Backing up files...")

        files_dir = f"{backup_path}/files"
        os.makedirs(files_dir, exist_ok=True)

        total_files = 0
        total_size = 0

        # Backup content files
        content_dir = f"{files_dir}/content"
        if default_storage.exists("content"):
            count, size = self.copy_storage_directory("content", content_dir)
            total_files += count
            total_size += size
            self.stdout.write(
                f"   ✅ Content files: {count} files ({self.format_size(size)})"
            )
        else:
            self.stdout.write("   ⏭️  No content files to backup")

        # Backup image files
        images_dir = f"{files_dir}/images"
        if default_storage.exists("images"):
            count, size = self.copy_storage_directory("images", images_dir)
            total_files += count
            total_size += size
            self.stdout.write(
                f"   ✅ Image files: {count} files ({self.format_size(size)})"
            )
        else:
            self.stdout.write("   ⏭️  No image files to backup")

        # Backup media files (if different from content/images)
        media_dir = f"{files_dir}/media"
        if default_storage.exists("media") and not default_storage.exists("content"):
            count, size = self.copy_storage_directory("media", media_dir)
            total_files += count
            total_size += size
            self.stdout.write(
                f"   ✅ Media files: {count} files ({self.format_size(size)})"
            )

        self.stdout.write(
            f"   📈 Total files: {total_files} ({self.format_size(total_size)})"
        )

    def copy_storage_directory(self, source_path, dest_path):
        """Copy storage directory recursively"""
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        file_count = 0
        total_size = 0

        try:
            for root, dirs, files in default_storage.walk(source_path):
                # Create local directory structure
                local_root = root.replace(source_path, dest_path)
                os.makedirs(local_root, exist_ok=True)

                # Copy files
                for file in files:
                    source_file = os.path.join(root, file)
                    dest_file = os.path.join(local_root, file)

                    try:
                        with default_storage.open(source_file, "rb") as src:
                            content = src.read()
                            with open(dest_file, "wb") as dst:
                                dst.write(content)

                        file_count += 1
                        total_size += len(content)

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   ⚠️  Could not copy {source_file}: {str(e)}"
                            )
                        )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"   ❌ Error walking directory {source_path}: {str(e)}"
                )
            )

        return file_count, total_size

    def create_metadata(self, backup_path, options):
        """Create metadata file for the backup"""
        metadata = {
            "backup_timestamp": datetime.now().isoformat(),
            "django_version": django.get_version(),
            "backup_options": {
                "include_files": options["include_files"],
                "skip_db": options["skip_db"],
                "compress": options["compress"],
                "models": options["models"] if options["models"] else "all",
            },
            "storage_backend": str(default_storage.__class__.__name__),
            "database_engine": settings.DATABASES["default"]["ENGINE"],
        }

        metadata_file = f"{backup_path}/backup_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.stdout.write("   ✅ Created backup metadata")

    def create_restore_script(self, backup_path, timestamp, options):
        """Create restoration script"""
        script_content = f"""#!/bin/bash
# Restoration script for backup {timestamp}
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
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

echo "🔄 Starting restoration from backup {timestamp}..."

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
"""

        script_path = f"{backup_path}/restore.sh"
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

        self.stdout.write("   ✅ Created restoration script")

    def compress_backup(self, backup_path):
        """Compress the backup directory"""
        self.stdout.write("🗜️  Compressing backup...")

        try:
            import tarfile

            archive_name = f"{backup_path}.tar.gz"
            with tarfile.open(archive_name, "w:gz") as tar:
                tar.add(backup_path, arcname=os.path.basename(backup_path))

            # Remove uncompressed directory
            shutil.rmtree(backup_path)

            self.stdout.write(f"   ✅ Backup compressed to: {archive_name}")

        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠️  tarfile module not available, skipping compression"
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error compressing backup: {str(e)}")
            )

    def show_backup_summary(self, backup_path):
        """Show summary of the backup"""
        self.stdout.write("\n📋 Backup Summary:")
        self.stdout.write("=" * 50)

        # Database summary
        db_files = [f for f in os.listdir(backup_path) if f.startswith("db_")]
        if db_files:
            self.stdout.write(f"📊 Database: {len(db_files)} model fixtures")

        # Files summary
        files_dir = os.path.join(backup_path, "files")
        if os.path.exists(files_dir):
            total_files = 0
            total_size = 0

            for root, dirs, files in os.walk(files_dir):
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)

            self.stdout.write(
                f"📁 Files: {total_files} files ({self.format_size(total_size)})"
            )

        # Metadata
        metadata_file = os.path.join(backup_path, "backup_metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
            self.stdout.write(f"⏰ Created: {metadata['backup_timestamp']}")

        # Restoration instructions
        self.stdout.write("\n🔄 To restore this backup:")
        self.stdout.write(f"   python manage.py restore_data {backup_path}")
        self.stdout.write(f"   or run: {backup_path}/restore.sh")

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
