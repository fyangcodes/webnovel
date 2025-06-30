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
from django.contrib.contenttypes.models import ContentType
import json
import logging
from django.views.decorators.http import require_http_methods
from django.views import View
import difflib
from django.db import models

from .models import Book, Chapter, Language, ChangeLog
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
            Book, pk=self.kwargs["pk"], owner=self.request.user
        )
        return context

    def form_valid(self, form):
        book = get_object_or_404(Book, pk=self.kwargs["pk"], owner=self.request.user)
        form.instance.book = book
        response = super().form_valid(form)
        messages.success(
            self.request, f"Chapter '{form.instance.title}' created successfully!"
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.kwargs["pk"]})


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
        # Check if this is a translation that's being edited
        chapter = form.instance
        is_translation = (
            hasattr(chapter, "original_chapter")
            and chapter.original_chapter is not None
        )
        
        # Store the original content before saving
        original_content = None
        original_title = None
        if chapter.pk:  # Only for existing chapters
            try:
                original_chapter = Chapter.objects.get(pk=chapter.pk)
                original_content = original_chapter.content
                original_title = original_chapter.title
            except Chapter.DoesNotExist:
                pass
        
        response = super().form_valid(form)
        
        # Create changelog entry for manual edits to all chapters
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            
            # Check for any changes (title or content)
            title_changed = original_title and original_title != chapter.title
            content_changed = original_content and original_content != chapter.content
            
            # Generate diff if there are any changes
            diff_content = ""
            if title_changed or content_changed:
                title_diff = ""
                content_diff = ""
                
                if title_changed:
                    title_diff = self._generate_diff(
                        original_title,
                        chapter.title,
                        context_lines=1
                    )
                
                if content_changed:
                    content_diff = self._generate_diff(
                        original_content,
                        chapter.content,
                        context_lines=3
                    )
                
                # Build the diff content
                if title_changed and content_changed:
                    diff_content = f"Title Changes:\n{title_diff}\n\nContent Changes:\n{content_diff}"
                elif title_changed:
                    diff_content = f"Title Changes:\n{title_diff}"
                elif content_changed:
                    diff_content = f"Content Changes:\n{content_diff}"
            
            # Create changelog entry if there are any changes
            if title_changed or content_changed:
                # Determine the notes based on what changed
                change_description = []
                if title_changed:
                    change_description.append("title")
                if content_changed:
                    change_description.append("content")
                
                change_text = " and ".join(change_description)
                
                if is_translation:
                    notes = f"Manual edit applied to {chapter.language.name if chapter.language else 'Unknown'} translation ({change_text} modified)"
                else:
                    notes = f"Manual edit applied to original chapter ({change_text} modified)"
                
                ChangeLog.objects.create(
                    content_type=content_type,
                    original_object_id=chapter.original_chapter.id if is_translation else chapter.id,
                    changed_object_id=chapter.id,
                    user=self.request.user,
                    change_type="edit",
                    status="completed",
                    notes=notes,
                    diff=diff_content,
                )
        except Exception as e:
            logger.error(
                f"Failed to create changelog entry for manual edit: {str(e)}"
            )
        
        messages.success(
            self.request, f"Chapter '{form.instance.title}' updated successfully!"
        )
        return response

    def _generate_diff(self, original_text, changed_text, context_lines=3):
        """Generate a diff between two text versions"""
        try:
            # Split texts into lines
            original_lines = original_text.splitlines(keepends=True)
            changed_lines = changed_text.splitlines(keepends=True)
            
            # Generate diff
            diff = difflib.unified_diff(
                original_lines,
                changed_lines,
                fromfile='Before',
                tofile='After',
                lineterm='',
                n=context_lines
            )
            
            return '\n'.join(diff)
        except Exception as e:
            logger.error(f"Error generating diff: {str(e)}")
            return f"Error generating diff: {str(e)}"

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
            Book, pk=self.kwargs["pk"], owner=self.request.user
        )
        context["is_translation"] = True
        return context

    def form_valid(self, form):
        original_book = get_object_or_404(
            Book, pk=self.kwargs["pk"], owner=self.request.user
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
class ChapterTranslationView(LoginRequiredMixin, View):
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

            # Create changelog entry for the translation
            self._create_changelog_entry(
                original_chapter,
                translated_chapter,
                "translation",
                "in_progress",
                f"AI translation initiated from {original_chapter.get_effective_language().name if original_chapter.get_effective_language() else 'Unknown'} to {target_language.name}",
                request.user,
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

    def _create_changelog_entry(
        self, original_chapter, translated_chapter, change_type, status, notes, user
    ):
        """Helper method to create changelog entries"""
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            return ChangeLog.objects.create(
                content_type=content_type,
                original_object_id=original_chapter.id,
                changed_object_id=translated_chapter.id,
                user=user,
                change_type=change_type,
                status=status,
                notes=notes,
            )
        except Exception as e:
            logger.error(f"Failed to create changelog entry: {str(e)}")
            return None

    def _retry_translation(self, translated_chapter, request):
        """Helper method to retry a failed translation"""
        try:
            # Update chapter status back to translating
            translated_chapter.status = "translating"
            translated_chapter.save()

            # Create changelog entry for retry
            self._create_changelog_entry(
                translated_chapter.original_chapter,
                translated_chapter,
                "translation",
                "in_progress",
                f"Translation retry initiated for {translated_chapter.language.name if translated_chapter.language else 'Unknown'}",
                request.user,
            )

            # Start the AI translation task again
            task = translate_chapter_async.delay(
                translated_chapter.id, translated_chapter.language.code
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Translation retry started for {translated_chapter.language.name}!",
                    "translated_chapter_id": translated_chapter.id,
                    "task_id": task.id,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    def _log_manual_edit(self, chapter, request, edit_type="manual_edit"):
        """Helper method to log manual edits to translated content"""
        try:
            if chapter.original_chapter:
                # This is a translation that was manually edited
                self._create_changelog_entry(
                    chapter.original_chapter,
                    chapter,
                    "edit",
                    "completed",
                    f"Manual {edit_type} applied to {chapter.language.name if chapter.language else 'Unknown'} translation",
                    request.user,
                )
        except Exception as e:
            logger.error(f"Failed to log manual edit: {str(e)}")

    def _get_translation_history(self, chapter):
        """Helper method to get translation history for a chapter"""
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            if chapter.original_chapter:
                # Get changelog entries for this translation
                return ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.original_chapter.id,
                    changed_object_id=chapter.id,
                ).order_by("-created_at")
            else:
                # Get changelog entries for translations of this chapter
                return ChangeLog.objects.filter(
                    content_type=content_type, original_object_id=chapter.id
                ).order_by("-created_at")
        except Exception as e:
            logger.error(f"Failed to get translation history: {str(e)}")
            return ChangeLog.objects.none()


@method_decorator(csrf_exempt, name="dispatch")
class ChapterChangelogView(LoginRequiredMixin, View):
    """View for displaying changelog history for a chapter"""

    def get(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get("pk")
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__owner=request.user
            )

            # Check if this is an AJAX request (multiple ways to detect)
            is_ajax = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest" or
                request.headers.get("Accept") == "application/json" or
                request.GET.get("format") == "json"
            )
            
            if is_ajax:
                logger.info(f"AJAX request detected for chapter {chapter_id}")
                return self._get_changelog_json(chapter)

            # Regular request - render template
            logger.info(f"Regular request for chapter {chapter_id} changelog")
            return self._render_changelog_template(chapter)

        except Exception as e:
            logger.error(f"Error in ChapterChangelogView.get: {str(e)}")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            else:
                messages.error(request, f"Failed to load changelog: {str(e)}")
                return redirect("books:chapter_detail", pk=chapter_id)

    def _get_changelog_json(self, chapter):
        """Return changelog data as JSON for AJAX requests"""
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            
            # Get all changelog entries related to this chapter
            changelog_entries = []
            
            # Case 1: If this is a translation, get entries for this specific translation
            if chapter.original_chapter:
                entries = ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.original_chapter.id,
                    changed_object_id=chapter.id,
                ).order_by("-created_at")
                changelog_entries.extend(entries)
                
                # Also get any entries where this chapter is the original (in case it has its own translations)
                entries_as_original = ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.id,
                ).order_by("-created_at")
                changelog_entries.extend(entries_as_original)
            
            # Case 2: If this is an original chapter, get all translations and edits
            else:
                # Get entries where this chapter is the original
                entries = ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.id,
                ).order_by("-created_at")
                changelog_entries.extend(entries)
                
                # Also get entries where this chapter is the changed object (in case it was created as a translation)
                entries_as_changed = ChangeLog.objects.filter(
                    content_type=content_type,
                    changed_object_id=chapter.id,
                ).order_by("-created_at")
                changelog_entries.extend(entries_as_changed)
            
            # Remove duplicates and sort by created_at
            seen_ids = set()
            unique_entries = []
            for entry in changelog_entries:
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    unique_entries.append(entry)
            
            # Sort by created_at descending
            unique_entries.sort(key=lambda x: x.created_at, reverse=True)
            
            # Format the changelog data
            formatted_entries = []
            for entry in unique_entries:
                entry_data = {
                    "id": entry.id,
                    "change_type": entry.get_change_type_display(),
                    "status": entry.status,
                    "notes": entry.notes,
                    "user": entry.user.username if entry.user else "System",
                    "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "version": entry.version,
                }
                
                # Add diff information for edit entries (manual corrections)
                if entry.change_type == "edit" and entry.status == "completed":
                    try:
                        # For edit entries, we'll use the stored diff if available
                        if entry.diff:
                            entry_data["diff_info"] = {
                                "has_diff": True,
                                "diff_content": entry.diff,
                                "edit_type": "manual_correction",
                                "chapter_id": entry.changed_object_id,
                            }
                        else:
                            entry_data["diff_info"] = {
                                "has_diff": False,
                                "note": "No diff available for this edit"
                            }
                    except Exception as e:
                        logger.error(f"Error processing diff for edit entry {entry.id}: {str(e)}")
                        entry_data["diff_info"] = {
                            "has_diff": False,
                            "error": str(e)
                        }
                else:
                    entry_data["diff_info"] = {"has_diff": False}
                
                formatted_entries.append(entry_data)
            
            return JsonResponse(
                {
                    "success": True,
                    "chapter_id": chapter.id,
                    "chapter_title": chapter.title,
                    "changelog_entries": formatted_entries,
                    "total_entries": len(formatted_entries),
                    "debug_info": self._debug_changelog_data(chapter)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in _get_changelog_json: {str(e)}")
            return JsonResponse(
                {
                    "success": False, 
                    "error": str(e),
                    "debug_info": self._debug_changelog_data(chapter)
                }
            )

    def _render_changelog_template(self, chapter):
        """Render the changelog template"""
        from django.shortcuts import render

        return render(
            self.request,
            "books/chapter/changelog.html",
            {
                "chapter": chapter,
            },
        )

    def _debug_changelog_data(self, chapter):
        """Debug method to check changelog data directly"""
        try:
            content_type = ContentType.objects.get_for_model(Chapter)
            
            # Get basic info
            debug_info = {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "is_translation": chapter.original_chapter is not None,
                "original_chapter_id": chapter.original_chapter.id if chapter.original_chapter else None,
                "content_type_id": content_type.id,
            }
            
            # Get all changelog entries for this content type
            all_entries = ChangeLog.objects.filter(content_type=content_type)
            debug_info["total_entries_for_model"] = all_entries.count()
            
            # Get entries where this chapter is involved
            original_entries = ChangeLog.objects.filter(
                content_type=content_type,
                original_object_id=chapter.id
            )
            changed_entries = ChangeLog.objects.filter(
                content_type=content_type,
                changed_object_id=chapter.id
            )
            
            debug_info["entries_as_original"] = original_entries.count()
            debug_info["entries_as_changed"] = changed_entries.count()
            
            # Version statistics
            if changed_entries.exists():
                max_version = changed_entries.aggregate(max_version=models.Max('version'))['max_version']
                debug_info["max_version"] = max_version or 0
                debug_info["version_range"] = f"1 - {max_version}"
            else:
                debug_info["max_version"] = 0
                debug_info["version_range"] = "No versions"
            
            # If translation, get entries for the original chapter
            if chapter.original_chapter:
                translation_entries = ChangeLog.objects.filter(
                    content_type=content_type,
                    original_object_id=chapter.original_chapter.id,
                    changed_object_id=chapter.id
                )
                debug_info["translation_entries"] = translation_entries.count()
            
            return debug_info
            
        except Exception as e:
            return {"error": str(e)}

    def _generate_diff(self, original_text, changed_text, context_lines=3):
        """Generate a diff between two text versions"""
        try:
            # Split texts into lines
            original_lines = original_text.splitlines(keepends=True)
            changed_lines = changed_text.splitlines(keepends=True)
            
            # Generate diff
            diff = difflib.unified_diff(
                original_lines,
                changed_lines,
                fromfile='Before',
                tofile='After',
                lineterm='',
                n=context_lines
            )
            
            return '\n'.join(diff)
        except Exception as e:
            logger.error(f"Error generating diff: {str(e)}")
            return f"Error generating diff: {str(e)}"

    def _get_chapter_version_content(self, chapter_id, version_info=None):
        """Get content for a specific version of a chapter"""
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            
            # For now, we'll return the current content
            # In a more advanced implementation, you might want to store version history
            content = {
                'title': chapter.title,
                'content': chapter.content,
                'abstract': chapter.abstract or '',
                'key_terms': chapter.key_terms or [],
                'language': chapter.language.name if chapter.language else 'Unknown',
                'version_info': version_info or 'Current version'
            }
            
            return content
        except Chapter.DoesNotExist:
            return None

    def _get_diff_between_chapters(self, original_chapter_id, translated_chapter_id):
        """Get diff between two specific chapters"""
        try:
            original_chapter = Chapter.objects.get(id=original_chapter_id)
            translated_chapter = Chapter.objects.get(id=translated_chapter_id)
            
            # Verify user has access to both chapters
            if (original_chapter.book.owner != self.request.user or 
                translated_chapter.book.owner != self.request.user):
                return JsonResponse({"success": False, "error": "Access denied"})
            
            # Generate diffs
            content_diff = self._generate_diff(
                original_chapter.content,
                translated_chapter.content,
                context_lines=3
            )
            
            title_diff = self._generate_diff(
                original_chapter.title,
                translated_chapter.title,
                context_lines=1
            )
            
            abstract_diff = ""
            if original_chapter.abstract and translated_chapter.abstract:
                abstract_diff = self._generate_diff(
                    original_chapter.abstract,
                    translated_chapter.abstract,
                    context_lines=2
                )
            
            return JsonResponse({
                "success": True,
                "original_chapter": {
                    "id": original_chapter.id,
                    "title": original_chapter.title,
                    "language": original_chapter.get_effective_language().name if original_chapter.get_effective_language() else "Unknown",
                },
                "translated_chapter": {
                    "id": translated_chapter.id,
                    "title": translated_chapter.title,
                    "language": translated_chapter.language.name if translated_chapter.language else "Unknown",
                },
                "diffs": {
                    "title": title_diff,
                    "content": content_diff,
                    "abstract": abstract_diff,
                }
            })
            
        except Chapter.DoesNotExist:
            return JsonResponse({"success": False, "error": "Chapter not found"})
        except Exception as e:
            logger.error(f"Error getting diff between chapters: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})


@method_decorator(csrf_exempt, name="dispatch")
class ChapterDiffView(LoginRequiredMixin, View):
    """View for getting diff between different versions of a chapter (for edit tracking)"""

    def get(self, request, *args, **kwargs):
        try:
            chapter_id = request.GET.get("chapter_id")
            version1_id = request.GET.get("version1_id")
            version2_id = request.GET.get("version2_id")
            
            if not chapter_id:
                return JsonResponse({
                    "success": False, 
                    "error": "chapter_id parameter is required"
                })
            
            # Get the chapter
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__owner=request.user
            )
            
            # For now, we'll compare with the current version
            # In a more advanced implementation, you might want to store version history
            current_content = chapter.content
            current_title = chapter.title
            
            # If specific versions are provided, compare them
            if version1_id and version2_id:
                try:
                    version1 = Chapter.objects.get(pk=version1_id, book__owner=request.user)
                    version2 = Chapter.objects.get(pk=version2_id, book__owner=request.user)
                    
                    content_diff = self._generate_diff(
                        version1.content,
                        version2.content,
                        context_lines=3
                    )
                    
                    title_diff = self._generate_diff(
                        version1.title,
                        version2.title,
                        context_lines=1
                    )
                    
                    return JsonResponse({
                        "success": True,
                        "version1": {
                            "id": version1.id,
                            "title": version1.title,
                            "updated_at": version1.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        "version2": {
                            "id": version2.id,
                            "title": version2.title,
                            "updated_at": version2.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        "diffs": {
                            "title": title_diff,
                            "content": content_diff,
                        }
                    })
                    
                except Chapter.DoesNotExist:
                    return JsonResponse({"success": False, "error": "One or both versions not found"})
            
            # Default: compare with a hypothetical previous version
            # This would be useful when you implement version history
            return JsonResponse({
                "success": True,
                "message": "Version comparison not implemented yet. Use changelog to view edit history.",
                "current_chapter": {
                    "id": chapter.id,
                    "title": chapter.title,
                    "updated_at": chapter.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            })
            
        except Exception as e:
            logger.error(f"Error in ChapterDiffView: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})

    def _generate_diff(self, original_text, changed_text, context_lines=3):
        """Generate a diff between two text versions"""
        try:
            # Split texts into lines
            original_lines = original_text.splitlines(keepends=True)
            changed_lines = changed_text.splitlines(keepends=True)
            
            # Generate diff
            diff = difflib.unified_diff(
                original_lines,
                changed_lines,
                fromfile='Before',
                tofile='After',
                lineterm='',
                n=context_lines
            )
            
            return '\n'.join(diff)
        except Exception as e:
            logger.error(f"Error generating diff: {str(e)}")
            return f"Error generating diff: {str(e)}"
