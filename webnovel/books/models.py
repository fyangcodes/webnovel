"""
Book and Chapter Models with Self-Contained File Organization

This module implements a self-contained file organization system where all files
related to a book are stored within a book-specific directory structure.

File Organization Structure:
    books/
    ├── {bookmaster.id}/
    │   ├── {book.id}_{book.language.code}/
    │   │   ├── files/
    │   │   ├── covers/
    │   │   └── chapters/
    │   │       ├── {chapter.id}/
    │   │       │   ├── content/
    │   │       │   │   └── raw_v1.json
    │   │       │   │   └── raw_v2.json
    │   │       │   │   └── structured_v1.json
    │   │       │   │   └── structured_v2.json
    │   │       │   │   └── structured_v3.json
    │   │       │   ├── image/
    │   │       │   │   └── chapter_illustration.jpg
    │   │       │   ├── audio/
    │   │       │   │   └── chapter_narration.mp3
    │   │       │   ├── video/
    │   │       │   │   └── chapter_battle_scene.mp4
    │   │       │   └── document/
    │   │       │       └── chapter_notes.pdf



Benefits of Self-Contained Organization:
- Easy backup/restore of entire books
- Clear ownership and organization
- Simple cleanup (delete book = delete entire directory)
- Better portability for translations and exports
- Logical grouping by content rather than file type
"""

import hashlib
import json
import mimetypes
import re

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from django.templatetags.static import static
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from common.models import TimeStampedModel

from .fields import AutoIncrementingPositiveIntegerField
from .choices import (
    RatingChoices,
    BookStatus,
    MediaType,
    ParagraphStyle,
    ChangeType,
    ProcessingStatus,
    ChapterStatus,
)
from .constants import (
    IMAGE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FILE_EXTENSIONS,
)
from .utils import (
    book_cover_upload_to,
    chapter_media_upload_to,
    book_file_upload_to,
)
from .validators import unicode_slug_validator


class Language(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'zh-CN'
    name = models.CharField(max_length=50)  # e.g., 'Chinese (Simplified)'
    local_name = models.CharField(max_length=50)  # e.g., '中文（简体）'

    def __str__(self):
        return self.name


class Nationality(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'CN'
    name = models.CharField(max_length=50)  # e.g., 'China'
    local_name = models.CharField(max_length=50)  # e.g., '中国'

    def __str__(self):
        return self.name


class AbstractMaster(TimeStampedModel):
    """
    A abstract master is a master object that represents a book or chapter in regardless of the language.
    It is used to store the book or chapter's metadata and to create book or chapter objects in different languages.
    """

    canonical_name = models.CharField(max_length=255)
    related_name_for_languages = None  # set by the subclass

    class Meta:
        abstract = True
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
        ]

    def __str__(self):
        return self.canonical_name

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.canonical_name:
            raise ValidationError("Canonical name is required")

    def get_existing_languages(self):
        """Get all languages that have a related object"""
        if not self.related_name_for_languages:
            raise NotImplementedError(
                "Subclasses must define related_name_for_languages"
            )
        related_manager = getattr(self, self.related_name_for_languages)
        return related_manager.values_list("language__code", flat=True)


class AuthorMaster(AbstractMaster):
    """
    A author master is a master object that represents an author in regardless of the language.
    It is used to store the author's metadata and to create author objects in different languages.
    It is also used to store the author's nationality, birth date, death date, birth place, and death place.
    """
    nationality = models.ForeignKey(
        Nationality, on_delete=models.SET_NULL, null=True, blank=True
    )
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    birth_place = models.CharField(max_length=255, null=True, blank=True)
    death_place = models.CharField(max_length=255, null=True, blank=True)
    related_name_for_languages = "authors"

    class Meta:
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
            models.Index(fields=["nationality"]),
        ]


