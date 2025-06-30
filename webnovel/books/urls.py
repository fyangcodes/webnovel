from django.urls import path
from . import views
from .views import (
    BookListView,
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,
    BookFileUploadView,
    BookCreateTranslationView,
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
    ChapterScheduleView,
    ChapterPublishNowView,
    ChapterTranslationView,
    CheckTranslationStatusView,
    AnalyzeChapterView,
    BatchAnalyzeChaptersView,
    ChapterChangelogView,
    ChapterDiffView,
)

app_name = "books"

# Regular URL patterns
urlpatterns = [
    # Book views
    path("", BookListView.as_view(), name="book_list"),
    path("create/", BookCreateView.as_view(), name="book_create"),
    path("<int:pk>/", BookDetailView.as_view(), name="book_detail"),
    path("<int:pk>/update/", BookUpdateView.as_view(), name="book_update"),
    path("<int:pk>/delete/", BookDeleteView.as_view(), name="book_delete"),
    path("<int:pk>/upload-file/", BookFileUploadView.as_view(), name="bookfile_upload"),
    path("<int:pk>/create-translation/", BookCreateTranslationView.as_view(), name="book_create_translation"),
    
    # Chapter CRUD views
    path("<int:pk>/chapters/create/", ChapterCreateView.as_view(), name="chapter_create"),
    path("chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter_detail"),
    path("chapters/<int:pk>/update/", ChapterUpdateView.as_view(), name="chapter_update"),
    path("chapters/<int:pk>/delete/", ChapterDeleteView.as_view(), name="chapter_delete"),
        
    # Chapter translation views
    path("chapters/<int:pk>/analyze/", AnalyzeChapterView.as_view(), name="chapter_analyze"),
    path("chapters/<int:chapter_id>/initiate-translation/<int:language_id>/", ChapterTranslationView.as_view(), name="chapter_initiate_translation"),
    path("chapters/<int:pk>/check-translation-status/", CheckTranslationStatusView.as_view(), name="chapter_check_translation_status"),
    path("chapters/<int:pk>/changelog/", ChapterChangelogView.as_view(), name="chapter_changelog"),
    path("chapters/diff/", ChapterDiffView.as_view(), name="chapter_diff"),
    
    # Chapter schedule and publish
    path("chapters/<int:pk>/schedule/", ChapterScheduleView.as_view(), name="chapter_schedule"),
    path("chapters/<int:pk>/publish/", ChapterPublishNowView.as_view(), name="chapter_publish_now"),
    
    # Batch processing views
    path("batch-analyze-chapters/", BatchAnalyzeChaptersView.as_view(), name="batch_analyze_chapters"),
]
