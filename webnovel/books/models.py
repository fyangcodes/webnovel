"""
Book and Chapter Models with Self-Contained File Organization

This module implements a self-contained file organization system where all files
related to a book are stored within a book-specific directory structure.

File Organization Structure:
    books/
    └── {id}/
        ├── files/                    # Book files (PDFs, manuscripts, etc.)
        │   ├── original_manuscript.pdf
        │   └── translation_draft.docx
        ├── thumbnails/               # Book-level thumbnails
        │   └── cover_thumbnail.jpg
        └── chapters/
            ├── 1/
            │   ├── content/
            │   │   └── raw_v1.json   # Chapter content versions
            │   │   └── raw_v2.json
            │   │   └── structured_v1.json
            │   │   └── structured_v2.json
            │   │   └── structured_v3.json
            │   ├── image/            # Chapter images
            │   │   ├── sunset.jpg
            │   │   └── character_portrait.png
            │   ├── audio/            # Chapter audio files
            │   │   └── chapter_narration.mp3
            │   ├── video/            # Chapter video files
            │   │   └── battle_scene.mp4
            │   └── document/         # Chapter documents
            │       └── chapter_notes.pdf
            └── 2/
                ├── content/
                │   └── raw_v1.json
                │   └── structured_v1.json
                └── image/
                    └── chapter_illustration.jpg


Benefits of Self-Contained Organization:
- Easy backup/restore of entire books
- Clear ownership and organization
- Simple cleanup (delete book = delete entire directory)
- Better portability for translations and exports
- Logical grouping by content rather than file type
"""

import hashlib
import json
import os
import mimetypes
import re
import uuid
from datetime import datetime

from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from django.templatetags.static import static
from .fields import AutoIncrementingPositiveIntegerField
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Custom validator for Unicode slugs
unicode_slug_validator = RegexValidator(
    regex=r'^[^\s/\\?%*:|"<>]+$',
    message='Slug can contain any characters except whitespace and /\\?%*:|"<>',
    code="invalid_slug",
)

# Media type choices for ChapterMedia
MEDIA_TYPE_CHOICES = [
    ("image", "Image"),
    ("audio", "Audio"),
    ("video", "Video"),
    ("document", "Document"),
    ("other", "Other"),
]

# File extension validators for different media types
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"]
AUDIO_EXTENSIONS = ["mp3", "wav", "ogg", "m4a", "flac", "aac"]
VIDEO_EXTENSIONS = ["mp4", "avi", "mov", "wmv", "flv", "webm", "mkv"]
DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx", "txt", "rtf", "odt"]


def generate_unique_filename(base_path, filename):
    """
    Generate a unique filename to prevent overwrites on S3.
    
    Args:
        base_path: The base directory path
        filename: The original filename
        
    Returns:
        str: A unique filename with timestamp and/or counter
    """
    # Split filename into name and extension
    name, ext = os.path.splitext(filename)
    
    # Generate timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create the full path
    full_path = f"{base_path}/{name}_{timestamp}{ext}"
    
    # Check if file exists, if so, add a counter
    counter = 1
    while default_storage.exists(full_path):
        full_path = f"{base_path}/{name}_{timestamp}_{counter}{ext}"
        counter += 1
        # Prevent infinite loops
        if counter > 1000:
            # If we hit 1000, use UUID as fallback
            unique_id = str(uuid.uuid4())[:8]
            full_path = f"{base_path}/{name}_{timestamp}_{unique_id}{ext}"
            break
    
    return full_path


def book_file_upload_to(instance, filename):
    """Generate upload path for book files with duplicate handling"""
    base_path = instance.book.get_book_files_directory()
    return generate_unique_filename(base_path, filename)


def chapter_media_upload_to(instance, filename):
    """Generate organized upload path for chapter media with duplicate handling"""
    base_path = instance.chapter.get_chapter_media_directory(instance.media_type)
    return generate_unique_filename(base_path, filename)


