from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from . import views

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
    path("", views.BookListView.as_view(), name="book_list"),
    path("upload/", views.BookUploadView.as_view(), name="book_upload"),
    path("<int:pk>/", views.BookDetailView.as_view(), name="book_detail"),
    path("<int:pk>/delete/", views.BookDeleteView.as_view(), name="book_delete"),
    
    # Chapter views
    path("<int:book_id>/chapters/", views.ChapterListView.as_view(), name="chapter_list"),
    path("chapters/<int:pk>/", views.ChapterDetailView.as_view(), name="chapter_detail"),
    
    # API endpoints
    path("api/", include(router.urls)),
    path("api/", include(books_router.urls)),
]
