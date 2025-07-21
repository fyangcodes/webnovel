from django.urls import path
from .views import (
    BookMasterListView,
    BookMasterCreateView,
    BookMasterDetailView,
    BookMasterUpdateView,
    BookMasterDeleteView,
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,   
    BookFileUploadView,
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
)

app_name = "books"

# Regular URL patterns
urlpatterns = [
    # BookMaster (Work/Series) views
    path("", BookMasterListView.as_view(), name="bookmaster_list"),
    path("works/create/", BookMasterCreateView.as_view(), name="bookmaster_create"),
    path("works/<int:pk>/", BookMasterDetailView.as_view(), name="bookmaster_detail"),
    path("works/<int:pk>/update/", BookMasterUpdateView.as_view(), name="bookmaster_update"),
    path("works/<int:pk>/delete/", BookMasterDeleteView.as_view(), name="bookmaster_delete"),

    # Book (Translation/Edition) views under a BookMaster
    path("works/<int:bookmaster_pk>/books/create/", BookCreateView.as_view(), name="book_create"),
    path("books/<int:pk>/", BookDetailView.as_view(), name="book_detail"),
    path("books/<int:pk>/update/", BookUpdateView.as_view(), name="book_update"),
    path("books/<int:pk>/delete/", BookDeleteView.as_view(), name="book_delete"),
    path("books/<int:pk>/upload-file/", BookFileUploadView.as_view(), name="bookfile_upload"),

    

    # Chapter CRUD views
    path("books/<int:book_pk>/chapters/create/", ChapterCreateView.as_view(), name="chapter_create"),
    path("chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter_detail"),
    path("chapters/<int:pk>/update/", ChapterUpdateView.as_view(), name="chapter_update"),
    path("chapters/<int:pk>/delete/", ChapterDeleteView.as_view(), name="chapter_delete"),
        
    # Chapter translation views
    #path("chapters/<int:pk>/analyze/", AnalyzeChapterView.as_view(), name="chapter_analyze"),
    #path("chapters/<int:chapter_id>/initiate-translation/<int:language_id>/", ChapterTranslationView.as_view(), name="chapter_initiate_translation"),
    #path("chapters/<int:pk>/check-translation-status/", CheckTranslationStatusView.as_view(), name="chapter_check_translation_status"),
    #path("chapters/<int:pk>/changelog/", ChapterChangelogView.as_view(), name="chapter_changelog"),
    #path("chapters/<int:pk>/compare/", ChapterVersionCompareView.as_view(), name="chapter_version_compare"),
    #path("chapters/diff/", ChapterDiffView.as_view(), name="chapter_diff"),
    
    # Chapter schedule and publish
    #path("chapters/<int:pk>/schedule/", ChapterScheduleView.as_view(), name="chapter_schedule"),
    #path("chapters/<int:pk>/publish/", ChapterPublishNowView.as_view(), name="chapter_publish_now"),
    
    # Batch processing views
    #path("batch-analyze-chapters/", BatchAnalyzeChaptersView.as_view(), name="batch_analyze_chapters"),
    
    # Task status views
    #path("task-status/", TaskStatusView.as_view(), name="task_status"),
]
