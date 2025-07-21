from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from ..models import ChapterMaster, Chapter, Language
from ..forms import ChapterMasterForm

class ChapterMasterCreateView(LoginRequiredMixin, CreateView):
    model = ChapterMaster
    form_class = ChapterMasterForm
    template_name = "books/chaptermaster/form.html"

    def get_success_url(self):
        return reverse_lazy("books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id})

class ChapterMasterDetailView(LoginRequiredMixin, DetailView):
    model = ChapterMaster
    template_name = "books/chaptermaster/detail.html"
    context_object_name = "chaptermaster"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chaptermaster = self.object
        chapters = Chapter.objects.filter(chaptermaster=chaptermaster).select_related('language')
        context['chapters'] = chapters
        return context


class ChapterMasterUpdateView(LoginRequiredMixin, UpdateView):
    model = ChapterMaster
    form_class = ChapterMasterForm
    template_name = "books/chaptermaster/form.html"

    def get_success_url(self):
        return reverse_lazy("books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id})

class ChapterMasterDeleteView(LoginRequiredMixin, DeleteView):
    model = ChapterMaster
    template_name = "books/chaptermaster/confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("books:bookmaster_detail", kwargs={"pk": self.object.bookmaster.id})