def book_cover_upload_to(instance, filename):
    """Generate upload path for book cover images with duplicate handling"""
    base_path = f"{instance.get_book_directory()}/covers"
    return generate_unique_filename(base_path, filename)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Language(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'zh-CN'
    name = models.CharField(max_length=50)  # e.g., 'Chinese (Simplified)'
    local_name = models.CharField(max_length=50)  # e.g., '中文（简体）'

    def __str__(self):
        return self.name


class Author(TimeStampedModel):
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    canonical_name = models.CharField(max_length=255)
    localized_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self):
        return f"{self.localized_name}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.canonical_name:
            raise ValidationError("Canonical name is required")
        if not self.localized_name:
            raise ValidationError("Localized name is required")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Book(TimeStampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
        ("private", "Private"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
    ]

    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255, unique=True, blank=True, validators=[unicode_slug_validator]
    )
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="books",
        null=True,
        blank=True,
    )
    original_book = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="translations",
        help_text="Link to the original book if this is a translation.",
    )
    isbn = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to=book_cover_upload_to, blank=True, null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Book status (e.g., draft, published, etc.)",
    )

    # Metadata
    total_chapters = models.PositiveIntegerField(default=0)
    estimated_words = models.PositiveIntegerField(default=0)
    total_words = models.PositiveIntegerField(default=0)
    total_characters = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["language", "status"]),
            models.Index(fields=["author", "status"]),
        ]

    def __str__(self):
        return f"{self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.title:
            raise ValidationError("Title is required")
        if self.original_book and self.original_book == self:
            raise ValidationError("A book cannot be its own original book")

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
            # Ensure uniqueness
            base_slug = self.slug
            counter = 1
            while Book.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        # Set default language to first available language if none specified
        if not self.language:
            first_language = Language.objects.first()
            if first_language:
                self.language = first_language

        super().save(*args, **kwargs)

    def update_metadata(self):
        """Update book metadata based on its chapters"""
        chapters = self.chapters.all()
        self.total_chapters = chapters.count()
        self.total_words = sum(chapter.word_count for chapter in chapters)
        self.total_characters = sum(chapter.char_count for chapter in chapters)
        self.estimated_words = (
            self.total_words
        )  # Could be enhanced with better estimation
        self.save(
            update_fields=[
                "total_chapters",
                "total_words",
                "total_characters",
                "estimated_words",
            ]
        )

    @property
    def is_published(self):
        return self.status == "published"

    @property
    def is_completed(self):
        return self.status == "completed"

    @property
    def has_translations(self):
        return self.translations.exists()

    def get_translation(self, language):
        """
        Returns the translated book in the specified language.
        Accepts either a Language instance or a language code (str).
        """
        if isinstance(language, str):
            return self.translations.filter(language__code=language).first()
        return self.translations.filter(language=language).first()

    def get_book_directory(self):
        """Get the base directory for all book files"""
        return f"books/{self.id}"

    def get_book_files_directory(self):
        """Get the directory for book files (PDFs, etc.)"""
        return f"books/{self.id}/files"

    def get_book_thumbnails_directory(self):
        """Get the directory for book thumbnails"""
        return f"books/{self.id}/thumbnails"

    def get_cover_image_url(self, fallback_to_default=True):
        """Get the cover image URL with a fallback to the default image"""
        if self.cover_image:
            return self.cover_image.url
        elif fallback_to_default:
            return static("images/default_book_cover.png")
        else:
            return None

    @property
    def has_custom_cover(self):
        """Check if the book has a custom cover image (not the default)"""
        return bool(self.cover_image)

    def get_cover_image_data(self):
        """Get cover image data as a dictionary for API responses"""
        return {
            "url": self.get_cover_image_url(),
            "is_default": not self.has_custom_cover,
            "custom_image_url": self.cover_image.url if self.cover_image else None,
        }


# --- MIXINS FOR CHAPTER ---


