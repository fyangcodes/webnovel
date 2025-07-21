from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy

from ..models import Book, BookMaster, Language
from ..forms import BookForm, BookFileForm
from ..tasks import process_bookfile_async


# Book CRUD Views
class BookCreateView(LoginRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book/form.html"

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.kwargs.get("bookmaster_pk")}
        )

    def form_valid(self, form):
        form.instance.owner = self.request.user
        # Set the master field from the URL kwarg
        bookmaster_pk = self.kwargs.get("bookmaster_pk")
        if bookmaster_pk:
            bookmaster = get_object_or_404(BookMaster, pk=bookmaster_pk)
            form.instance.master = bookmaster
            # Determine the language: GET/POST param or default to original
            language_id = self.request.GET.get("language") or self.request.POST.get(
                "language"
            )
            if language_id:
                try:
                    requested_language = Language.objects.get(pk=language_id)
                except Language.DoesNotExist:
                    messages.error(
                        self.request,
                        f"Language '{requested_language}' does not exist. Using original language.",
                    )
                    requested_language = bookmaster.original_language
            else:
                requested_language = bookmaster.original_language
            form.instance.language = requested_language
            # Check if a book in the requested language already exists for this master
            if Book.objects.filter(
                master=bookmaster, language=requested_language
            ).exists():
                messages.warning(
                    self.request,
                    f"A book in {requested_language.name} already exists for this work.",
                )
                return redirect("books:bookmaster_detail", pk=bookmaster_pk)
        return super().form_valid(form)


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = "books/book/detail.html"
    context_object_name = "book"

    def get_queryset(self):
        return Book.objects.filter(master__owner=self.request.user)

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

    def get_queryset(self):
        return Book.objects.filter(master__owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        book = self.get_object()
        # Remove uploaded_file reference as it's not in the new model
        # if book.uploaded_file:
        #     book.uploaded_file.delete()
        messages.success(request, "Book deleted successfully.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy(
            "books:bookmaster_detail", kwargs={"pk": self.object.master.pk}
        )

class BookFileUploadView(LoginRequiredMixin, FormView):
    form_class = BookFileForm
    template_name = "books/bookfile/upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["book"] = get_object_or_404(
            Book, pk=self.kwargs["pk"], master__owner=self.request.user
        )
        return context

    def form_valid(self, form):
        book = get_object_or_404(
            Book, pk=self.kwargs["pk"], master__owner=self.request.user
        )
        book_file = form.save(commit=False)
        book_file.book = book
        book_file.owner = self.request.user
        book_file.save()
        # Trigger async processing with user ID
        process_bookfile_async.delay(book_file.id, user_id=self.request.user.id)
        return redirect("books:book_detail", pk=book.pk)