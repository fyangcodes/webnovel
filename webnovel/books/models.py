import hashlib

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify


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

    def __str__(self):
        return f"{self.localized_name}"


class Book(TimeStampedModel):
    title = models.CharField(max_length=255)
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
        default="draft",
        help_text="Book status (e.g., draft, published, etc.)",
    )

    # Metadata
    total_chapters = models.PositiveIntegerField(default=0)
    estimated_words = models.PositiveIntegerField(default=0)

    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            base_slug = self.slug
            counter = 1
            while Book.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class Chapter(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=255)
    content = models.TextField()
    original_chapter = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="translations",
    )
    chapter_number = models.PositiveIntegerField()
    excerpt = models.TextField(max_length=1000, blank=True)
    abstract = models.TextField(
        blank=True, help_text="AI-generated summary for translation context"
    )
    key_terms = models.JSONField(
        default=list, help_text="Important terms for consistent translation"
    )
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
    active_at = models.DateTimeField(null=True, blank=True)

    slug = models.SlugField(max_length=255, blank=True)

    class Meta:
        ordering = ["chapter_number"]
        unique_together = ["book", "chapter_number"]
        indexes = [models.Index(fields=["book", "chapter_number"])]

    def __str__(self):
        return f"{self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness per book
            base_slug = self.slug
            counter = 1
            while Chapter.objects.filter(book=self.book, slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        if self.content:
            self.word_count = len(self.content.split())
            self.char_count = len(self.content)
            self.excerpt = self.content[:1000]
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.active_at is not None and self.active_at <= timezone.now()

    @property
    def has_translations(self):
        # Returns True if there are chapters that reference this chapter as their original_chapter
        return self.translations.exists()

    def get_translation(self, language):
        """
        Returns the translated chapter in the specified language.
        Accepts either a Language instance or a language code (str).
        """
        if isinstance(language, str):
            return self.translations.filter(language__code=language).first()
        return self.translations.filter(language=language).first()


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
        return f"{self.get_change_type_display()} by {self.user} on {self.date}"


def book_file_upload_to(instance, filename):
    # instance is a BookFile object
    # instance.book is the related Book object
    return f"book_files/{instance.book.id}/{filename}"


class BookFile(TimeStampedModel):
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
    processing_progress = models.PositiveIntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)

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
