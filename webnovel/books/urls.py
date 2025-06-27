from django.urls import path
from . import views
from .views import (
    BookListView,
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,
    BookFileUploadView,
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
    ChapterScheduleView,
    ChapterPublishNowView,
    AnalyzeChapterView,
    BatchAnalyzeChaptersView,
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
    
    # Chapter CRUD views
    path("<int:book_id>/chapters/create/", ChapterCreateView.as_view(), name="chapter_create"),
    path("chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter_detail"),
    path("chapters/<int:pk>/update/", ChapterUpdateView.as_view(), name="chapter_update"),
    path("chapters/<int:pk>/delete/", ChapterDeleteView.as_view(), name="chapter_delete"),
    
    # Chapter publishing views
    path("chapters/<int:pk>/schedule/", ChapterScheduleView.as_view(), name="chapter_schedule"),
    path("chapters/<int:pk>/publish/", ChapterPublishNowView.as_view(), name="chapter_publish_now"),
    path("chapters/<int:pk>/analyze/", AnalyzeChapterView.as_view(), name="chapter_analyze"),
    
    # Batch processing views
    path("batch-analyze-chapters/", BatchAnalyzeChaptersView.as_view(), name="batch_analyze_chapters"),
]
