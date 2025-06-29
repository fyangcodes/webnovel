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
import logging
from django.views.decorators.http import require_http_methods
from django.views import View

from .models import Book, Chapter, Language
from .tasks import process_bookfile_async, translate_chapter_async
from .forms import BookFileForm, ChapterForm, BookForm, ChapterScheduleForm

logger = logging.getLogger(__name__)


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.object

        # Get the original chapter (either this chapter or its original)
        original_chapter = chapter.original_chapter or chapter
        
        # Get all languages that already have translations of the original chapter
        already_translated_ids = set(
            original_chapter.translations.values_list("language_id", flat=True)
        )
        
        # Add the original chapter's language
        original_language = original_chapter.get_effective_language()
        if original_language:
            already_translated_ids.add(original_language.id)
        
        # If this chapter is itself a translation, also add its own language
        if chapter.original_chapter and chapter.language:
            already_translated_ids.add(chapter.language.id)
        
        available_translation_languages = Language.objects.exclude(
            id__in=already_translated_ids
        )
        context["available_translation_languages"] = available_translation_languages

        context["existing_translations"] = chapter.translations.all()

        # Check if there are any completed translations (status = 'draft' and has content)
        completed_translations = chapter.translations.filter(
            status="draft", content__isnull=False
        ).exclude(content="")
        context["completed_translations"] = completed_translations

        return context


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


@method_decorator(csrf_exempt, name="dispatch")
class AnalyzeChapterView(LoginRequiredMixin, View):
    """View for analyzing a single chapter with LLM to generate abstract and key terms."""

    def post(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get("pk")
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__owner=request.user
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
                f"Chapter '{chapter.title}' analyzed successfully! Generated abstract and {len(key_terms)} key terms.",
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Chapter analyzed successfully! Generated abstract and {len(key_terms)} key terms.",
                    "abstract": abstract,
                    "key_terms": key_terms,
                }
            )

        except Exception as e:
            error_msg = f"Failed to analyze chapter: {str(e)}"
            messages.error(request, error_msg)
            return JsonResponse({"success": False, "error": error_msg})


@method_decorator(csrf_exempt, name="dispatch")
class BatchAnalyzeChaptersView(LoginRequiredMixin, View):
    """View for batch analyzing multiple chapters"""

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            chapter_ids = data.get("chapter_ids", [])

            if not chapter_ids:
                return JsonResponse(
                    {"success": False, "error": "No chapter IDs provided"}
                )

            chapters = Chapter.objects.filter(
                id__in=chapter_ids, book__owner=request.user
            )

            if not chapters.exists():
                return JsonResponse(
                    {"success": False, "error": "No valid chapters found"}
                )

            # Process each chapter with LLM
            processed_count = 0
            for chapter in chapters:
                try:
                    # Import LLM service here to avoid circular imports
                    from llm_integration.services import LLMTranslationService

                    llm_service = LLMTranslationService()

                    # Generate abstract and key terms with user tracking
                    abstract = llm_service.generate_chapter_abstract(
                        chapter.content, chapter=chapter, user=request.user
                    )
                    key_terms = llm_service.extract_key_terms(
                        chapter.content, chapter=chapter, user=request.user
                    )

                    # Update chapter
                    chapter.abstract = abstract
                    chapter.key_terms = key_terms
                    chapter.save()

                    processed_count += 1

                except Exception as e:
                    # Log error but continue with other chapters
                    print(f"Error processing chapter {chapter.id}: {str(e)}")
                    continue

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Successfully processed {processed_count} out of {len(chapters)} chapters",
                    "processed_count": processed_count,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON data"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})


class BookCreateTranslationView(LoginRequiredMixin, CreateView):
    """View for creating a new book as a translation of an existing book"""

    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["original_book"] = get_object_or_404(
            Book, pk=self.kwargs["book_id"], owner=self.request.user
        )
        context["is_translation"] = True
        return context

    def form_valid(self, form):
        original_book = get_object_or_404(
            Book, pk=self.kwargs["book_id"], owner=self.request.user
        )
        form.instance.owner = self.request.user
        form.instance.original_book = original_book

        # Set the language to a different one than the original if possible
        if not form.instance.language:
            # Get available languages excluding the original book's language
            available_languages = Language.objects.exclude(
                id=original_book.language.id if original_book.language else 0
            )
            if available_languages.exists():
                form.instance.language = available_languages.first()

        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Translation '{form.instance.title}' created successfully from '{original_book.title}'!",
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.pk})


