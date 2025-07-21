from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    DeleteView,
    UpdateView,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
import difflib
import logging
from django.contrib.auth import get_user_model

from ..models import Book, Chapter, Language
from ..forms import ChapterForm
from ..choices import ChapterStatus

# Chapter CRUD Views
class ChapterCreateView(LoginRequiredMixin, CreateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = get_object_or_404(
            Book, pk=self.kwargs["book_pk"], bookmaster__owner=self.request.user
        )
        return context

    def form_valid(self, form):
        book = get_object_or_404(Book, pk=self.kwargs["book_pk"], bookmaster__owner=self.request.user)
        form.instance.book = book

        # Set user for raw content saving
        form.user = self.request.user

        response = super().form_valid(form)
        messages.success(
            self.request, f"Chapter '{form.instance.title}' created successfully!"
        )
        return response

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.kwargs["book_pk"]})


class ChapterDetailView(LoginRequiredMixin, DetailView):
    model = Chapter
    template_name = "books/chapter/detail.html"
    context_object_name = "chapter"

    def get_queryset(self):
        user = self.request.user
        User = get_user_model()
        if not user.is_authenticated or not isinstance(user, User):
            return Chapter.objects.none()
        return Chapter.objects.filter(book__bookmaster__owner=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Removed translation logic as translations are now managed in chaptermaster
        return context


class ChapterUpdateView(LoginRequiredMixin, UpdateView):
    model = Chapter
    form_class = ChapterForm
    template_name = "books/chapter/form.html"
    context_object_name = "chapter"

    def get_queryset(self):
        return Chapter.objects.filter(book__bookmaster__owner=self.request.user)

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
                original_content = original_chapter.get_content('raw')  # Use raw content
                original_title = original_chapter.title
            except Chapter.DoesNotExist:
                pass

        # Set user for raw content saving
        form.user = self.request.user

        response = super().form_valid(form)

        # Create changelog entry for manual edits
        try:
            content_type = ContentType.objects.get_for_model(Chapter)

            # Check for any changes (title or content)
            title_changed = original_title and original_title != chapter.title
            content_changed = (
                original_content
                and original_content != form.cleaned_data.get("content", "")
            )

            # Generate diff if there are any changes
            diff_content = ""
            if title_changed or content_changed:
                title_diff = ""
                content_diff = ""

                if title_changed:
                    title_diff = self._generate_diff(
                        original_title, chapter.title, context_lines=1
                    )

                if content_changed:
                    content_diff = self._generate_diff(
                        original_content,
                        form.cleaned_data.get("content", ""),
                        context_lines=3,
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
                    original_object_id=(
                        chapter.original_chapter.id if is_translation else chapter.id
                    ),
                    changed_object_id=chapter.id,
                    user=self.request.user,
                    change_type="edit",
                    status="completed",
                    notes=notes,
                    diff=diff_content,
                )
        except Exception as e:
            logger.error(f"Failed to create changelog entry for manual edit: {str(e)}")

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
                fromfile="Before",
                tofile="After",
                lineterm="",
                n=context_lines,
            )

            return "\n".join(diff)
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
                "title": chapter.title,
                "content": chapter.get_content('raw'),
                "abstract": chapter.abstract or "",
                "key_terms": chapter.key_terms or [],
                "language": chapter.language.name if chapter.language else "Unknown",
                "version_info": version_info or "Current version",
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
            if (
                original_chapter.book.owner != self.request.user
                or translated_chapter.book.owner != self.request.user
            ):
                return JsonResponse({"success": False, "error": "Access denied"})

            # Generate diffs
            content_diff = self._generate_diff(
                original_chapter.get_content('raw'),
                translated_chapter.get_content('raw'),
                context_lines=3,
            )

            title_diff = self._generate_diff(
                original_chapter.title, translated_chapter.title, context_lines=1
            )

            abstract_diff = ""
            if original_chapter.abstract and translated_chapter.abstract:
                abstract_diff = self._generate_diff(
                    original_chapter.abstract,
                    translated_chapter.abstract,
                    context_lines=2,
                )

            return JsonResponse(
                {
                    "success": True,
                    "original_chapter": {
                        "id": original_chapter.id,
                        "title": original_chapter.title,
                        "language": (
                            original_chapter.get_effective_language().name
                            if original_chapter.get_effective_language()
                            else "Unknown"
                        ),
                    },
                    "translated_chapter": {
                        "id": translated_chapter.id,
                        "title": translated_chapter.title,
                        "language": (
                            translated_chapter.language.name
                            if translated_chapter.language
                            else "Unknown"
                        ),
                    },
                    "diffs": {
                        "title": title_diff,
                        "content": content_diff,
                        "abstract": abstract_diff,
                    },
                }
            )

        except Chapter.DoesNotExist:
            return JsonResponse({"success": False, "error": "Chapter not found"})
        except Exception as e:
            logger.error(f"Error getting diff between chapters: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})

class ChapterAnalyzeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        chapter_id = kwargs.get("pk")
        chapter = get_object_or_404(Chapter, pk=chapter_id, book__bookmaster__owner=request.user)
        return JsonResponse({"success": True, "chapter": chapter.id})


class ChapterDeleteView(LoginRequiredMixin, DeleteView):
    model = Chapter
    template_name = "books/chapter/confirm_delete.html"

    def get_queryset(self):
        return Chapter.objects.filter(book__bookmaster__owner=self.request.user)

    def get_success_url(self):
        return reverse_lazy("books:book_detail", kwargs={"pk": self.object.book.pk})

@method_decorator(csrf_exempt, name="dispatch")
class ChapterDiffView(LoginRequiredMixin, View):
    """View for getting diff between different versions of a chapter (for edit tracking)"""

    def get(self, request, *args, **kwargs):
        try:
            chapter_id = request.GET.get("chapter_id")
            version1_id = request.GET.get("version1_id")
            version2_id = request.GET.get("version2_id")

            if not chapter_id:
                return JsonResponse(
                    {"success": False, "error": "chapter_id parameter is required"}
                )

            # Get the chapter
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__bookmaster__owner=request.user
            )

            # For now, we'll compare with the current version
            # In a more advanced implementation, you might want to store version history
            current_content = chapter.get_content('raw')
            current_title = chapter.title

            # If specific versions are provided, compare them
            if version1_id and version2_id:
                try:
                    version1 = Chapter.objects.get(
                        pk=version1_id, book__bookmaster__owner=request.user
                    )
                    version2 = Chapter.objects.get(
                        pk=version2_id, book__bookmaster__owner=request.user
                    )

                    content_diff = self._generate_diff(
                        version1.get_content('raw'),
                        version2.get_content('raw'),
                        context_lines=3,
                    )

                    title_diff = self._generate_diff(
                        version1.title, version2.title, context_lines=1
                    )

                    return JsonResponse(
                        {
                            "success": True,
                            "version1": {
                                "id": version1.id,
                                "title": version1.title,
                                "updated_at": version1.updated_at.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            },
                            "version2": {
                                "id": version2.id,
                                "title": version2.title,
                                "updated_at": version2.updated_at.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            },
                            "diffs": {
                                "title": title_diff,
                                "content": content_diff,
                            },
                        }
                    )

                except Chapter.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "error": "One or both versions not found"}
                    )

            # Default: compare with a hypothetical previous version
            # This would be useful when you implement version history
            return JsonResponse(
                {
                    "success": True,
                    "message": "Version comparison not implemented yet. Use changelog to view edit history.",
                    "current_chapter": {
                        "id": chapter.id,
                        "title": chapter.title,
                        "updated_at": chapter.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error in ChapterDiffView: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})


@method_decorator(csrf_exempt, name="dispatch")
class ChapterVersionCompareView(LoginRequiredMixin, View):
    """View for comparing different versions of a chapter side by side"""

    def get(self, request, *args, **kwargs):
        try:
            chapter_id = kwargs.get("pk")
            version1_id = request.GET.get("version1")
            version2_id = request.GET.get("version2")

            # Get the main chapter
            chapter = get_object_or_404(
                Chapter, pk=chapter_id, book__bookmaster__owner=request.user
            )

            # Check if this is an AJAX request
            is_ajax = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or request.headers.get("Accept") == "application/json"
                or request.GET.get("format") == "json"
            )

            if is_ajax:
                return self._get_comparison_json(chapter, version1_id, version2_id)
            else:
                return self._render_comparison_template(
                    chapter, version1_id, version2_id
                )

        except Exception as e:
            logger.error(f"Error in ChapterVersionCompareView.get: {str(e)}")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            else:
                messages.error(request, f"Failed to load version comparison: {str(e)}")
                return redirect("books:chapter_detail", pk=chapter_id)

    def _get_comparison_json(self, chapter, version1_id, version2_id):
        """Return comparison data as JSON for AJAX requests"""
        try:
            # Get available versions for this chapter
            available_versions = self._get_available_versions(chapter)

            if not available_versions:
                return JsonResponse(
                    {"success": False, "error": "No versions available for comparison"}
                )

            # Determine which versions to compare
            version1, version2 = self._get_comparison_versions(
                chapter, version1_id, version2_id, available_versions
            )

            if not version1 or not version2:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Could not determine versions to compare. Available versions: "
                        + str(len(available_versions)),
                    }
                )

            # Get the content for both versions
            try:
                version1_content = self._get_version_content(version1)
                version2_content = self._get_version_content(version2)
            except Exception as e:
                logger.error(f"Error getting version content: {str(e)}")
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Error loading version content: {str(e)}",
                    }
                )

            # Generate diffs
            try:
                title_diff = self._generate_diff(
                    version1_content["title"],
                    version2_content["title"],
                    context_lines=1,
                )

                content_diff = self._generate_diff(
                    version1_content["content"],
                    version2_content["content"],
                    context_lines=3,
                )
            except Exception as e:
                logger.error(f"Error generating diffs: {str(e)}")
                title_diff = "Error generating title diff"
                content_diff = "Error generating content diff"

            # Prepare version info for response
            def prepare_version_info(version_obj, content):
                try:
                    if version_obj["type"] == "history":
                        version_info = version_obj["version_info"]
                        return {
                            "id": version_info["id"],
                            "title": content["title"],
                            "content": content["content"],
                            "language": content["language"],
                            "updated_at": version_info["updated_at"],
                            "is_original": False,
                            "version_type": "history",
                            "version_number": version_info["version_number"],
                            "change_notes": version_info["change_notes"],
                            "user": version_info["user"],
                            "type": version_info["type"],
                        }
                    else:
                        chapter = version_obj["chapter"]
                        return {
                            "id": chapter.id,
                            "title": content["title"],
                            "content": content["content"],
                            "language": content["language"],
                            "updated_at": chapter.updated_at.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "is_original": chapter.original_chapter is None,
                            "version_type": "translation",
                            "type": (
                                "Original"
                                if chapter.original_chapter is None
                                else "Translation"
                            ),
                        }
                except Exception as e:
                    logger.error(f"Error preparing version info: {str(e)}")
                    return {
                        "id": "error",
                        "title": "Error loading version",
                        "content": "Error loading content",
                        "language": "Unknown",
                        "updated_at": "Unknown",
                        "is_original": False,
                        "version_type": "error",
                        "type": "Error",
                    }

            return JsonResponse(
                {
                    "success": True,
                    "chapter_id": chapter.id,
                    "chapter_title": chapter.title,
                    "available_versions": available_versions,
                    "comparison": {
                        "version1": prepare_version_info(version1, version1_content),
                        "version2": prepare_version_info(version2, version2_content),
                        "diffs": {
                            "title": title_diff,
                            "content": content_diff,
                        },
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error in _get_comparison_json: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)})

    def _render_comparison_template(self, chapter, version1_id, version2_id):
        """Render the comparison template"""
        from django.shortcuts import render

        # Get available versions for the template
        available_versions = self._get_available_versions(chapter)

        return render(
            self.request,
            "books/chapter/version_compare.html",
            {
                "chapter": chapter,
                "available_versions": available_versions,
                "version1_id": version1_id,
                "version2_id": version2_id,
            },
        )

    def _get_available_versions(self, chapter):
        """Get all available versions of a chapter (original + translations + version history)"""
        try:
            versions = []
            content_type = ContentType.objects.get_for_model(Chapter)

            # Add the original chapter if this is a translation
            if chapter.original_chapter:
                original = chapter.original_chapter
                versions.append(
                    {
                        "id": original.id,
                        "title": original.title,
                        "language": (
                            original.get_effective_language().name
                            if original.get_effective_language()
                            else "Unknown"
                        ),
                        "updated_at": original.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_original": True,
                        "type": "Original",
                        "version_type": "translation",
                    }
                )

            # Add this chapter
            versions.append(
                {
                    "id": chapter.id,
                    "title": chapter.title,
                    "language": (
                        chapter.get_effective_language().name
                        if chapter.get_effective_language()
                        else "Unknown"
                    ),
                    "updated_at": chapter.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_original": chapter.original_chapter is None,
                    "type": (
                        "Original"
                        if chapter.original_chapter is None
                        else "Translation"
                    ),
                    "version_type": "translation",
                }
            )

            # Add all translations of this chapter
            if chapter.original_chapter is None:  # This is an original chapter
                translations = chapter.translations.all()
                for translation in translations:
                    versions.append(
                        {
                            "id": translation.id,
                            "title": translation.title,
                            "language": (
                                translation.language.name
                                if translation.language
                                else "Unknown"
                            ),
                            "updated_at": translation.updated_at.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "is_original": False,
                            "type": "Translation",
                            "version_type": "translation",
                        }
                    )

            # Add version history from changelog entries
            version_history = self._get_version_history(chapter, content_type)
            versions.extend(version_history)

            # Sort by updated_at descending
            versions.sort(key=lambda x: x["updated_at"], reverse=True)

            return versions

        except Exception as e:
            logger.error(f"Error getting available versions: {str(e)}")
            return []

    def _get_version_history(self, chapter, content_type):
        """Get version history from changelog entries for a specific chapter"""
        try:
            version_history = []

            # Get changelog entries where this chapter is the changed object
            changelog_entries = ChangeLog.objects.filter(
                content_type=content_type,
                changed_object_id=chapter.id,
                change_type="edit",
                status="completed",
            ).order_by("-created_at")

            for entry in changelog_entries:
                # Create a version entry for each changelog entry
                version_history.append(
                    {
                        "id": f"version_{entry.version}",
                        "title": f"{chapter.title} (v{entry.version})",
                        "language": (
                            chapter.get_effective_language().name
                            if chapter.get_effective_language()
                            else "Unknown"
                        ),
                        "updated_at": entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_original": False,
                        "type": f"Version {entry.version}",
                        "version_type": "history",
                        "changelog_entry_id": entry.id,
                        "changed_object_id": entry.changed_object_id,
                        "version_number": entry.version,
                        "change_notes": entry.notes,
                        "user": entry.user.username if entry.user else "System",
                    }
                )

            return version_history

        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return []

    def _get_comparison_versions(
        self, chapter, version1_id, version2_id, available_versions
    ):
        """Get the two versions to compare"""
        try:
            version1 = None
            version2 = None

            # If specific versions are requested, use them
            if version1_id and version2_id:
                # Check if these are version history entries
                if version1_id.startswith("version_"):
                    version1 = self._get_version_from_history(
                        chapter, version1_id, available_versions
                    )
                else:
                    try:
                        chapter_obj = Chapter.objects.get(
                            pk=version1_id, book__bookmaster__owner=self.request.user
                        )
                        version1 = {"type": "chapter", "chapter": chapter_obj}
                    except Chapter.DoesNotExist:
                        pass

                if version2_id.startswith("version_"):
                    version2 = self._get_version_from_history(
                        chapter, version2_id, available_versions
                    )
                else:
                    try:
                        chapter_obj = Chapter.objects.get(
                            pk=version2_id, book__bookmaster__owner=self.request.user
                        )
                        version2 = {"type": "chapter", "chapter": chapter_obj}
                    except Chapter.DoesNotExist:
                        pass

            # If not specified or not found, use sensible defaults
            if not version1 or not version2:
                if available_versions:
                    # Use the first two available versions
                    if len(available_versions) >= 2:
                        version1 = self._get_version_from_available(
                            available_versions[0]
                        )
                        version2 = self._get_version_from_available(
                            available_versions[1]
                        )
                    else:
                        # Only one version available, compare with itself
                        version1 = self._get_version_from_available(
                            available_versions[0]
                        )
                        version2 = version1

            return version1, version2

        except Exception as e:
            logger.error(f"Error getting comparison versions: {str(e)}")
            return None, None

    def _get_version_from_available(self, version_info):
        """Get version object from available version info"""
        try:
            if version_info.get("version_type") == "history":
                # This is a version history entry
                changed_object_id = version_info["changed_object_id"]
                return {
                    "type": "history",
                    "version_info": version_info,
                    "chapter": Chapter.objects.get(pk=changed_object_id),
                }
            else:
                # This is a regular chapter
                return {
                    "type": "chapter",
                    "chapter": Chapter.objects.get(pk=version_info["id"]),
                }
        except Exception as e:
            logger.error(f"Error getting version from available: {str(e)}")
            return None

    def _get_version_from_history(self, chapter, version_id, available_versions):
        """Get version from history based on version ID"""
        try:
            # Find the version info in available versions
            for version_info in available_versions:
                if version_info["id"] == version_id:
                    return self._get_version_from_available(version_info)
            return None
        except Exception as e:
            logger.error(f"Error getting version from history: {str(e)}")
            return None

    def _get_version_content(self, version_obj):
        """Get the content for a specific version of a chapter"""
        try:
            if version_obj["type"] == "history":
                # This is a version history entry - we need to reconstruct the content
                return self._reconstruct_version_content(version_obj)
            else:
                # This is a regular chapter
                chapter = version_obj["chapter"]
                return {
                    "title": chapter.title,
                    "content": chapter.get_content('raw'),
                    "abstract": chapter.abstract or "",
                    "key_terms": chapter.key_terms or [],
                    "language": (
                        chapter.get_effective_language().name
                        if chapter.get_effective_language()
                        else "Unknown"
                    ),
                }
        except Exception as e:
            logger.error(f"Error getting version content: {str(e)}")
            return {
                "title": "Error loading content",
                "content": "Error loading content",
                "abstract": "",
                "key_terms": [],
                "language": "Unknown",
            }

    def _reconstruct_version_content(self, version_obj):
        """Reconstruct content for a specific version from changelog history"""
        try:
            chapter = version_obj["chapter"]
            version_info = version_obj["version_info"]

            # For now, we'll return the current content
            # In a more advanced implementation, you might want to store the actual content
            # at each version or reconstruct it from the diff
            return {
                "title": chapter.title,
                "content": chapter.get_content('raw'),
                "abstract": chapter.abstract or "",
                "key_terms": chapter.key_terms or [],
                "language": (
                    chapter.get_effective_language().name
                    if chapter.get_effective_language()
                    else "Unknown"
                ),
                "version_notes": version_info.get("change_notes", ""),
                "version_user": version_info.get("user", "Unknown"),
                "version_number": version_info.get("version_number", 1),
            }
        except Exception as e:
            logger.error(f"Error reconstructing version content: {str(e)}")
            return {
                "title": "Error reconstructing content",
                "content": "Error reconstructing content",
                "abstract": "",
                "key_terms": [],
                "language": "Unknown",
            }

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
                fromfile="Before",
                tofile="After",
                lineterm="",
                n=context_lines,
            )

            return "\n".join(diff)
        except Exception as e:
            logger.error(f"Error generating diff: {str(e)}")
            return f"Error generating diff: {str(e)}"


