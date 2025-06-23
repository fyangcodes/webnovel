import hashlib
import os

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from languages.models import Language


class Book(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("chunking", "Dividing into Chapters"),
        ("translating", "Translating"),
        ("translated", "Translated"),
        ("proofreading", "Proofreading"),
        ("completed", "Completed"),
        ("error", "Error"),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    original_language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, related_name='books', help_text='Original language of the book')
    isbn = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True)

    # File handling
    uploaded_file = models.FileField(
        upload_to="books/original/",
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "txt", "docx", "epub"])
        ],
    )
    file_size = models.PositiveIntegerField(default=0)  # in bytes
    file_hash = models.CharField(max_length=64, blank=True)  # SHA256

    # Status and processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    processing_progress = models.PositiveIntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)

    # Metadata
    total_chapters = models.PositiveIntegerField(default=0)
    estimated_words = models.PositiveIntegerField(default=0)
    upload_date = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)

    # settings.AUTH_USER_MODEL relationship
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books"
    )

    class Meta:
        ordering = ["-upload_date"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["upload_date"]),
        ]

    def __str__(self):
        return f"{self.title} by {self.author}"

    def save(self, *args, **kwargs):
        if self.uploaded_file and not self.file_hash:
            self.file_hash = self.calculate_file_hash()
            self.file_size = self.uploaded_file.size
        super().save(*args, **kwargs)

    def calculate_file_hash(self):
        """Calculate SHA256 hash of uploaded file"""
        hash_sha256 = hashlib.sha256()
        for chunk in self.uploaded_file.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

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
    def file_extension(self):
        return os.path.splitext(self.uploaded_file.name)[1].lower()


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    chapter_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200, blank=True)
    original_text = models.TextField()
    excerpt = models.TextField(max_length=1000, blank=True)
    abstract = models.TextField(blank=True, help_text="AI-generated summary for translation context")
    key_terms = models.JSONField(default=list, help_text="Important terms for consistent translation")
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
    processing_status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chapter_number"]
        unique_together = ["book", "chapter_number"]
        indexes = [
            models.Index(fields=["book", "chapter_number"]),
            models.Index(fields=["processing_status"]),
        ]

    def __str__(self):
        return f"{self.book.title} - Chapter {self.chapter_number}"

    def save(self, *args, **kwargs):
        if self.original_text:
            self.word_count = len(self.original_text.split())
            self.char_count = len(self.original_text)
            self.excerpt = self.original_text[:1000]
        super().save(*args, **kwargs)

    @property
    def has_translations(self):
        return self.translations.exists()

    def get_translation(self, language):
        """Get latest translation for specified language (accepts Language instance or code)"""
        if isinstance(language, str):
            try:
                language = Language.objects.get(code=language)
            except Language.DoesNotExist:
                return None
        return (
            self.translations.filter(target_language=language)
            .order_by("-version")
            .first()
        )
