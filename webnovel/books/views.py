from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    DeleteView,
    UpdateView,
    FormView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils import timezone
import json
from django.views.decorators.http import require_http_methods
from django.views import View

from .models import Book, Chapter
from .tasks import process_bookfile_async, schedule_chapter_publishing_async
from .forms import BookFileForm, ChapterForm, BookForm, ChapterScheduleForm


# Regular Django Views
class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = "books/book/list.html"
    context_object_name = "books"

    def get_queryset(self):
        return Book.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book_create_url"] = reverse_lazy("books:book_create")
        return context


class BookCreateView(LoginRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"
    success_url = reverse_lazy("books:book_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = "books/book/detail.html"
    context_object_name = "book"

    def get_queryset(self):
        return Book.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapters"] = self.object.chapters.all().order_by("chapter_number")
        context["published_chapters"] = self.object.chapters.filter(
            status="published"
        ).order_by("chapter_number")
        context["scheduled_chapters"] = self.object.chapters.filter(
            status="scheduled"
        ).order_by("chapter_number")
        context["draft_chapters"] = self.object.chapters.filter(
            status="draft"
        ).order_by("chapter_number")
        context["chapter_create_url"] = reverse_lazy(
            "books:chapter_create", kwargs={"book_id": self.object.pk}
        )
        return context


class BookUpdateView(LoginRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"
    context_object_name = "book"

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class BookDeleteView(LoginRequiredMixin, DeleteView):
    model = Book
    template_name = "books/book/confirm_delete.html"
    success_url = reverse_lazy("books:book_list")

    def get_queryset(self):
        return Book.objects.filter(owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        book = self.get_object()
        # Remove uploaded_file reference as it's not in the new model
        # if book.uploaded_file:
        #     book.uploaded_file.delete()
        messages.success(request, "Book deleted successfully.")
        return super().delete(request, *args, **kwargs)


class BookFileUploadView(LoginRequiredMixin, FormView):
    form_class = BookFileForm
    template_name = "books/bookfile/upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = get_object_or_404(
            Book, pk=self.kwargs["pk"], owner=self.request.user
        )
        return context

    def form_valid(self, form):
        book = get_object_or_404(Book, pk=self.kwargs["pk"], owner=self.request.user)
        book_file = form.save(commit=False)
        book_file.book = book
        book_file.owner = self.request.user
        book_file.save()
        # Trigger async processing
        process_bookfile_async.delay(book_file.id)
        return redirect("books:book_detail", pk=book.pk)


# Chapter CRUD Views
class ChapterCreateView(LoginRequiredMixin, CreateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = get_object_or_404(
            Book, pk=self.kwargs["book_id"], owner=self.request.user
        )
        return context

    def form_valid(self, form):
        book = get_object_or_404(
            Book, pk=self.kwargs["book_id"], owner=self.request.user
        )
        form.instance.book = book
        response = super().form_valid(form)
        messages.success(
            self.request, f"Chapter '{form.instance.title}' created successfully!"
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.kwargs["book_id"]})


class ChapterDetailView(LoginRequiredMixin, DetailView):
    model = Chapter
    template_name = "books/chapter/detail.html"
    context_object_name = "chapter"

    def get_queryset(self):
        return Chapter.objects.filter(book__owner=self.request.user)


class ChapterUpdateView(LoginRequiredMixin, UpdateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"
    context_object_name = "chapter"

    def get_queryset(self):
        return Chapter.objects.filter(book__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = self.object.book
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, f"Chapter '{form.instance.title}' updated successfully!"
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:chapter_detail", kwargs={"pk": self.object.pk})


class ChapterDeleteView(LoginRequiredMixin, DeleteView):
    model = Chapter
    template_name = "books/chapter/confirm_delete.html"
    context_object_name = "chapter"

    def get_queryset(self):
        return Chapter.objects.filter(book__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        chapter = self.get_object()
        book_id = chapter.book.id
        messages.success(request, f"Chapter '{chapter.title}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            "books:book_detail",
            kwargs={"pk": self.kwargs.get("book_id") or self.object.book.id},
        )


# Chapter Publishing Views
class ChapterScheduleView(LoginRequiredMixin, FormView):
    """View for scheduling chapter publication"""

    form_class = ChapterScheduleForm
    template_name = "books/chapter/schedule.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chapter"] = get_object_or_404(
            Chapter, pk=self.kwargs["pk"], book__owner=self.request.user
        )
        return context

    def form_valid(self, form):
        chapter = get_object_or_404(
            Chapter, pk=self.kwargs["pk"], book__owner=self.request.user
        )
        publish_datetime = form.cleaned_data["publish_datetime"]

        try:
            chapter.schedule_for_publishing(publish_datetime)
            messages.success(
                self.request,
                f"Chapter '{chapter.title}' scheduled for publication on {publish_datetime.strftime('%Y-%m-%d %H:%M')}",
            )
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        return redirect("books:book_detail", pk=chapter.book.pk)


class ChapterPublishNowView(LoginRequiredMixin, DetailView):
    """View for publishing a chapter immediately"""

    model = Chapter
    template_name = "books/chapter/publish_confirm.html"

    def get_queryset(self):
        return Chapter.objects.filter(book__owner=self.request.user)

    def post(self, request, *args, **kwargs):
        chapter = self.get_object()
        try:
            chapter.publish_now()
            messages.success(
                request, f"Chapter '{chapter.title}' published successfully!"
            )
        except Exception as e:
            messages.error(request, f"Failed to publish chapter: {str(e)}")

        return redirect("books:book_detail", pk=chapter.book.pk)


@method_decorator(csrf_exempt, name='dispatch')
class AnalyzeChapterView(LoginRequiredMixin, View):
    """View for analyzing a single chapter with LLM to generate abstract and key terms."""
    
    def post(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get('pk')
            chapter = get_object_or_404(
                Chapter, 
                pk=chapter_id, 
                book__owner=request.user
            )
            
            # Import LLM service here to avoid circular imports
            from llm_integration.services import LLMTranslationService
            llm_service = LLMTranslationService()
            
            # Generate abstract and key terms
            abstract = llm_service.generate_chapter_abstract(chapter.content)
            key_terms = llm_service.extract_key_terms(chapter.content)
            
            # Update chapter
            chapter.abstract = abstract
            chapter.key_terms = key_terms
            chapter.save()
            
            messages.success(
                request, 
                f"Chapter '{chapter.title}' analyzed successfully! Generated abstract and {len(key_terms)} key terms."
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Chapter analyzed successfully! Generated abstract and {len(key_terms)} key terms.',
                'abstract': abstract,
                'key_terms': key_terms
            })
            
        except Exception as e:
            error_msg = f"Failed to analyze chapter: {str(e)}"
            messages.error(request, error_msg)
            return JsonResponse({'success': False, 'error': error_msg})


@method_decorator(csrf_exempt, name='dispatch')
class BatchAnalyzeChaptersView(LoginRequiredMixin, View):
    """View for batch analyzing chapters with LLM to generate abstracts and key terms."""
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            chapter_ids = data.get('chapter_ids', [])
            book_id = data.get('book_id')
            
            if not chapter_ids:
                return JsonResponse({'success': False, 'error': 'No chapters selected'})
            
            # Get chapters that belong to the user
            chapters = Chapter.objects.filter(
                id__in=chapter_ids,
                book__owner=request.user,
                book_id=book_id
            )
            
            if not chapters.exists():
                return JsonResponse({'success': False, 'error': 'No valid chapters found'})
            
            # Process each chapter with LLM
            processed_count = 0
            for chapter in chapters:
                try:
                    # Import LLM service here to avoid circular imports
                    from llm_integration.services import LLMTranslationService
                    llm_service = LLMTranslationService()
                    
                    # Generate abstract and key terms
                    abstract = llm_service.generate_chapter_abstract(chapter.content)
                    key_terms = llm_service.extract_key_terms(chapter.content)
                    
                    # Update chapter
                    chapter.abstract = abstract
                    chapter.key_terms = key_terms
                    chapter.save()
                    
                    processed_count += 1
                    
                except Exception as e:
                    # Log error but continue with other chapters
                    print(f"Error processing chapter {chapter.id}: {str(e)}")
                    continue
            
            return JsonResponse({
                'success': True, 
                'message': f'Successfully processed {processed_count} out of {len(chapters)} chapters',
                'processed_count': processed_count
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