class BookMaster(AbstractMaster):
    """
    A book master is a master object that represents a book in regardless of the language.
    It is used to store the book's metadata and to create book objects in different languages.
    It is also used to store the book's original and pivot languages.
    It is also used to store the book's author and owner.
    """

    author = models.ManyToManyField(AuthorMaster, related_name="books")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="books",
        null=True,
        blank=True,
    )
    original_language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    pivot_language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_name_for_languages = "books"

    class Meta:
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
            models.Index(fields=["author"]),
            models.Index(fields=["owner"]),
        ]

    def save(self, *args, **kwargs):
        # set the original language to chinese if not set
        if not self.original_language:
            self.original_language = Language.objects.get(code="zh")
        # set the pivot language to english if not set
        if not self.pivot_language:
            self.pivot_language = Language.objects.get(code="en")
        super().save(*args, **kwargs)


class ChapterMaster(AbstractMaster):
    """
    A chapter master is a master object that represents a chapter in regardless of the language.
    It is used to store the chapter's metadata and to create chapter objects in different languages.
    It is also used to store the chapter's book and language.
    """

    book_master = models.ForeignKey(
        BookMaster, on_delete=models.CASCADE, related_name="chapter_masters"
    )
    related_name_for_languages = "chapters"

    class Meta:
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
            models.Index(fields=["book_master"]),
        ]


class Author(TimeStampedModel):
    master = models.ForeignKey(
        AuthorMaster, on_delete=models.CASCADE, related_name="authors"
    )
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    localized_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["master"]
        indexes = [
            models.Index(fields=["master"]),
            models.Index(fields=["language"]),
            models.Index(fields=["master", "language"]),
        ]

    def __str__(self):
        return f"{self.localized_name} ({self.master.canonical_name})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.localized_name:
            raise ValidationError("Localized name is required")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Book(TimeStampedModel):

    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255, unique=True, blank=True, validators=[unicode_slug_validator]
    )
    description = models.TextField(blank=True)
    master = models.ForeignKey(
        BookMaster, on_delete=models.CASCADE, related_name="books"
    )
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=BookStatus.choices,
        default=BookStatus.DRAFT,
        help_text="Book status (e.g., draft, ongoing, completed, archived)",
    )
    is_published = models.BooleanField(default=False)
    cover_image = models.ImageField(
        upload_to=book_cover_upload_to, blank=True, null=True
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
        return f"{self.title} ({self.master.canonical_name})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.title:
            raise ValidationError("Title is required")

    def save(self, *args, **kwargs):
        self.full_clean()

        if not self.slug:
            # generate a slug from the title
            self.slug = slugify(self.title, allow_unicode=True)
            # Ensure uniqueness
            base_slug = self.slug
            counter = 1
            while Book.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

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
    def _root_directory(self):
        """Get the base directory for all book files"""
        return f"books/{self.master.id}/{self.id}_{self.language.code}"

    @property
    def files_directory(self):
        """Get the directory for book files (PDFs, etc.)"""
        return f"{self._root_directory}/files"

    @property
    def covers_directory(self):
        """Get the directory for book thumbnails"""
        return f"{self._root_directory}/covers"

    @property
    def chapters_directory(self):
        """Get the directory for book chapters"""
        return f"{self._root_directory}/chapters"

    @property
    def has_custom_cover(self):
        """Check if the book has a custom cover image (not the default)"""
        return bool(self.cover_image)

    @property
    def cover_image_url(self, fallback_to_default=True):
        """Get the cover image URL with a fallback to the default image"""
        if self.has_custom_cover:
            return self.cover_image.url
        elif fallback_to_default:
            return static("images/default_book_cover.png")
        else:
            return None


class BookFile(TimeStampedModel):

    book = models.ForeignKey("Book", on_delete=models.CASCADE, related_name="files")
    file = models.FileField(
        upload_to=book_file_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["txt"])],
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
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.WAITING,
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


# --- MIXINS FOR CHAPTER ---


