from django.contrib import admin
from .models import Book, Chapter, Language, BookFile, Author, ChangeLog


class BookFileInline(admin.TabularInline):
    model = BookFile
    extra = 1


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "author",
        "owner",
        "status",
        "total_chapters",
    ]
    list_filter = ["status"]
    search_fields = ["title", "author", "owner__username"]
    readonly_fields = []
    inlines = [BookFileInline]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "author", "isbn", "description")},
        ),
        ("File Information", {"fields": ()}),
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
            {"fields": ()},
        ),
    )


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "chapter_number", "book"]
    list_filter = []


admin.site.register(Language)
admin.site.register(Author)
admin.site.register(BookFile)
admin.site.register(ChangeLog)
