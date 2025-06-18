from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.views.generic import ListView, DetailView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages

from .models import Book, Chapter
from .serializers import (
    BookSerializer,
    BookCreateSerializer,
    ChapterSerializer,
    ChapterDetailSerializer,
)
from .tasks import process_book_async
from .utils import extract_text_from_file

# Regular Django Views
class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = 'books/book_list.html'
    context_object_name = 'books'

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = 'books/book_detail.html'
    context_object_name = 'book'

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chapters'] = self.object.chapters.all().order_by('chapter_number')
        return context

class BookUploadView(LoginRequiredMixin, CreateView):
    model = Book
    template_name = 'books/book_upload.html'
    fields = ['title', 'author', 'uploaded_file']
    success_url = reverse_lazy('books:book_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.status = 'uploaded'
        response = super().form_valid(form)
        
        # Start async processing
        process_book_async.delay(self.object.id)
        messages.success(self.request, 'Book uploaded successfully and is being processed.')
        
        return response

class BookDeleteView(LoginRequiredMixin, DeleteView):
    model = Book
    template_name = 'books/book_confirm_delete.html'
    success_url = reverse_lazy('books:book_list')

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        book = self.get_object()
        if book.uploaded_file:
            book.uploaded_file.delete()
        messages.success(request, 'Book deleted successfully.')
        return super().delete(request, *args, **kwargs)

class ChapterListView(LoginRequiredMixin, ListView):
    model = Chapter
    template_name = 'books/chapter_list.html'
    context_object_name = 'chapters'

    def get_queryset(self):
        self.book = get_object_or_404(Book, id=self.kwargs['book_id'], user=self.request.user)
        return Chapter.objects.filter(book=self.book).order_by('chapter_number')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['book'] = self.book
        return context

class ChapterDetailView(LoginRequiredMixin, DetailView):
    model = Chapter
    template_name = 'books/chapter_detail.html'
    context_object_name = 'chapter'

    def get_queryset(self):
        return Chapter.objects.filter(book__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['book'] = self.object.book
        return context

# Existing ViewSets
class BookViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return BookCreateSerializer
        return BookSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            book = serializer.save()
            # Start async processing
            process_book_async.delay(book.id)

        return Response(BookSerializer(book).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """Reprocess a book (useful if processing failed)"""
        book = self.get_object()

        if book.is_processing:
            return Response(
                {"error": "Book is already being processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        book.status = "processing"
        book.processing_progress = 0
        book.error_message = ""
        book.save()

        process_book_async.delay(book.id)

        return Response({"message": "Book reprocessing started"})

    @action(detail=True, methods=["get"])
    def chapters(self, request, pk=None):
        """Get all chapters for a book"""
        book = self.get_object()
        chapters = book.chapters.all()
        serializer = ChapterSerializer(chapters, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["delete"])
    def delete_with_files(self, request, pk=None):
        """Delete book and associated files"""
        book = self.get_object()

        # Delete the uploaded file
        if book.uploaded_file:
            book.uploaded_file.delete()

        book.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChapterViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        book_id = self.kwargs.get("book_pk")
        if book_id:
            book = get_object_or_404(Book, id=book_id, user=self.request.user)
            return Chapter.objects.filter(book=book)
        return Chapter.objects.filter(book__user=self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ChapterDetailSerializer
        return ChapterSerializer

    @action(detail=True, methods=["post"])
    def regenerate_abstract(self, request, pk=None):
        """Regenerate AI abstract for a chapter"""
        from .tasks import generate_chapter_abstract_async

        chapter = self.get_object()
        generate_chapter_abstract_async.delay(chapter.id)

        return Response({"message": "Abstract regeneration started"})