class ChapterContentMixin(models.Model):
    structured_content_file_path = models.CharField(
        max_length=255, blank=True, help_text="Path to structured content JSON file"
    )
    raw_content_file_path = models.CharField(
        max_length=255, blank=True, help_text="Path to raw content JSON file"
    )
    paragraph_style = models.CharField(
        max_length=20,
        choices=[
            ("single_newline", "Single Newline"),
            ("double_newline", "Double Newline"),
            ("auto_detect", "Auto Detect"),
        ],
        default="auto_detect",
        help_text="How to parse paragraphs from content",
    )

    class Meta:
        abstract = True

    def get_content_base_directory(self):
        """Get the base directory for this chapter's content files."""
        book_id = self.book.id
        chapter_id = self.id
        return f"books/{book_id}/chapters/{chapter_id}/content"

    def _list_content_versions_generic(self, content_type, base_dir):
        """Generic method to list versioned content files for both structured and raw content.

        Args:
            content_type: Either 'structured' or 'raw'
            base_dir: Base directory path

        Returns:
            dict: Dictionary with version numbers as keys and filenames as values.
                  Example: {0: 'structured_v0.json', 1: 'structured_v1.json'}
        """
        pattern = re.compile(rf"{content_type}_v(\d+)\.json")

        try:
            # For S3 storage, we need to handle the flat structure differently
            # List all files with the base directory prefix
            if hasattr(default_storage, "listdir"):
                try:
                    directories, files = default_storage.listdir(base_dir)
                    # Filter and extract version numbers in one pass
                    version_files = {}
                    for f in files:
                        match = pattern.match(f)
                        if match:
                            version_num = int(match.group(1))
                            version_files[version_num] = f
                except Exception:
                    # Fallback for S3 or other storage backends
                    version_files = self._list_versions_s3_fallback_generic(
                        base_dir, pattern
                    )
            else:
                # Fallback for storage backends that don't support listdir
                version_files = self._list_versions_s3_fallback_generic(
                    base_dir, pattern
                )
        except Exception as e:
            print(f"Warning: Error listing files in {base_dir}: {e}")
            version_files = {}

        return version_files

    def _list_versions_s3_fallback_generic(self, base_dir, pattern):
        """Generic fallback method for listing versions that works with S3 storage"""
        version_files = {}

        try:
            # For S3, we need to check if files exist by trying to access them
            # Start with version 0 and check up to a reasonable limit
            for version in range(100):  # Limit to prevent infinite loops
                # Extract content type from pattern
                content_type = pattern.pattern.split("_")[0].split("(")[-1]
                filename = f"{content_type}_v{version}.json"
                file_path = f"{base_dir}/{filename}"

                if default_storage.exists(file_path):
                    version_files[version] = filename
                else:
                    # If we haven't found any files yet, continue checking
                    # If we've found some files and now hit a gap, we can stop
                    if version_files:
                        break
        except Exception as e:
            print(f"Warning: Error in S3 fallback listing for {base_dir}: {e}")

        return version_files

    def list_content_versions(self):
        """List all versioned JSON files for structured content.

        Returns:
            dict: Dictionary with version numbers as keys and filenames as values.
                  Example: {0: 'structured_v0.json', 1: 'structured_v1.json'}
        """
        base_dir = self.get_content_base_directory()
        return self._list_content_versions_generic("structured", base_dir)

    def list_raw_content_versions(self):
        """List all versioned JSON files for raw content.

        Returns:
            dict: Dictionary with version numbers as keys and filenames as values.
                  Example: {0: 'raw_v0.json', 1: 'raw_v1.json'}
        """
        base_dir = self.get_content_base_directory()
        return self._list_content_versions_generic("raw", base_dir)

    def get_content_file_path(self, next_version=False):
        """Return the canonical versioned file path for this chapter's structured content."""
        base_dir = self.get_content_base_directory()

        # Get existing files as dictionary
        version_files = self.list_content_versions()

        if not version_files:
            latest_version = 0
        else:
            # Get the highest version number (keys are version numbers)
            latest_version = max(version_files.keys())

        if next_version:
            latest_version += 1

        return f"{base_dir}/structured_v{latest_version}.json"

    def get_content_file_path_for_version(self, version):
        """Get the file path for a specific structured content version."""
        base_dir = self.get_content_base_directory()
        return f"{base_dir}/structured_v{version}.json"

    def get_raw_content_file_path(self, next_version=False):
        """Get path for raw content JSON file"""
        base_dir = self.get_content_base_directory()
        version_files = self.list_raw_content_versions()

        if not version_files:
            latest_version = 0
        else:
            latest_version = max(version_files.keys())

        if next_version:
            latest_version += 1

        return f"{base_dir}/raw_v{latest_version}.json"

    def get_raw_content_file_path_for_version(self, version):
        """Get the file path for a specific raw content version."""
        base_dir = self.get_content_base_directory()
        return f"{base_dir}/raw_v{version}.json"

    def _save_content_generic(self, content_data, content_type, user=None, summary=""):
        """Generic method to save content to JSON file.

        Args:
            content_data: The content data to save
            content_type: Either 'structured' or 'raw'
            user: User who made the change
            summary: Summary of the change
        """
        if content_type == "structured":
            file_path = self.get_content_file_path(next_version=True)
        else:  # raw
            file_path = self.get_raw_content_file_path(next_version=True)

        try:
            # Let Django's storage handle directory creation
            json_content = json.dumps(content_data, indent=2, ensure_ascii=False)
            content_file = ContentFile(json_content.encode("utf-8"))

            # Save to storage
            saved_path = default_storage.save(file_path, content_file)

            # Update the database record
            if content_type == "structured":
                self.structured_content_file_path = file_path
                self.save(update_fields=["structured_content_file_path"])
            else:  # raw
                self.raw_content_file_path = file_path
                self.save(update_fields=["raw_content_file_path"])

            # Log the change
            ChangeLog.objects.create(
                content_type=ContentType.objects.get_for_model(self),
                original_object_id=self.id,
                changed_object_id=self.id,
                user=user,
                change_type="edit",
                status="completed",
                notes=summary or f"{content_type.title()} content updated",
                diff="",  # Optionally add a diff
            )

        except Exception as e:
            print(f"Error saving {content_type} content to {file_path}: {e}")
            raise

    def save_structured_content(self, structured_content, user=None, summary=""):
        """Save structured content to a new versioned JSON file and log the change."""
        self._save_content_generic(structured_content, "structured", user, summary)

    def save_raw_content(self, content_text, user=None, summary=""):
        """Save raw content to JSON file with metadata"""
        content_data = {
            "content": content_text,
            "word_count": len(content_text.split()),
            "char_count": len(content_text),
            "language": (
                self.get_effective_language().code
                if self.get_effective_language()
                else None
            ),
            "saved_at": timezone.now().isoformat(),
            "user_id": user.id if user else None,
            "summary": summary,
            "version": len(self.list_raw_content_versions()) + 1,
        }

        self._save_content_generic(content_data, "raw", user, summary)

    def _get_content_generic(self, content_type):
        """Generic method to load content from JSON file.

        Args:
            content_type: Either 'structured' or 'raw'

        Returns:
            The loaded content data
        """
        if content_type == "structured":
            file_path = self.structured_content_file_path
        else:  # raw
            file_path = self.raw_content_file_path

        # Use the database path (authoritative source)
        if not file_path:
            return (
                [] if content_type == "structured" else ""
            )  # Return appropriate fallback

        if not default_storage.exists(file_path):
            return (
                [] if content_type == "structured" else ""
            )  # Return appropriate fallback

        try:
            with default_storage.open(file_path, "r") as f:
                data = json.load(f)
                if content_type == "structured":
                    return data
                else:  # raw
                    return data.get("content", "")
        except (json.JSONDecodeError, IOError):
            return (
                [] if content_type == "structured" else ""
            )  # Return appropriate fallback

    def get_structured_content(self):
        """Load structured content from JSON file"""
        return self._get_content_generic("structured")

    def get_raw_content(self):
        """Get raw content from JSON file or database fallback"""
        raw_content = self._get_content_generic("raw")
        if raw_content:
            return raw_content

        # No database content fallback since content field was removed
        return ""

    def get_raw_content_metadata(self):
        """Get raw content metadata (word count, language, etc.)"""
        if self.raw_content_file_path and default_storage.exists(
            self.raw_content_file_path
        ):
            try:
                with default_storage.open(self.raw_content_file_path, "r") as f:
                    data = json.load(f)
                    return {
                        "word_count": data.get("word_count", 0),
                        "char_count": data.get("char_count", 0),
                        "language": data.get("language"),
                        "saved_at": data.get("saved_at"),
                        "version": data.get("version"),
                    }
            except (json.JSONDecodeError, IOError):
                pass

        # Fallback to calculated values
        content = self.get_raw_content()
        return {
            "word_count": len(content.split()),
            "char_count": len(content),
            "language": (
                self.get_effective_language().code
                if self.get_effective_language()
                else None
            ),
            "saved_at": None,
            "version": None,
        }

    def _parse_legacy_content(self):
        """Parse legacy content based on paragraph style setting"""
        if self.paragraph_style == "single_newline":
            return self._parse_single_newline()
        elif self.paragraph_style == "double_newline":
            return self._parse_double_newline()
        else:
            return self._parse_auto_detect()

    def _parse_single_newline(self):
        """Parse by single newlines"""
        raw_content = self.get_raw_content()
        paragraphs = raw_content.split("\n")
        structured_content = []

        for paragraph in paragraphs:
            if paragraph.strip():
                structured_content.append(
                    {"type": "text", "content": paragraph.strip()}
                )

        return structured_content

    def _parse_double_newline(self):
        """Parse by double newlines"""
        raw_content = self.get_raw_content()
        paragraphs = raw_content.split("\n\n")
        structured_content = []

        for content in paragraphs:
            if content.strip():
                structured_content.append({"type": "text", "content": content.strip()})

        return structured_content

    def _parse_auto_detect(self):
        """Auto-detect paragraph style"""
        raw_content = self.get_raw_content()
        # Count single vs double newlines
        single_count = raw_content.count("\n")
        double_count = raw_content.count("\n\n")

        # If more double newlines, use double newline parsing
        if double_count > single_count / 4:  # Threshold for detection
            return self._parse_double_newline()
        else:
            return self._parse_single_newline()

    def get_paragraphs(self):
        """Get paragraphs with calculated numbers"""
        structured_content = self.get_structured_content()
        paragraphs = []

        for i, element in enumerate(structured_content):
            if element["type"] == "text":
                paragraphs.append(
                    {
                        "paragraph_number": i + 1,  # Calculate from array index
                        "content": element["content"],
                        "array_index": i,
                    }
                )

        return paragraphs

    def get_paragraph_by_number(self, paragraph_number):
        """Get specific paragraph by number"""
        paragraphs = self.get_paragraphs()
        for paragraph in paragraphs:
            if paragraph["paragraph_number"] == paragraph_number:
                return paragraph
        return None

    def add_paragraph(self, content, position=None):
        """Add a new paragraph to the chapter"""
        structured_content = self.get_structured_content()

        new_paragraph = {"type": "text", "content": content}

        if position is None:
            structured_content.append(new_paragraph)
        else:
            structured_content.insert(position, new_paragraph)

        self.save_structured_content(
            structured_content, summary="Added paragraph to structured content"
        )

    def update_paragraph(self, index, content):
        """Update paragraph content at specific index"""
        structured_content = self.get_structured_content()

        if (
            0 <= index < len(structured_content)
            and structured_content[index]["type"] == "text"
        ):
            structured_content[index]["content"] = content
            self.save_structured_content(
                structured_content, summary="Updated paragraph in structured content"
            )
            return True
        return False

    def delete_paragraph(self, index):
        """Delete paragraph at specific index"""
        structured_content = self.get_structured_content()
        if 0 <= index < len(structured_content):
            del structured_content[index]
            self.save_structured_content(
                structured_content, summary="Deleted paragraph from structured content"
            )
            return True


