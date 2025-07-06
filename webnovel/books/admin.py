from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from .models import Book, Chapter, Language, BookFile, Author, ChangeLog, ChapterImage, ChapterMedia


class BookFileInline(admin.TabularInline):
    model = BookFile
    extra = 1


class ChapterImageInline(admin.TabularInline):
    model = ChapterImage
    extra = 1
    readonly_fields = ['created_at']


class ChapterMediaInline(admin.TabularInline):
    model = ChapterMedia
    extra = 1
    readonly_fields = ['created_at', 'updated_at', 'file_size', 'mime_type', 'formatted_file_size', 'formatted_duration']
    fields = ['media_type', 'file', 'title', 'caption', 'alt_text', 'position', 'duration', 'thumbnail']


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
        "paragraph_style",
        "active_at",
        "created_at"
    ]
    list_filter = ["status", "language", "paragraph_style", "created_at", "active_at"]
    search_fields = ["title", "book__title", "content"]
    readonly_fields = [
        "slug", 
        "word_count", 
        "char_count", 
        "content_file_path",
        "created_at", 
        "updated_at",
        "structured_content_preview",
        "paragraph_count",
        "image_count"
    ]
    inlines = [ChapterImageInline, ChapterMediaInline]
    
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("book", "title", "slug", "chapter_number", "content")},
        ),
        (
            "Structured Content",
            {
                "fields": ("paragraph_style", "content_file_path", "structured_content_preview"),
                "description": "Configure how content is parsed and stored in structured format."
            },
        ),
        (
            "Content Statistics",
            {"fields": ("paragraph_count", "image_count")},
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
    
    actions = ['regenerate_structured_content', 'sync_media_with_content', 'rebuild_content_from_media']
    
    def structured_content_preview(self, obj):
        """Show a preview of the structured content"""
        if not obj.pk:
            return "Save the chapter first to see structured content preview."
        
        try:
            structured_content = obj.get_structured_content()
            if not structured_content:
                return "No structured content available."
            
            preview_lines = []
            for i, element in enumerate(structured_content[:5]):  # Show first 5 elements
                if element['type'] == 'text':
                    content_preview = element['content'][:100] + "..." if len(element['content']) > 100 else element['content']
                    preview_lines.append(f"[{i}] Text: {content_preview}")
                elif element['type'] == 'image':
                    preview_lines.append(f"[{i}] Image: ID {element.get('image_id', 'N/A')} - {element.get('caption', 'No caption')}")
            
            if len(structured_content) > 5:
                preview_lines.append(f"... and {len(structured_content) - 5} more elements")
            
            return "<br>".join(preview_lines)
        except Exception as e:
            return f"Error loading structured content: {str(e)}"
    
    structured_content_preview.short_description = "Structured Content Preview"
    structured_content_preview.allow_tags = True
    
    def paragraph_count(self, obj):
        """Show the number of paragraphs in structured content"""
        if not obj.pk:
            return "N/A"
        
        try:
            paragraphs = obj.get_paragraphs()
            return len(paragraphs)
        except Exception:
            return "Error"
    
    paragraph_count.short_description = "Paragraph Count"
    
    def image_count(self, obj):
        """Show the number of images in the chapter"""
        if not obj.pk:
            return "N/A"
        
        try:
            return obj.images.count()
        except Exception:
            return "Error"
    
    image_count.short_description = "Image Count"
    

    
    def regenerate_structured_content(self, request, queryset):
        """Regenerate structured content for selected chapters"""
        regenerated_count = 0
        for chapter in queryset:
            try:
                # Force regeneration by parsing legacy content
                structured_content = chapter._parse_legacy_content()
                # Save to file
                chapter.save_structured_content(structured_content)
                regenerated_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Error regenerating chapter {chapter.title}: {str(e)}", 
                    level=messages.ERROR
                )
        
        self.message_user(
            request, 
            f"Successfully regenerated structured content for {regenerated_count} chapters."
        )
    regenerate_structured_content.short_description = "Regenerate structured content"

    def sync_media_with_content(self, request, queryset):
        """Sync media items with structured content for selected chapters"""
        synced_count = 0
        total_added = 0
        
        for chapter in queryset:
            try:
                added = chapter.sync_media_with_content()
                if added > 0:
                    synced_count += 1
                    total_added += added
            except Exception as e:
                self.message_user(
                    request, 
                    f"Error syncing chapter {chapter.title}: {str(e)}", 
                    level=messages.ERROR
                )
        
        if total_added > 0:
            self.message_user(
                request, 
                f"Successfully synced {synced_count} chapters. Added {total_added} media items to structured content."
            )
        else:
            self.message_user(
                request, 
                f"No new media items found to sync in {synced_count} chapters."
            )
    sync_media_with_content.short_description = "Sync media with structured content"

    def rebuild_content_from_media(self, request, queryset):
        """Rebuild structured content from media order for selected chapters"""
        rebuilt_count = 0
        
        for chapter in queryset:
            try:
                elements_count = chapter.rebuild_structured_content_from_media()
                rebuilt_count += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f"Error rebuilding chapter {chapter.title}: {str(e)}", 
                    level=messages.ERROR
                )
        
        self.message_user(
            request, 
            f"Successfully rebuilt structured content for {rebuilt_count} chapters."
        )
    rebuild_content_from_media.short_description = "Rebuild content from media order"
    
    def get_urls(self):
        """Add custom URLs for quick actions"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:chapter_id>/regenerate-structured/',
                self.admin_site.admin_view(self.regenerate_single_chapter),
                name='books_chapter_regenerate_structured',
            ),
            path(
                '<int:chapter_id>/sync-media/',
                self.admin_site.admin_view(self.sync_single_chapter_media),
                name='books_chapter_sync_media',
            ),
            path(
                '<int:chapter_id>/rebuild-content/',
                self.admin_site.admin_view(self.rebuild_single_chapter_content),
                name='books_chapter_rebuild_content',
            ),
        ]
        return custom_urls + urls
    

    
    def regenerate_single_chapter(self, request, chapter_id):
        """Regenerate structured content for a single chapter"""
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            structured_content = chapter._parse_legacy_content()
            chapter.save_structured_content(structured_content)
            messages.success(
                request, 
                f"Successfully regenerated structured content for chapter '{chapter.title}'."
            )
        except Chapter.DoesNotExist:
            messages.error(request, "Chapter not found.")
        except Exception as e:
            messages.error(request, f"Error regenerating chapter: {str(e)}")
        
        return redirect('admin:books_chapter_change', chapter_id)

    def sync_single_chapter_media(self, request, chapter_id):
        """Sync media with structured content for a single chapter"""
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            chapter.sync_media_with_content()
            messages.success(
                request,
                f"Media synchronized with structured content for chapter '{chapter.title}'"
            )
        except Chapter.DoesNotExist:
            messages.error(request, "Chapter not found.")
        except Exception as e:
            messages.error(request, f"Error synchronizing media: {str(e)}")
        
        return redirect('admin:books_chapter_change', chapter_id)

    def rebuild_single_chapter_content(self, request, chapter_id):
        """Rebuild structured content from media for a single chapter"""
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            chapter.rebuild_structured_content_from_media()
            messages.success(
                request,
                f"Structured content rebuilt from media for chapter '{chapter.title}'"
            )
        except Chapter.DoesNotExist:
            messages.error(request, "Chapter not found.")
        except Exception as e:
            messages.error(request, f"Error rebuilding content: {str(e)}")
        
        return redirect('admin:books_chapter_change', chapter_id)


@admin.register(ChapterImage)
class ChapterImageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "chapter", 
        "position", 
        "caption", 
        "created_at"
    ]
    list_filter = ["created_at", "chapter__book"]
    search_fields = ["caption", "alt_text", "chapter__title", "chapter__book__title"]
    readonly_fields = ["created_at"]
    
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("chapter", "image", "position")},
        ),
        (
            "Content",
            {"fields": ("caption", "alt_text")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",)},
        ),
    )


@admin.register(ChapterMedia)
class ChapterMediaAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "chapter", 
        "media_type",
        "display_title",
        "position", 
        "formatted_file_size",
        "formatted_duration",
        "is_processed",
        "created_at"
    ]
    list_filter = ["media_type", "is_processed", "created_at", "chapter__book"]
    search_fields = ["title", "caption", "alt_text", "chapter__title", "chapter__book__title"]
    readonly_fields = [
        "created_at", 
        "updated_at", 
        "file_size", 
        "mime_type", 
        "formatted_file_size", 
        "formatted_duration"
    ]
    
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("chapter", "media_type", "file", "position")},
        ),
        (
            "Content",
            {"fields": ("title", "caption", "alt_text")},
        ),
        (
            "Media Metadata",
            {"fields": ("duration", "thumbnail", "formatted_file_size", "formatted_duration")},
        ),
        (
            "Processing",
            {"fields": ("is_processed", "processing_error")},
        ),
        (
            "File Information",
            {"fields": ("file_size", "mime_type")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )

    def display_title(self, obj):
        return obj.display_title
    display_title.short_description = "Title"

    def formatted_file_size(self, obj):
        return obj.formatted_file_size
    formatted_file_size.short_description = "File Size"

    def formatted_duration(self, obj):
        return obj.formatted_duration or "N/A"
    formatted_duration.short_description = "Duration"


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