class ChapterContentMixin(models.Model):
    raw_content_file_path = models.CharField(
        max_length=255, blank=True, help_text="Path to raw content JSON file"
    )
    structured_content_file_path = models.CharField(
        max_length=255, blank=True, help_text="Path to structured content JSON file"
    )
    paragraph_style = models.CharField(
        max_length=20,
        choices=ParagraphStyle.choices,
        default=ParagraphStyle.AUTO_DETECT,
        help_text="How to parse paragraphs from raw content",
    )

    class Meta:
        abstract = True

    def _list_versions_s3_fallback_generic(self, base_dir, content_type):
        """Generic fallback method for listing versions that works with S3 storage"""
        version_files = {}

        try:
            # For S3, we need to check if files exist by trying to access them
            # Start with version 0 and check up to a reasonable limit
            for version in range(100):  # Limit to prevent infinite loops
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

    def list_content_versions(self, content_type):
        """Generic method to list versioned content files for both structured and raw content.

        Args:
            content_type: Either 'structured' or 'raw'
            base_dir: Base directory path

        Returns:
            dict: Dictionary with version numbers as keys and filenames as values.
                  Example: {0: 'structured_v0.json', 1: 'structured_v1.json'}
        """
        base_dir = self.content_directory

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
                        base_dir, content_type
                    )
            else:
                # Fallback for storage backends that don't support listdir
                version_files = self._list_versions_s3_fallback_generic(
                    base_dir, content_type
                )
        except Exception as e:
            print(f"Warning: Error listing files in {base_dir}: {e}")
            version_files = {}

        return version_files

    def get_content_file_path(self, content_type, version=None, next_version=False):
        """Return the canonical versioned file path for this chapter's structured content."""
        base_dir = self.content_directory

        # Get existing files as dictionary
        version_files = self.list_content_versions(content_type)
        if not version_files:
            # If no files exist, start at version 0
            latest_version = 0
        else:
            # Get the highest version number (keys are version numbers)
            latest_version = max(version_files.keys())

        # If version is provided, use it, otherwise use the latest version
        if version is not None:
            latest_version = version
        elif next_version:
            latest_version += 1

        return f"{base_dir}/{content_type}_v{latest_version}.json"

    def save_content_file(
        self, content_type, content_data, version=None, user=None, summary=""
    ):
        """Generic method to save content to JSON file.

        Args:
            content_data: The content data to save
            content_type: Either 'structured' or 'raw'
            user: User who made the change
            summary: Summary of the change
        """
        file_path = self.get_content_file_path(content_type, version, next_version=True)

        # Let Django's storage handle directory creation
        json_content = json.dumps(content_data, indent=2, ensure_ascii=False)
        content_file = ContentFile(json_content.encode("utf-8"))

        # Save to storage
        saved_path = default_storage.save(file_path, content_file)

        # Update the database record
        attr_name = f"{content_type}_content_file_path"
        setattr(self, attr_name, saved_path)
        self.save(update_fields=[attr_name])

    def get_content(self, content_type, text_only=False):
        """Generic method to load content from JSON file.

        Args:
            content_type: Either 'structured' or 'raw'

        Returns:
            The loaded content data
        """
        attr_name = f"{content_type}_content_file_path"
        file_path = getattr(self, attr_name)

        # Use the database path (authoritative source)
        if not file_path:
            return (
                [] if content_type == "structured" else ""
            )  # Return appropriate fallback

        if not default_storage.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with default_storage.open(file_path, "r") as f:
                data = json.load(f)
                if content_type == "structured":
                    if text_only:
                        return "\n\n".join([element["content"] for element in data])
                    else:
                        return data
                else:  # raw
                    return data.get("content", "")

        except (json.JSONDecodeError, IOError):
            raise ValueError(f"Invalid JSON file: {file_path}")

    def parse_content_raw_to_structured(self, style=ParagraphStyle.AUTO_DETECT):
        """Parse legacy content based on paragraph style setting"""
        # Get raw content
        raw_content = self.get_content("raw")

        # Split content into paragraphs based on style
        # if style is auto detect, detect by counting newlines
        if style == ParagraphStyle.AUTO_DETECT:
            single_count = raw_content.count("\n")
            double_count = raw_content.count("\n\n")
            if double_count > single_count / 4:
                style = ParagraphStyle.DOUBLE_NEWLINE
            else:
                style = ParagraphStyle.SINGLE_NEWLINE

        paragraphs = raw_content.split(
            "\n" if style == ParagraphStyle.SINGLE_NEWLINE else "\n\n"
        )

        structured_content = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                structured_content.append({"type": "text", "content": paragraph})

        return structured_content

    def parse_content_structured_to_raw(self):
        """Parse structured content to raw content"""
        structured_content = self.get_content("structured")

        raw_content = ""
        for element in structured_content:
            if element["type"] == "text":
                raw_content += element["content"] + "\n\n"

        return raw_content.strip()