class ChapterContentMediaMixin(ChapterContentMixin):
    class Meta:
        abstract = True

    def add_media_to_content(self, media_id, media_type, caption="", position=None):
        """Add media to structured content at position relative to text paragraphs"""
        structured_content = self.get_structured_content()

        # Create media element based on type with file path
        if media_type == "image":
            # For backward compatibility, use image_id for images
            new_media = {"type": "image", "image_id": media_id, "caption": caption}
        else:
            # For new media types, use media_id
            new_media = {"type": media_type, "media_id": media_id, "caption": caption}

        # Add file path if available
        try:
            if media_type == "image":
                media_obj = ChapterMedia.objects.get(id=media_id, media_type="image")
            else:
                media_obj = ChapterMedia.objects.get(id=media_id, media_type=media_type)
            new_media["file_path"] = media_obj.file.url if media_obj.file else None
        except ChapterMedia.DoesNotExist:
            new_media["file_path"] = None

        if position is None:
            # If no position specified, append to end
            structured_content.append(new_media)
        else:
            # Find the absolute position relative to text paragraphs
            text_count = 0
            insert_index = len(structured_content)  # Default to end

            for i, element in enumerate(structured_content):
                if element["type"] == "text":
                    text_count += 1
                    if text_count == position:
                        # Insert before this text paragraph
                        insert_index = i
                        break
                elif text_count == position:
                    # We've reached the target text position, insert here
                    insert_index = i
                    break

            structured_content.insert(insert_index, new_media)

        self.save_structured_content(
            structured_content,
            summary=f"Added {media_type} media to structured content",
        )

    def get_media_by_type(self, media_type):
        """Get all media of a specific type for this chapter"""
        return self.media.filter(media_type=media_type).order_by("position")

    def get_images(self):
        """Get all images for this chapter (backward compatibility)"""
        return self.get_media_by_type("image")

    def get_audio(self):
        """Get all audio files for this chapter"""
        return self.get_media_by_type("audio")

    def get_videos(self):
        """Get all video files for this chapter"""
        return self.get_media_by_type("video")

    def get_documents(self):
        """Get all documents for this chapter"""
        return self.get_media_by_type("document")

    def add_media(self, file, media_type=None, title="", caption="", position=None):
        """Add a new media item to this chapter"""
        if position is None:
            # Get the next position
            last_media = self.media.order_by("-position").first()
            position = (last_media.position + 1) if last_media else 1

        media = ChapterMedia.objects.create(
            chapter=self,
            file=file,
            media_type=media_type,
            title=title,
            caption=caption,
            position=position,
        )

        # Automatically add to structured content
        self.add_media_to_content(media.id, media.media_type, media.caption)

        return media

    def add_image(self, image_file, caption="", alt_text="", position=None):
        """Add an image to this chapter (backward compatibility)"""
        media = self.add_media(
            file=image_file, media_type="image", caption=caption, position=position
        )
        media.alt_text = alt_text
        media.save()
        return media

    def add_audio(self, audio_file, title="", caption="", duration=None, position=None):
        """Add an audio file to this chapter"""
        media = self.add_media(
            file=audio_file,
            media_type="audio",
            title=title,
            caption=caption,
            position=position,
        )
        if duration:
            media.duration = duration
            media.save()
        return media

    def add_video(
        self,
        video_file,
        title="",
        caption="",
        duration=None,
        thumbnail=None,
        position=None,
    ):
        """Add a video file to this chapter"""
        media = self.add_media(
            file=video_file,
            media_type="video",
            title=title,
            caption=caption,
            position=position,
        )
        if duration:
            media.duration = duration
        if thumbnail:
            media.thumbnail = thumbnail
        media.save()
        return media

    def add_document(self, document_file, title="", caption="", position=None):
        """Add a document to this chapter"""
        return self.add_media(
            file=document_file,
            media_type="document",
            title=title,
            caption=caption,
            position=position,
        )

    def reorder_media(self, media_ids):
        """Reorder media items by providing a list of media IDs in desired order"""
        for position, media_id in enumerate(media_ids, 1):
            try:
                media = self.media.get(id=media_id)
                media.position = position
                media.save(update_fields=["position"])
            except ChapterMedia.DoesNotExist:
                continue

    def get_media_count_by_type(self):
        """Get count of media items by type"""
        from django.db.models import Count

        return self.media.values("media_type").annotate(count=Count("id"))

    def delete_element(self, index):
        """Delete element at specific index"""
        structured_content = self.get_structured_content()

        if 0 <= index < len(structured_content):
            del structured_content[index]
            self.save_structured_content(
                structured_content, summary="Deleted element from structured content"
            )
            return True
        return False

    def reorder_elements(self, new_order):
        """Reorder elements based on new index order"""
        structured_content = self.get_structured_content()

        if len(new_order) == len(structured_content):
            reordered_content = [structured_content[i] for i in new_order]
            self.save_structured_content(
                reordered_content, summary="Reordered elements in structured content"
            )
            return True
        return False

    def get_element_by_index(self, index):
        """Get element by array index"""
        structured_content = self.get_structured_content()
        if 0 <= index < len(structured_content):
            element = structured_content[index]
            if element["type"] == "paragraph":
                return {**element, "paragraph_number": index + 1, "array_index": index}
            else:
                return {**element, "array_index": index}
        return None

    @property
    def total_media_count(self):
        """Get total number of media items"""
        return self.media.count()

    def sync_media_with_content(self):
        """Sync all media items with structured content, adding any that are missing"""
        structured_content = self.get_structured_content()
        existing_media_ids = set()

        # Collect existing media IDs from structured content
        for element in structured_content:
            if element["type"] == "image" and "image_id" in element:
                existing_media_ids.add(("image", element["image_id"]))
            elif (
                element["type"] in ["audio", "video", "document"]
                and "media_id" in element
            ):
                existing_media_ids.add((element["type"], element["media_id"]))

        # Find media items that are not in structured content
        all_media = self.media.all()
        media_to_add = []

        for media in all_media:
            media_key = (media.media_type, media.id)
            if media_key not in existing_media_ids:
                # Create media element based on type with file path
                if media.media_type == "image":
                    # For backward compatibility, use image_id for images
                    media_element = {
                        "type": "image",
                        "image_id": media.id,
                        "caption": media.caption,
                        "file_path": media.file.url if media.file else None,
                    }
                else:
                    # For new media types, use media_id
                    media_element = {
                        "type": media.media_type,
                        "media_id": media.id,
                        "caption": media.caption,
                        "file_path": media.file.url if media.file else None,
                    }

                media_to_add.append((media_element, media.position))

        # Add all missing media items at once
        if media_to_add:
            # Sort by position to ensure proper insertion order
            media_to_add.sort(key=lambda x: x[1] if x[1] is not None else float("inf"))

            # Insert media items at their relative positions
            for media_element, position in media_to_add:
                if position is None:
                    # If no position specified, append to end
                    structured_content.append(media_element)
                else:
                    # Find the absolute position relative to text paragraphs
                    text_count = 0
                    insert_index = len(structured_content)  # Default to end

                    for i, element in enumerate(structured_content):
                        if element["type"] == "text":
                            text_count += 1
                            if text_count == position:
                                # Insert before this text paragraph
                                insert_index = i
                                break
                        elif text_count == position:
                            # We've reached the target text position, insert here
                            insert_index = i
                            break

                    structured_content.insert(insert_index, media_element)

            # Save the updated structured content once with versioning
            self.save_structured_content(
                structured_content, summary="Synced media with structured content"
            )

        return len(media_to_add)

    def rebuild_structured_content_from_media(self):
        """Rebuild structured content to match current media order using relative positioning"""
        # Get all media ordered by position
        all_media = self.media.order_by("position")

        # Start with existing text content ONLY (remove any existing media)
        structured_content = []
        existing_content = self.get_structured_content()

        # Add ONLY text elements (filter out any existing media)
        for element in existing_content:
            if element["type"] == "text":
                structured_content.append(element)

        # Add ALL media elements from database at their relative positions
        for media in all_media:
            if media.media_type == "image":
                media_element = {
                    "type": "image",
                    "image_id": media.id,
                    "caption": media.caption,
                    "file_path": media.file.url if media.file else None,
                }
            else:
                media_element = {
                    "type": media.media_type,
                    "media_id": media.id,
                    "caption": media.caption,
                    "file_path": media.file.url if media.file else None,
                }

            # Insert at relative position (before text paragraph N)
            if media.position is None:
                structured_content.append(media_element)
            else:
                # Find the absolute position relative to text paragraphs
                text_count = 0
                insert_index = len(structured_content)  # Default to end

                for i, element in enumerate(structured_content):
                    if element["type"] == "text":
                        text_count += 1
                        if text_count == media.position:
                            # Insert before this text paragraph
                            insert_index = i
                            break
                    elif text_count == media.position:
                        # We've reached the target text position, insert here
                        insert_index = i
                        break

                structured_content.insert(insert_index, media_element)

        # Save the rebuilt content with versioning
        self.save_structured_content(
            structured_content, summary="Rebuilt structured content from media"
        )
        return len(structured_content)

    def get_paragraphs_and_media(self):
        """Get paragraphs and media in order as they appear in structured content"""
        structured_content = self.get_structured_content()
        result = []

        for element in structured_content:
            if element["type"] == "text":
                result.append(
                    {
                        "type": "text",
                        "content": element["content"],
                        "paragraph_number": element.get("paragraph_number", 0),
                    }
                )
            elif element["type"] == "image":
                # Use file path from JSON if available, otherwise fallback to database lookup
                if element.get("file_path"):
                    result.append(
                        {
                            "type": "image",
                            "media": None,
                            "image": None,
                            "caption": element.get("caption", ""),
                            "position": element.get("position"),
                            "file_path": element["file_path"],
                        }
                    )
                else:
                    try:
                        # Try to find in ChapterMedia
                        media = ChapterMedia.objects.filter(
                            chapter=self, media_type="image", id=element["image_id"]
                        ).first()

                        if not media:
                            # Skip if media doesn't exist
                            continue
                        else:
                            result.append(
                                {
                                    "type": "image",
                                    "media": media,
                                    "image": None,
                                    "caption": element.get("caption", media.caption),
                                    "position": element.get("position", media.position),
                                    "file_path": media.file.url if media.file else None,
                                }
                            )
                    except Exception:
                        # Skip if media doesn't exist
                        continue
            elif element["type"] in ["audio", "video", "document"]:
                # Use file path from JSON if available, otherwise fallback to database lookup
                if element.get("file_path"):
                    result.append(
                        {
                            "type": element["type"],
                            "media": None,
                            "caption": element.get("caption", ""),
                            "position": element.get("position"),
                            "file_path": element["file_path"],
                        }
                    )
                else:
                    try:
                        media = ChapterMedia.objects.get(
                            chapter=self,
                            media_type=element["type"],
                            id=element["media_id"],
                        )
                        result.append(
                            {
                                "type": element["type"],
                                "media": media,
                                "caption": element.get("caption", media.caption),
                                "position": element.get("position", media.position),
                                "file_path": media.file.url if media.file else None,
                            }
                        )
                    except ChapterMedia.DoesNotExist:
                        # Skip if media doesn't exist
                        continue

        return result


