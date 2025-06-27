import hashlib

from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from .fields import AutoIncrementingPositiveIntegerField

# Custom validator for Unicode slugs
unicode_slug_validator = RegexValidator(
    regex=r'^[^\s/\\?%*:|"<>]+$',
    message='Slug can contain any characters except whitespace and /\\?%*:|"<>',
    code='invalid_slug'
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
    code = models.CharField(max_length=10, unique=True)  # e.g., 'en'
    name = models.CharField(max_length=50)  # e.g., 'English'
    local_name = models.CharField(max_length=50)  # e.g., 'English'

    def __str__(self):
        return self.name


class Author(TimeStampedModel):
    canonical_name = models.CharField(max_length=255)
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
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
    slug = models.CharField(max_length=255, unique=True, blank=True, validators=[unicode_slug_validator])
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
    slug = models.CharField(max_length=255, blank=True, validators=[unicode_slug_validator])
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
        help_text="When this chapter should become active/published"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Chapter status",
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
        if self.status == "published" and self.active_at and self.active_at > timezone.now():
            raise ValidationError("Published chapters cannot have future active_at dates")
        
        # Ensure slug is not empty (let Django's SlugField handle format validation)
        if self.slug and self.slug.strip() == "":
            raise ValidationError("Slug cannot be empty")

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # Auto-update status based on active_at
        if self.active_at and self.active_at <= timezone.now() and self.status == "scheduled":
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
        """Unpublish this chapter (set back to draft)"""
        self.status = "draft"
        self.active_at = None
        self.save()

    @classmethod
    def get_published_chapters(cls, book=None):
        """Get all currently published chapters, optionally filtered by book"""
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
        """Returns the language of this chapter, falling back to book language"""
        return self.language or self.book.language


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
    version = models.PositiveIntegerField(default=1)
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
