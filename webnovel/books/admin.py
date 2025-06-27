from django.contrib import admin
from .models import Book, Chapter, Language, BookFile, Author, ChangeLog


class BookFileInline(admin.TabularInline):
    model = BookFile
    extra = 1


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 1
    readonly_fields = ['word_count', 'char_count', 'created_at']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "slug",
        "author",
        "owner",
        "status",
        "total_chapters",
        "total_words",
        "created_at",
    ]
    list_filter = ["status", "language", "created_at"]
    search_fields = ["title", "author__localized_name", "owner__username"]
    readonly_fields = ["slug", "total_chapters", "total_words", "total_characters", "estimated_words", "created_at", "updated_at"]
    inlines = [BookFileInline, ChapterInline]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "slug", "author", "language", "isbn", "description", "cover_image")},
        ),
        (
            "Status & Metadata",
            {
                "fields": (
                    "status",
                    "total_chapters",
                    "total_words",
                    "total_characters",
                    "estimated_words",
                )
            },
        ),
        (
            "Relationships",
            {"fields": ("owner", "original_book")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = [
        "title", 
        "chapter_number", 
        "book", 
        "status", 
        "word_count", 
        "active_at",
        "created_at"
    ]
    list_filter = ["status", "language", "created_at", "active_at"]
    search_fields = ["title", "book__title", "content"]
    readonly_fields = ["slug", "word_count", "char_count", "created_at", "updated_at"]
    
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("book", "title", "slug", "chapter_number", "content")},
        ),
        (
            "Status & Publishing",
            {"fields": ("status", "active_at", "language")},
        ),
        (
            "Analysis",
            {"fields": ("excerpt", "abstract", "key_terms")},
        ),
        (
            "Statistics",
            {"fields": ("word_count", "char_count")},
        ),
        (
            "Relationships",
            {"fields": ("original_chapter",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "local_name"]
    search_fields = ["code", "name", "local_name"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["canonical_name", "localized_name", "language"]
    list_filter = ["language"]
    search_fields = ["canonical_name", "localized_name"]


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
    list_display = ["file", "book", "owner", "status", "processing_progress", "created_at"]
    list_filter = ["status", "file_type", "created_at"]
    readonly_fields = ["file_size", "file_hash", "file_type", "processing_duration", "created_at", "updated_at"]


@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ["change_type", "user", "content_type", "status", "created_at"]
    list_filter = ["change_type", "status", "created_at"]
    readonly_fields = ["created_at", "updated_at"]