class ChapterScheduleMixin(models.Model):
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("translating", "Translating"),
            ("scheduled", "Scheduled"),
            ("published", "Published"),
            ("archived", "Archived"),
            ("private", "Private"),
            ("error", "Error"),
        ],
        default="draft",
        help_text="Chapter status",
    )
    active_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this chapter should become active/published",
    )

    class Meta:
        abstract = True

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        # Validate scheduled publishing
        if getattr(self, "status", None) == "scheduled" and not getattr(
            self, "active_at", None
        ):
            raise ValidationError("Scheduled chapters must have an active_at date")
        if (
            getattr(self, "status", None) == "published"
            and getattr(self, "active_at", None)
            and getattr(self, "active_at") > timezone.now()
        ):
            raise ValidationError(
                "Published chapters cannot have future active_at dates"
            )
        super().clean()

    @property
    def is_active(self):
        """Returns True if the chapter is currently active (published and past active_at)"""
        if self.status != "published":
            return False
        if self.active_at:
            return self.active_at <= timezone.now()
        return True

    @property
    def is_published(self):
        return self.status == "published"

    @property
    def is_scheduled(self):
        return self.status == "scheduled"

    @property
    def is_draft(self):
        return self.status == "draft"

    @property
    def scheduled_for(self):
        """Returns the scheduled date if this chapter is scheduled for publishing"""
        if self.status == "scheduled" and self.active_at:
            return self.active_at
        return None

    @property
    def time_until_publish(self):
        """Returns time remaining until publication (for scheduled chapters)"""
        if self.status == "scheduled" and self.active_at:
            remaining = self.active_at - timezone.now()
            return remaining if remaining.total_seconds() > 0 else None
        return None

    def schedule_for_publishing(self, publish_datetime):
        """Schedule this chapter for publishing at a specific datetime"""
        if publish_datetime <= timezone.now():
            raise ValueError("Publish datetime must be in the future")

        # Ensure slug is valid before scheduling
        if not self.slug or self.slug.strip() == "":
            if self.title and self.title.strip():
                self.slug = slugify(self.title, allow_unicode=True)
            else:
                self.slug = f"chapter-{self.chapter_number}"

            # Ensure uniqueness per book
            base_slug = self.slug
            counter = 1
            while (
                Chapter.objects.filter(book=self.book, slug=self.slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        self.active_at = publish_datetime
        self.status = "scheduled"
        self.save()

    def publish_now(self):
        """Publish this chapter immediately"""
        # Ensure slug is valid before publishing
        if not self.slug or self.slug.strip() == "":
            if self.title and self.title.strip():
                self.slug = slugify(self.title, allow_unicode=True)
            else:
                self.slug = f"chapter-{self.chapter_number}"

            # Ensure uniqueness per book
            base_slug = self.slug
            counter = 1
            while (
                Chapter.objects.filter(book=self.book, slug=self.slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        self.status = "published"
        self.active_at = timezone.now()
        self.save()

    def unpublish(self):
        """Unpublish this chapter"""
        self.status = "draft"
        self.active_at = None
        self.save()

    @classmethod
    def get_published_chapters(cls, book=None):
        """Get all published chapters, optionally filtered by book"""
        queryset = cls.objects.filter(status="published")
        if book:
            queryset = queryset.filter(book=book)
        return queryset.filter(
            models.Q(active_at__isnull=True) | models.Q(active_at__lte=timezone.now())
        )

    @classmethod
    def get_scheduled_chapters(cls, book=None):
        """Get all scheduled chapters, optionally filtered by book"""
        queryset = cls.objects.filter(status="scheduled")
        if book:
            queryset = queryset.filter(book=book)
        return queryset.filter(active_at__gt=timezone.now())


class ChapterAIMixin(models.Model):
    abstract = models.TextField(
        blank=True, help_text="AI-generated summary for translation context"
    )
    key_terms = models.JSONField(
        default=list, blank=True, help_text="Important terms for consistent translation"
    )

    class Meta:
        abstract = True


# Refactored Chapter model
class Chapter(
    TimeStampedModel, ChapterContentMediaMixin, ChapterScheduleMixin, ChapterAIMixin
):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255, blank=True, validators=[unicode_slug_validator]
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Language of this chapter (inherits from book if not specified)",
    )
    original_chapter = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="translations",
        help_text="Original chapter if this is a translation",
    )
    chapter_number = AutoIncrementingPositiveIntegerField(scope_field="book")
    excerpt = models.TextField(max_length=1000, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["chapter_number"]
        unique_together = ["book", "chapter_number"]
        indexes = [
            models.Index(fields=["book", "chapter_number"]),
            models.Index(fields=["book", "status"]),
            models.Index(fields=["language", "status"]),
            models.Index(fields=["active_at", "status"]),
        ]

    def __str__(self):
        return f"{self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if not self.title:
            raise ValidationError("Title is required")
        if self.original_chapter and self.original_chapter == self:
            raise ValidationError("A chapter cannot be its own original chapter")
        # Ensure slug is not empty (let Django's SlugField handle format validation)
        if self.slug and self.slug.strip() == "":
            raise ValidationError("Slug cannot be empty")

    def has_translations(self):
        """Check if this chapter has translations"""
        return self.translations.exists()

    def get_translation(self, language):
        """
        Returns the translated chapter in the specified language.
        Accepts either a Language instance or a language code (str).
        """
        if isinstance(language, str):
            return self.translations.filter(language__code=language).first()
        return self.translations.filter(language=language).first()

    def get_effective_language(self):
        """Get the effective language of this chapter (inherits from book if not specified)"""
        return self.language or self.book.language

    def get_chapter_media_directory(self, media_type):
        """Get the directory for chapter media files of a specific type"""
        book_id = self.book.id
        chapter_id = self.id
        return f"books/{book_id}/chapters/{chapter_id}/{media_type}"

    def generate_excerpt(self, max_length=200):
        """Generate an excerpt from the chapter content"""
        raw_content = self.get_raw_content()
        if not raw_content:
            return ""
        
        # Clean up the content for excerpt generation
        clean_content = raw_content.strip()
        
        # If content is shorter than max_length, return as is
        if len(clean_content) <= max_length:
            return clean_content
        
        # Find a good breaking point (sentence end, paragraph break, etc.)
        # Try to break at sentence endings first
        sentence_endings = ['.', '!', '?', '。', '！', '？']
        for ending in sentence_endings:
            pos = clean_content.rfind(ending, 0, max_length)
            if pos > max_length * 0.7:  # Only break if we're at least 70% through
                return clean_content[:pos + 1] + "..."
        
        # If no good sentence break, try paragraph break
        pos = clean_content.rfind('\n\n', 0, max_length)
        if pos > max_length * 0.7:
            return clean_content[:pos].strip() + "..."
        
        # If no good paragraph break, try single newline
        pos = clean_content.rfind('\n', 0, max_length)
        if pos > max_length * 0.7:
            return clean_content[:pos].strip() + "..."
        
        # Last resort: just truncate and add ellipsis
        return clean_content[:max_length] + "..."

    def update_content_statistics(self):
        """Update word and character counts from raw content"""
        raw_content = self.get_raw_content()
        if raw_content:
            self.word_count = len(raw_content.split())
            self.char_count = len(raw_content)
        else:
            self.word_count = 0
            self.char_count = 0


class ChapterMedia(TimeStampedModel):
    """Generalized model for storing various media types organized by book and chapter"""

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default="image",
        help_text="Type of media content",
    )
    file = models.FileField(
        upload_to=chapter_media_upload_to,
        validators=[
            FileExtensionValidator(
                allowed_extensions=IMAGE_EXTENSIONS
                + AUDIO_EXTENSIONS
                + VIDEO_EXTENSIONS
                + DOCUMENT_EXTENSIONS
            )
        ],
    )
    title = models.CharField(
        max_length=255, blank=True, help_text="Title or name of the media"
    )
    caption = models.TextField(blank=True, help_text="Description or caption")
    alt_text = models.CharField(
        max_length=255, blank=True, help_text="Accessibility text"
    )
    position = models.PositiveIntegerField(
        help_text="Position relative to text paragraphs (e.g., 1 = before first paragraph)"
    )

    # Media-specific metadata
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Duration in seconds (for audio/video)"
    )
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    mime_type = models.CharField(
        max_length=100, blank=True, help_text="MIME type of the file"
    )

    # Processing status
    is_processed = models.BooleanField(
        default=False, help_text="Whether media has been processed"
    )
    processing_error = models.TextField(
        blank=True, help_text="Error message if processing failed"
    )

    class Meta:
        ordering = ["position"]
        indexes = [
            models.Index(fields=["chapter", "media_type"]),
            models.Index(fields=["media_type", "is_processed"]),
        ]

    def __str__(self):
        return f"{self.get_media_type_display()} {self.id} in Chapter {self.chapter.id}"

    def save(self, *args, **kwargs):
        # Auto-detect media type from file extension if not set
        if self.file and not self.media_type:
            self.media_type = self._detect_media_type()

        # Set file size and MIME type
        if self.file:
            self.file_size = self.file.size
            self.mime_type = self._get_mime_type()

        super().save(*args, **kwargs)

    def _detect_media_type(self):
        """Detect media type from file extension"""
        if not self.file:
            return "other"

        ext = self.file.name.split(".")[-1].lower()

        if ext in IMAGE_EXTENSIONS:
            return "image"
        elif ext in AUDIO_EXTENSIONS:
            return "audio"
        elif ext in VIDEO_EXTENSIONS:
            return "video"
        elif ext in DOCUMENT_EXTENSIONS:
            return "document"
        else:
            return "other"

    def _get_mime_type(self):
        """Get MIME type from file extension"""
        if not self.file:
            return ""

        ext = self.file.name.split(".")[-1].lower()
        mime_type, _ = mimetypes.guess_type(f"file.{ext}")
        return mime_type or "application/octet-stream"

    @property
    def is_image(self):
        return self.media_type == "image"

    @property
    def is_audio(self):
        return self.media_type == "audio"

    @property
    def is_video(self):
        return self.media_type == "video"

    @property
    def is_document(self):
        return self.media_type == "document"

    @property
    def display_title(self):
        """Get display title (title or filename)"""
        return self.title or self.file.name.split("/")[-1]

    @property
    def formatted_duration(self):
        """Format duration as MM:SS"""
        if not self.duration:
            return None

        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def formatted_file_size(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "0 B"

        for unit in ["B", "KB", "MB", "GB"]:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"


class ChangeLog(TimeStampedModel):
    """
    General-purpose model to track changes (translations, edits, corrections, etc.)
    between any two objects (Book or Chapter).
    """

    CHANGE_TYPE_CHOICES = [
        ("translation", "Translation"),
        ("edit", "Edit/Correction"),
        ("other", "Other"),
    ]
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    original_object_id = models.PositiveIntegerField()
    original_object = GenericForeignKey("content_type", "original_object_id")
    changed_object_id = models.PositiveIntegerField()
    changed_object = GenericForeignKey("content_type", "changed_object_id")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who made the change (translator, editor, etc.)",
    )
    change_type = models.CharField(
        max_length=20, choices=CHANGE_TYPE_CHOICES, default="edit"
    )
    status = models.CharField(max_length=50, default="completed")
    notes = models.TextField(blank=True)
    version = AutoIncrementingPositiveIntegerField(scope_field="changed_object_id")
    diff = models.TextField(
        blank=True, help_text="Optional: store a diff of the change"
    )

    def __str__(self):
        return f"{self.get_change_type_display()} by {self.user} on {self.created_at}"

    @property
    def change_summary(self):
        """Returns a brief summary of the change"""
        return f"{self.get_change_type_display()}: {self.original_object} → {self.changed_object}"

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "original_object_id"]),
            models.Index(fields=["content_type", "changed_object_id"]),
            models.Index(fields=["user", "change_type"]),
            models.Index(fields=["created_at"]),
        ]


