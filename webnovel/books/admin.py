from django.contrib import admin
from .models import Book, Chapter


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "author",
        "user",
        "status",
        "total_chapters",
        "upload_date",
    ]
    list_filter = ["status", "original_language", "upload_date"]
    search_fields = ["title", "author", "user__username"]
    readonly_fields = ["file_hash", "file_size", "processing_duration"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "author", "original_language", "isbn", "description")},
        ),
        ("File Information", {"fields": ("uploaded_file", "file_size", "file_hash")}),
        (
            "Processing Status",
            {
                "fields": (
                    "status",
                    "processing_progress",
                    "error_message",
                    "total_chapters",
                    "estimated_words",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "upload_date",
                    "processing_started_at",
                    "processing_completed_at",
                    "processing_duration",
                )
            },
        ),
    )


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["__str__", "processing_status", "word_count", "has_translations"]
    list_filter = ["processing_status", "book__status"]
    search_fields = ["title", "book__title", "excerpt"]
    readonly_fields = ["word_count", "char_count"]

    fieldsets = (
        ("Basic Information", {"fields": ("book", "chapter_number", "title")}),
        ("Content", {"fields": ("excerpt", "original_text")}),
        ("AI Analysis", {"fields": ("abstract", "key_terms")}),
        ("Metadata", {"fields": ("word_count", "char_count", "processing_status")}),
    )