class ChapterContentMediaMixin(ChapterContentMixin):
    class Meta:
        abstract = True

    def get_media_by_type(self, media_type):
        """Get all media of a specific type for this chapter"""
        return self.media.filter(media_type=media_type).order_by("position")

    def get_media_count_by_type(self, media_type):
        """Get count of media items by type"""
        return self.media.filter(media_type=media_type).count()

    def build_structured_content_with_media(self):
        """Build structured content to match current media order using relative positioning"""
        # Start with existing structured content or initialize by parsing raw content
        structured_content = self.get_content("structured", text_only=True)
        if not structured_content:
            structured_content = self.parse_content_raw_to_structured()

        # Add ALL media elements from database at their relative positions
        for media in self.media.all():
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
                for i, element in enumerate(structured_content):
                    if element["type"] == "text":
                        text_count += 1
                        if text_count == media.position:
                            # Insert before this text paragraph
                            insert_index = i
                            break

                structured_content.insert(insert_index, media_element)

        return structured_content


class ChapterScheduleMixin(models.Model):
    status = models.CharField(
        max_length=20,
        choices=ChapterStatus.choices,
        default=ChapterStatus.DRAFT,
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
    rating = models.CharField(
        max_length=5, choices=RatingChoices.choices, default=RatingChoices.EVERYONE
    )
    summary = models.TextField(blank=True, help_text="Summary for translation context")
    key_terms = models.JSONField(
        default=list, blank=True, help_text="Important terms for consistent translation"
    )

    class Meta:
        abstract = True


# Refactored Chapter model
class Chapter(
    TimeStampedModel, ChapterContentMediaMixin, ChapterScheduleMixin, ChapterAIMixin
):
    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255, blank=True, validators=[unicode_slug_validator]
    )
    master = models.ForeignKey(
        ChapterMaster, on_delete=models.CASCADE, related_name="chapters"
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        help_text="Language of this chapter (inherits from book if not specified)",
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
        return f"{self.title} ({self.master.canonical_name})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.title:
            raise ValidationError("Title is required")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        if not self.language:
            self.language = self.book.language
        super().save(*args, **kwargs)

    def generate_excerpt(self, max_length=200):
        """Generate an excerpt from the chapter raw content"""
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
        sentence_endings = [".", "!", "?", "。", "！", "？"]
        for ending in sentence_endings:
            pos = clean_content.rfind(ending, 0, max_length)
            if pos > max_length * 0.7:  # Only break if we're at least 70% through
                return clean_content[: pos + 1] + "..."

        # If no good sentence break, try paragraph break
        pos = clean_content.rfind("\n\n", 0, max_length)
        if pos > max_length * 0.7:
            return clean_content[:pos].strip() + "..."

        # If no good paragraph break, try single newline
        pos = clean_content.rfind("\n", 0, max_length)
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

    @property
    def _root_directory(self):
        """Get the base directory for all chapter files"""
        return f"{self.book.chapters_directory}/{self.id}"

    @property
    def content_directory(self):
        """Get the directory for chapter content files"""
        return f"{self._root_directory}/content"

    @property
    def media_directory(self):
        """Get the directory for chapter media files of a specific type"""
        return f"{self._root_directory}/media"


class ChapterMedia(TimeStampedModel):
    """Generalized model for storing various media types organized by book and chapter"""

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
        help_text="Type of media content",
    )
    file = models.FileField(
        upload_to=chapter_media_upload_to,
        validators=[
            FileExtensionValidator(
                allowed_extensions=IMAGE_EXTENSIONS
                + AUDIO_EXTENSIONS
                + VIDEO_EXTENSIONS
                + FILE_EXTENSIONS
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
    order = models.PositiveIntegerField(
        default=0, help_text="Order of the media in the chapter"
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
        ordering = ["position", "order"]
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
        elif ext in FILE_EXTENSIONS:
            return "file"
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
        max_length=20, choices=ChangeType.choices, default=ChangeType.EDIT
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


def get_default_book_cover_url():
    """Get the URL for the default book cover image"""
    return static("images/default_book_cover.png")
