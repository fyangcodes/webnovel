from django.core.management.base import BaseCommand
from django.core import serializers
from django.core.files.storage import default_storage
from django.conf import settings
import django
import os
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class Command(BaseCommand):
    help = "Create complete backup of database and file storage to S3"

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-name",
            type=str,
            help="Custom name for the backup (default: auto-generated timestamp)",
        )
        parser.add_argument(
            "--s3-prefix",
            type=str,
            default="backup",
            help="S3 prefix/directory for backups (default: backup)",
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
            default=True,
            help="Compress backup files (default: True)",
        )
        parser.add_argument(
            "--skip-db",
            action="store_true",
            default=False,
            help="Skip database backup, only backup files",
        )
        parser.add_argument(
            "--keep-local",
            action="store_true",
            default=False,
            help="Keep local backup files after uploading to S3",
        )

    def handle(self, *args, **options):
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
                self.style.ERROR(f"❌ S3 credentials not configured: {str(e)}")
            )
            return

        # Generate backup name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = options["backup_name"] or f"backup_{timestamp}"
        s3_prefix = options["s3_prefix"]
        s3_backup_path = f"{s3_prefix}/{backup_name}"

        # Create temporary local directory
        with tempfile.TemporaryDirectory() as temp_dir:
            self.stdout.write(f"Creating backup: {backup_name}")
            self.stdout.write(f"S3 location: s3://{self.bucket_name}/{s3_backup_path}")

            # 1. Backup database as fixture
            if not options["skip_db"]:
                self.backup_database(temp_dir, options["models"])

            # 2. Backup file storage
            if options["include_files"] and not options["skip_files"]:
                self.backup_files(temp_dir)

            # 3. Create metadata file
            self.create_metadata(temp_dir, options, backup_name)

            # 4. Create restoration script
            self.create_restore_script(temp_dir, backup_name, options)

            # 5. Compress if requested
            if options["compress"]:
                archive_path = self.compress_backup(temp_dir, backup_name)
                upload_path = archive_path
            else:
                upload_path = temp_dir

            # 6. Upload to S3
            self.upload_to_s3(upload_path, s3_backup_path, options["compress"])

            # 7. Clean up local files
            if not options["keep_local"] and options["compress"]:
                os.remove(archive_path)

        self.stdout.write(
            self.style.SUCCESS(f"✅ Backup uploaded successfully to S3: s3://{self.bucket_name}/{s3_backup_path}")
        )

        # Show backup summary
        self.show_backup_summary(s3_backup_path, backup_name)

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

    def create_metadata(self, backup_path, options, backup_name):
        """Create metadata file for the backup"""
        metadata = {
            "backup_name": backup_name,
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
            "s3_bucket": self.bucket_name,
            "s3_region": settings.AWS_S3_REGION_NAME,
        }

        metadata_file = f"{backup_path}/backup_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        self.stdout.write("   ✅ Created backup metadata")

    def create_restore_script(self, backup_path, backup_name, options):
        """Create restoration script"""
        script_content = f"""#!/bin/bash
# S3 Restoration script for backup {backup_name}
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Usage: ./restore_s3.sh [--skip-files] [--force]

set -e

BACKUP_NAME="{backup_name}"
S3_BUCKET="{self.bucket_name}"
S3_PREFIX="{options.get('s3_prefix', 'backup')}"
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

echo "🔄 Starting S3 restoration from backup {backup_name}..."

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Confirm restoration
if [ "$FORCE" != "true" ]; then
    read -p "Are you sure you want to restore from s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Restoration cancelled."
        exit 0
    fi
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Using temporary directory: $TEMP_DIR"

# Download backup from S3
echo "⬇️  Downloading backup from S3..."
if aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME.tar.gz" &> /dev/null; then
    # Compressed backup
    aws s3 cp "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME.tar.gz" "$TEMP_DIR/"
    tar -xzf "$TEMP_DIR/$BACKUP_NAME.tar.gz" -C "$TEMP_DIR"
    # The backup files are now directly in TEMP_DIR, not in a subdirectory
    BACKUP_DIR="$TEMP_DIR"
else
    # Uncompressed backup
    aws s3 sync "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME" "$TEMP_DIR/$BACKUP_NAME"
    BACKUP_DIR="$TEMP_DIR/$BACKUP_NAME"
fi

# 1. Restore database
echo "📊 Restoring database..."
if [ -d "$BACKUP_DIR" ] && ls "$BACKUP_DIR"/db_*.json 1> /dev/null 2>&1; then
    python manage.py loaddata "$BACKUP_DIR"/db_*.json
    echo "✅ Database restored successfully"
else
    echo "⚠️  No database fixtures found"
fi

# 2. Restore files
if [ "$SKIP_FILES" != "true" ] && [ -d "$BACKUP_DIR/files" ]; then
    echo "📁 Restoring files..."
    
    # Restore content files
    if [ -d "$BACKUP_DIR/files/content" ]; then
        cp -r "$BACKUP_DIR/files/content"/* media/content/ 2>/dev/null || mkdir -p media/content && cp -r "$BACKUP_DIR/files/content"/* media/content/
        echo "✅ Content files restored"
    fi
    
    # Restore image files
    if [ -d "$BACKUP_DIR/files/images" ]; then
        cp -r "$BACKUP_DIR/files/images"/* media/images/ 2>/dev/null || mkdir -p media/images && cp -r "$BACKUP_DIR/files/images"/* media/images/
        echo "✅ Image files restored"
    fi
    
    # Restore media files
    if [ -d "$BACKUP_DIR/files/media" ]; then
        cp -r "$BACKUP_DIR/files/media"/* media/ 2>/dev/null || mkdir -p media && cp -r "$BACKUP_DIR/files/media"/* media/
        echo "✅ Media files restored"
    fi
else
    echo "⏭️  Skipping file restoration"
fi

# Clean up
rm -rf "$TEMP_DIR"
echo "🧹 Temporary files cleaned up"

echo "✅ S3 restoration completed successfully!"
echo "🔄 You may need to restart your application server."
"""

        script_path = f"{backup_path}/restore_s3.sh"
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

        self.stdout.write("   ✅ Created S3 restoration script")

    def compress_backup(self, backup_path, backup_name):
        """Compress the backup directory"""
        self.stdout.write("🗜️  Compressing backup...")

        try:
            import tarfile

            archive_name = f"{backup_path}/{backup_name}.tar.gz"
            with tarfile.open(archive_name, "w:gz") as tar:
                # Add the contents of backup_path, not the directory itself
                for item in os.listdir(backup_path):
                    item_path = os.path.join(backup_path, item)
                    tar.add(item_path, arcname=item)

            self.stdout.write(f"   ✅ Backup compressed to: {archive_name}")
            return archive_name

        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠️  tarfile module not available, skipping compression"
                )
            )
            return None
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error compressing backup: {str(e)}")
            )
            return None

    def upload_to_s3(self, source_path, s3_path, is_compressed):
        """Upload backup to S3"""
        self.stdout.write("☁️  Uploading to S3...")

        try:
            if is_compressed and os.path.isfile(source_path):
                # Upload single compressed file
                self.s3_client.upload_file(
                    source_path,
                    self.bucket_name,
                    f"{s3_path}.tar.gz"
                )
                self.stdout.write(f"   ✅ Uploaded: {s3_path}.tar.gz")
            else:
                # Upload directory recursively
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        local_path = os.path.join(root, file)
                        # Calculate relative path for S3
                        rel_path = os.path.relpath(local_path, source_path)
                        s3_key = f"{s3_path}/{rel_path}"
                        
                        self.s3_client.upload_file(
                            local_path,
                            self.bucket_name,
                            s3_key
                        )
                
                self.stdout.write(f"   ✅ Uploaded directory: {s3_path}")

        except ClientError as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ S3 upload error: {str(e)}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Upload error: {str(e)}")
            )

    def show_backup_summary(self, s3_path, backup_name):
        """Show summary of the backup"""
        self.stdout.write("\n📋 S3 Backup Summary:")
        self.stdout.write("=" * 50)
        self.stdout.write(f"📦 Backup Name: {backup_name}")
        self.stdout.write(f"☁️  S3 Location: s3://{self.bucket_name}/{s3_path}")
        self.stdout.write(f"⏰ Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Try to get file size from S3
        try:
            if self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{s3_path}.tar.gz"):
                response = self.s3_client.head_object(Bucket=self.bucket_name, Key=f"{s3_path}.tar.gz")
                size = response['ContentLength']
                self.stdout.write(f"📏 Size: {self.format_size(size)}")
        except:
            pass

        self.stdout.write("\n🔄 To restore this backup:")
        self.stdout.write(f"   python manage.py restore_data_s3 {backup_name}")
        self.stdout.write(f"   or download and run: s3://{self.bucket_name}/{s3_path}/restore_s3.sh")

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