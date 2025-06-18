from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, DetailView
from django.utils.html import escape
from difflib import HtmlDiff

from books.models import Book, Chapter
from .models import Translation, EditHistory
from .forms import TranslationForm


class TranslationDashboardView(LoginRequiredMixin, ListView):
    model = Book
    template_name = "translations/dashboard.html"
    context_object_name = "books"

    def get_queryset(self):
        return Book.objects.filter(status__in=["translating", "proofreading"])


class ChapterTranslationView(LoginRequiredMixin, DetailView):
    model = Chapter
    template_name = "translations/chapter_translate.html"
    context_object_name = "chapter"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chapter = self.get_object()

        # Get translations for both languages
        en_translation = chapter.get_translation("en")
        de_translation = chapter.get_translation("de")

        context.update(
            {
                "en_translation": en_translation,
                "de_translation": de_translation,
                "form": TranslationForm(),
                "previous_chapter": chapter.book.chapters.filter(
                    chapter_number=chapter.chapter_number - 1
                ).first(),
                "next_chapter": chapter.book.chapters.filter(
                    chapter_number=chapter.chapter_number + 1
                ).first(),
            }
        )
        return context


@login_required
def save_translation(request, chapter_id, language):
    chapter = get_object_or_404(Chapter, id=chapter_id)
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Get current translation or create new one
    translation = chapter.get_translation(language)
    new_text = request.POST.get("translated_text", "").strip()

    if translation:
        # Create edit history before updating
        if translation.translated_text != new_text:
            diff_maker = HtmlDiff()
            diff_html = diff_maker.make_table(
                translation.translated_text.splitlines(),
                new_text.splitlines(),
                fromdesc="Previous Version",
                todesc="New Version",
            )

            EditHistory.objects.create(
                translation=translation,
                old_text=translation.translated_text,
                new_text=new_text,
                diff_html=diff_html,
                edited_by=request.user,
                comment=request.POST.get("comment", ""),
            )

            # Update version and text
            translation.version += 1
            translation.translated_text = new_text
            translation.save()
    else:
        # Create new translation
        translation = Translation.objects.create(
            chapter=chapter,
            target_language=language,
            translated_text=new_text,
            created_by=request.user,
            is_ai_generated=False,
        )

    return JsonResponse({"success": True, "version": translation.version})


@login_required
def translation_history(request, translation_id):
    translation = get_object_or_404(Translation, id=translation_id)
    history = translation.edit_history.all().order_by("-edited_at")

    return render(
        request,
        "translations/history.html",
        {"translation": translation, "history": history},
    )


@login_required
def compare_versions(request, history_id):
    edit = get_object_or_404(EditHistory, id=history_id)
    return render(
        request,
        "translations/compare.html",
        {"edit": edit, "diff_html": edit.diff_html},
    )