@method_decorator(csrf_exempt, name="dispatch")
class TaskStatusView(LoginRequiredMixin, View):
    """View for checking task status via AJAX"""

    def get(self, request, *args, **kwargs):
        try:
            task_id = request.GET.get("task_id")
            task_type = request.GET.get("task_type")  # 'sync' or 'rebuild'

            if not task_id:
                return JsonResponse({"success": False, "error": "Task ID is required"})

            # Import celery result backend
            from celery.result import AsyncResult

            # Get task result
            task_result = AsyncResult(task_id)

            # Get task status
            status = task_result.status

            # Prepare response data
            response_data = {
                "success": True,
                "task_id": task_id,
                "task_type": task_type,
                "status": status,
                "is_pending": status in ["PENDING", "STARTED"],
                "is_success": status == "SUCCESS",
                "is_failure": status in ["FAILURE", "REVOKED"],
                "is_retry": status == "RETRY",
            }

            # Add result data if task is complete
            if status == "SUCCESS":
                result = task_result.result
                if isinstance(result, dict):
                    response_data.update(
                        {
                            "result": result,
                            "message": result.get(
                                "message", "Task completed successfully"
                            ),
                            "chapter_id": result.get("chapter_id"),
                            "added_count": result.get("added_count"),
                            "media_count": result.get("media_count"),
                            "result_count": result.get("result_count"),
                        }
                    )
                else:
                    response_data.update(
                        {"result": result, "message": "Task completed successfully"}
                    )
            elif status == "FAILURE":
                response_data.update(
                    {
                        "error": str(task_result.result),
                        "message": f"Task failed: {str(task_result.result)}",
                    }
                )
            elif status == "RETRY":
                response_data.update(
                    {
                        "message": "Task is being retried",
                        "retry_count": getattr(task_result, "retry_count", 0),
                    }
                )

            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"Error checking task status: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                    "message": f"Error checking task status: {str(e)}",
                }
            )


