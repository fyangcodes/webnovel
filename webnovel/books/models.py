import hashlib
import json
import os

from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from .fields import AutoIncrementingPositiveIntegerField
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Custom validator for Unicode slugs
unicode_slug_validator = RegexValidator(
    regex=r'^[^\s/\\?%*:|"<>]+$',
    message='Slug can contain any characters except whitespace and /\\?%*:|"<>',
    code="invalid_slug",
)


def book_file_upload_to(instance, filename):
    # instance is a BookFile object
    # instance.book is the related Book object
    return f"book_files/{instance.book.id}/{filename}"


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
    cover_image = models.ImageField(upload_to="book_covers/", blank=True, null=True)
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


class Chapter(TimeStampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("translating", "Translating"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
        ("archived", "Archived"),
        ("private", "Private"),
        ("error", "Error"),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255, blank=True, validators=[unicode_slug_validator]
    )
    content = models.TextField()
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
    abstract = models.TextField(
        blank=True, help_text="AI-generated summary for translation context"
    )
    key_terms = models.JSONField(
        default=list, blank=True, help_text="Important terms for consistent translation"
    )
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
    active_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this chapter should become active/published",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Chapter status",
    )

    # New fields for file-based storage and flexible parsing
    content_file_path = models.CharField(
        max_length=255, blank=True, help_text="Path to JSON content file"
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

        if not self.title:
            raise ValidationError("Title is required")
        if not self.content:
            raise ValidationError("Content is required")
        if self.original_chapter and self.original_chapter == self:
            raise ValidationError("A chapter cannot be its own original chapter")

        # Validate scheduled publishing
        if self.status == "scheduled" and not self.active_at:
            raise ValidationError("Scheduled chapters must have an active_at date")
        if (
            self.status == "published"
            and self.active_at
            and self.active_at > timezone.now()
        ):
            raise ValidationError(
                "Published chapters cannot have future active_at dates"
            )

        # Ensure slug is not empty (let Django's SlugField handle format validation)
        if self.slug and self.slug.strip() == "":
            raise ValidationError("Slug cannot be empty")

    def save(self, *args, **kwargs):
        self.full_clean()

        # Auto-update status based on active_at
        if (
            self.active_at
            and self.active_at <= timezone.now()
            and self.status == "scheduled"
        ):
            self.status = "published"

        # Always ensure we have a valid slug
        if not self.slug or self.slug.strip() == "":
            # Generate slug from title, fallback to chapter number if title is empty
            if self.title and self.title.strip():
                self.slug = slugify(self.title, allow_unicode=True)
            else:
                # Fallback to chapter number if title is empty
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

        # Set language from book if not specified
        if not self.language and self.book.language:
            self.language = self.book.language

        if self.content:
            self.word_count = len(self.content.split())
            self.char_count = len(self.content)
            self.excerpt = self.content[:1000]

        # Save the chapter first
        super().save(*args, **kwargs)

        # Update book metadata after saving
        self.book.update_metadata()

    # File-based storage methods
    def get_content_file_path(self):
        """Generate organized file path for chapter content"""
        if self.content_file_path:
            return self.content_file_path

        book_id = self.book.id
        chapter_id = self.id

        # Create organized path: content/chapters/book_{id}/chapter_{id}.json
        path = f"content/chapters/book_{book_id}/chapter_{chapter_id}.json"
        return path

    def get_book_content_directory(self):
        """Get the content directory for this book"""
        return f"content/chapters/book_{self.book.id}"

    def get_book_images_directory(self):
        """Get the images directory for this book"""
        return f"images/book_{self.book.id}"

    def get_chapter_images_directory(self):
        """Get the images directory for this chapter"""
        return f"images/book_{self.book.id}/chapter_{self.id}"

    def get_structured_content(self):
        """Load structured content from JSON file"""
        file_path = self.get_content_file_path()

        try:
            if default_storage.exists(file_path):
                with default_storage.open(file_path, "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

        # Fallback to legacy content
        return self._parse_legacy_content()

    def save_structured_content(self, structured_content):
        """Save clean structured content to JSON file"""
        file_path = self.get_content_file_path()

        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # Save JSON file
        json_content = json.dumps(structured_content, indent=2, ensure_ascii=False)
        default_storage.save(file_path, ContentFile(json_content.encode("utf-8")))

        # Update model
        self.content_file_path = file_path
        self.save(update_fields=["content_file_path"])

    # Flexible paragraph parsing methods
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
        paragraphs = self.content.split("\n")
        structured_content = []

        for paragraph in paragraphs:
            if paragraph.strip():
                structured_content.append(
                    {"type": "text", "content": paragraph.strip()}
                )

        return structured_content

    def _parse_double_newline(self):
        """Parse by double newlines"""
        paragraphs = self.content.split("\n\n")
        structured_content = []

        for content in paragraphs:
            if content.strip():
                structured_content.append({"type": "text", "content": content.strip()})

        return structured_content

    def _parse_auto_detect(self):
        """Auto-detect paragraph style"""
        # Count single vs double newlines
        single_count = self.content.count("\n")
        double_count = self.content.count("\n\n")

        # If more double newlines, use double newline parsing
        if double_count > single_count / 4:  # Threshold for detection
            return self._parse_double_newline()
        else:
            return self._parse_single_newline()

    # Content access methods
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

    def get_paragraphs_and_images(self):
        """Get all content elements with calculated numbers"""
        structured_content = self.get_structured_content()
        elements = []

        for i, element in enumerate(structured_content):
            if element["type"] == "text":
                elements.append(
                    {
                        **element,
                        "paragraph_number": i + 1,  # Calculate from array index
                        "array_index": i,
                    }
                )
            else:
                elements.append({**element, "array_index": i})

        return elements

    def get_paragraph_by_number(self, paragraph_number):
        """Get specific paragraph by number"""
        paragraphs = self.get_paragraphs()
        for paragraph in paragraphs:
            if paragraph["paragraph_number"] == paragraph_number:
                return paragraph
        return None

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

    # Content manipulation methods
    def add_paragraph(self, content, position=None):
        """Add a new paragraph to the chapter"""
        structured_content = self.get_structured_content()

        new_paragraph = {"type": "text", "content": content}

        if position is None:
            structured_content.append(new_paragraph)
        else:
            structured_content.insert(position, new_paragraph)

        self.save_structured_content(structured_content)

    def add_image(self, image_id, caption="", position=None):
        """Add an image to the chapter"""
        structured_content = self.get_structured_content()

        new_image = {"type": "image", "image_id": image_id, "caption": caption}

        if position is None:
            structured_content.append(new_image)
        else:
            structured_content.insert(position, new_image)

        self.save_structured_content(structured_content)

    def update_paragraph(self, index, content):
        """Update paragraph content at specific index"""
        structured_content = self.get_structured_content()

        if (
            0 <= index < len(structured_content)
            and structured_content[index]["type"] == "text"
        ):
            structured_content[index]["content"] = content
            self.save_structured_content(structured_content)
            return True
        return False

    def delete_element(self, index):
        """Delete element at specific index"""
        structured_content = self.get_structured_content()

        if 0 <= index < len(structured_content):
            del structured_content[index]
            self.save_structured_content(structured_content)
            return True
        return False

    def reorder_elements(self, new_order):
        """Reorder elements based on new index order"""
        structured_content = self.get_structured_content()

        if len(new_order) == len(structured_content):
            reordered_content = [structured_content[i] for i in new_order]
            self.save_structured_content(reordered_content)
            return True
        return False

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


class ChapterImage(models.Model):
    """Stores images organized by book and chapter"""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="chapter_image_upload_to")
    caption = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(help_text="Order in chapter")
    created_at = models.DateTimeField(auto_now_add=True)

    def chapter_image_upload_to(instance, filename):
        """Generate organized upload path for chapter images"""
        book_id = instance.chapter.book.id
        chapter_id = instance.chapter.id
        ext = filename.split(".")[-1]

        # Create organized path: images/book_{id}/chapter_{id}/image_{position}.{ext}
        return f"images/book_{book_id}/chapter_{chapter_id}/image_{instance.position}.{ext}"

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"Image {self.id} in Chapter {self.chapter.id}"


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