class ChapterCreateTranslationView(LoginRequiredMixin, CreateView):
    """View for creating a new chapter as a translation of an existing chapter"""

    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["original_chapter"] = get_object_or_404(
            Chapter, pk=self.kwargs["chapter_id"], book__owner=self.request.user
        )
        context["is_translation"] = True

        # Get target language from URL parameter
        target_language_id = self.kwargs.get("language_id")
        if target_language_id:
            context["target_language"] = get_object_or_404(
                Language, id=target_language_id
            )

        return context

    def form_valid(self, form):
        original_chapter = get_object_or_404(
            Chapter, pk=self.kwargs["chapter_id"], book__owner=self.request.user
        )

        # Get target language
        target_language_id = self.kwargs.get("language_id")
        if not target_language_id:
            messages.error(self.request, "Target language is required for translation.")
            return self.form_invalid(form)

        target_language = get_object_or_404(Language, id=target_language_id)

        # Validate that target language is different from original
        if original_chapter.get_effective_language() == target_language:
            messages.error(
                self.request,
                "Target language must be different from the original chapter's language.",
            )
            return self.form_invalid(form)

        # Find or create the translated book
        translated_book = self._get_or_create_translated_book(
            original_chapter, target_language
        )

        # Create the translated chapter with minimal info
        # The actual content will be filled by the AI translation task
        form.instance.book = translated_book
        form.instance.original_chapter = original_chapter
        form.instance.language = target_language
        form.instance.chapter_number = original_chapter.chapter_number
        form.instance.status = (
            "translating"  # Set status to indicate translation is in progress
        )

        # Set a minimal placeholder title that will be updated by the translation task
        if not form.instance.title:
            form.instance.title = (
                original_chapter.title
            )  # Use original title as placeholder

        # Set minimal content placeholder
        if not form.instance.content:
            form.instance.content = f"Translation in progress...\n\nOriginal chapter: {original_chapter.title}\nTarget language: {target_language.name}"

        response = super().form_valid(form)

        # Start the AI translation task
        try:
            task = translate_chapter_async.delay(self.object.id, target_language.code)

            messages.success(
                self.request,
                f"Translation started! The AI is now translating '{original_chapter.title}' to {target_language.name}. "
                f"You'll be notified when the translation is complete. Task ID: {task.id}",
            )
        except Exception as e:
            # If task creation fails, update chapter status and show error
            self.object.status = "error"
            self.object.save()
            messages.error(
                self.request,
                f"Failed to start translation task: {str(e)}. Please try again.",
            )

        return response

    def _get_or_create_translated_book(self, original_chapter, target_language):
        """Helper method to find or create a translated book"""
        original_book = original_chapter.book

        # First, try to find existing translated book in the target language
        if original_book.has_translations:
            translated_book = original_book.get_translation(target_language)
            if translated_book:
                return translated_book

        # Create a new translated book if it doesn't exist
        translated_book = Book.objects.create(
            title=f"{original_book.title} ({target_language.name})",
            language=target_language,
            original_book=original_book,
            owner=self.request.user,
            status="draft",
            description=f"Translation of '{original_book.title}' to {target_language.name}",
        )

        return translated_book

    def get_success_url(self):
        # Redirect back to the original chapter to show translation status
        return reverse_lazy(
            "books:chapter_detail", kwargs={"pk": self.kwargs["chapter_id"]}
        )


@method_decorator(csrf_exempt, name="dispatch")
class CheckTranslationStatusView(LoginRequiredMixin, View):
    """View for checking translation status via AJAX"""

    def get(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get("pk")
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__owner=request.user
            )

            # Get all translations of this chapter
            translations = chapter.translations.all()
            translation_statuses = []

            for translation in translations:
                translation_statuses.append(
                    {
                        "id": translation.id,
                        "language": (
                            translation.language.name
                            if translation.language
                            else "Unknown"
                        ),
                        "language_code": (
                            translation.language.code if translation.language else ""
                        ),
                        "status": translation.status,
                        "title": translation.title,
                        "is_translating": translation.status == "translating",
                        "is_complete": translation.status == "draft"
                        and translation.original_chapter is not None,
                        "has_error": translation.status == "error",
                        "url": reverse_lazy(
                            "books:chapter_detail", kwargs={"pk": translation.id}
                        ),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "chapter_id": chapter.id,
                    "original_chapter_title": chapter.title,
                    "original_language": (
                        chapter.get_effective_language().name
                        if chapter.get_effective_language()
                        else "Unknown"
                    ),
                    "translations": translation_statuses,
                    "translation_count": len(translation_statuses),
                    "has_translations": len(translation_statuses) > 0,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})


@method_decorator(csrf_exempt, name="dispatch")
class InitiateChapterTranslationView(LoginRequiredMixin, View):
    """View for quickly initiating a chapter translation without form submission"""

    def post(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get("chapter_id")
            language_id = kwargs.get("language_id")

            # Get the original chapter
            original_chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__owner=request.user
            )

            # Get target language
            target_language = get_object_or_404(Language, id=language_id)

            # Validate that target language is different from original
            if original_chapter.get_effective_language() == target_language:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Target language must be different from the original chapter's language.",
                    }
                )

            # Check if translation already exists
            existing_translation = Chapter.objects.filter(
                original_chapter=original_chapter, language=target_language
            ).first()

            if existing_translation:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Translation to {target_language.name} already exists.",
                        "existing_translation_id": existing_translation.id,
                    }
                )

            # Find or create the translated book
            translated_book = self._get_or_create_translated_book(
                original_chapter, target_language
            )

            # Create the translated chapter
            translated_chapter = Chapter.objects.create(
                book=translated_book,
                original_chapter=original_chapter,
                language=target_language,
                chapter_number=original_chapter.chapter_number,
                title=original_chapter.title,  # Use original title as placeholder
                content=f"Translation in progress...\n\nOriginal chapter: {original_chapter.title}\nTarget language: {target_language.name}",
                status="translating",
            )

            # Start the AI translation task
            task = translate_chapter_async.delay(
                translated_chapter.id, target_language.code
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Translation started! The AI is now translating to {target_language.name}.",
                    "translated_chapter_id": translated_chapter.id,
                    "task_id": task.id,
                    "target_language": target_language.name,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    def _get_or_create_translated_book(self, original_chapter, target_language):
        """Helper method to find or create a translated book"""
        original_book = original_chapter.book

        # First, try to find existing translated book in the target language
        if original_book.has_translations:
            translated_book = original_book.get_translation(target_language)
            if translated_book:
                return translated_book

        # Create a new translated book if it doesn't exist
        translated_book = Book.objects.create(
            title=f"{original_book.title} ({target_language.name})",
            language=target_language,
            original_book=original_book,
            owner=self.request.user,
            status="draft",
            description=f"Translation of '{original_book.title}' to {target_language.name}",
        )

        return translated_book
