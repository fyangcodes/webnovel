from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from . import views
from .views import (
    BookListView, BookCreateView, BookDetailView, BookUpdateView, BookDeleteView,
    BookFileUploadView, ChapterAddView, ChapterDetailView
)

app_name = "books"

# API Routes
router = DefaultRouter()
router.register(r"books", views.BookViewSet, basename="book")

# Nested router for chapters within books
books_router = routers.NestedDefaultRouter(router, r"books", lookup="book")
books_router.register(r"chapters", views.ChapterViewSet, basename="book-chapters")

# Regular URL patterns
urlpatterns = [
    # Book views
    path("", BookListView.as_view(), name="book_list"),
    path("create/", BookCreateView.as_view(), name="book_create"),
    path("<int:pk>/", BookDetailView.as_view(), name="book_detail"),
    path("<int:pk>/update/", BookUpdateView.as_view(), name="book_update"),
    path("<int:pk>/delete/", BookDeleteView.as_view(), name="book_delete"),
    path("<int:pk>/upload-file/", BookFileUploadView.as_view(), name="bookfile_upload"),
    path("<int:pk>/add-chapter/", ChapterAddView.as_view(), name="chapter_add"),
    
    # Chapter views
    path("<int:book_id>/chapters/", views.ChapterListView.as_view(), name="chapter_list"),
    path("chapters/<int:pk>/", ChapterDetailView.as_view(), name="chapter_detail"),
    
    # API endpoints
    path("api/", include(router.urls)),
    path("api/", include(books_router.urls)),
]