class BookFile(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("chunking", "Chunking"),
        ("translating", "Translating"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    book = models.ForeignKey("Book", on_delete=models.CASCADE, related_name="files")
    file = models.FileField(
        upload_to=book_file_upload_to,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "txt", "docx", "epub"])
        ],
    )
    description = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_bookfiles",
        help_text="User who uploaded this file.",
    )
    file_size = models.PositiveIntegerField(default=0)  # in bytes
    file_hash = models.CharField(max_length=64, blank=True)
    file_type = models.CharField(max_length=20, blank=True)

    # Status and processing
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Processing status of the file",
    )
    processing_progress = models.PositiveIntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["book", "status"]),
            models.Index(fields=["status", "processing_progress"]),
        ]

    def save(self, *args, **kwargs):
        if self.file and not self.file_hash:
            self.file_hash = self.calculate_file_hash()
            self.file_size = self.file.size
            self.file_type = self.file.name.split(".")[-1]
        super().save(*args, **kwargs)

    def calculate_file_hash(self):
        """Calculate SHA256 hash of uploaded file"""
        hash_sha256 = hashlib.sha256()
        for chunk in self.file.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def __str__(self):
        return f"{self.file.name} for {self.book.title}"

    @property
    def processing_duration(self):
        """Calculate processing duration"""
        if self.processing_started_at and self.processing_completed_at:
            return self.processing_completed_at - self.processing_started_at
        elif self.processing_started_at:
            return timezone.now() - self.processing_started_at
        return None

    @property
    def is_processing(self):
        return self.status in ["processing", "chunking", "translating"]

    @property
    def is_completed(self):
        return self.status == "completed"

    @property
    def is_failed(self):
        return self.status == "failed"

    def get_processing_status_display(self):
        """Get a user-friendly status display"""
        status_map = {
            "pending": "Waiting to be processed",
            "processing": "Processing file",
            "chunking": "Dividing into chapters",
            "translating": "Translating content",
            "completed": "Processing completed",
            "failed": "Processing failed",
        }
        return status_map.get(self.status, self.status)

    def get_progress_percentage(self):
        """Get progress as a percentage"""
        if self.status == "completed":
            return 100
        elif self.status == "failed":
            return 0
        else:
            return self.processing_progress


def get_default_book_cover_url():
    """Get the URL for the default book cover image"""
    return static("images/default_book_cover.png")
