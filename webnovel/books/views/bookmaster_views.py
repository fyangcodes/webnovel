from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    CreateView,
    ListView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy

from ..models import BookMaster
from ..forms import BookMasterForm


class BookMasterCreateView(LoginRequiredMixin, CreateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("books:bookmaster_detail", kwargs={"pk": self.object.pk})


class BookMasterListView(LoginRequiredMixin, ListView):
    model = BookMaster
    template_name = "books/bookmaster/list.html"
    context_object_name = "bookmasters"

    def get_queryset(self):
        return BookMaster.objects.filter(owner=self.request.user)


class BookMasterDetailView(LoginRequiredMixin, DetailView):
    model = BookMaster
    template_name = "books/bookmaster/detail.html"
    context_object_name = "bookmaster"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["books"] = self.object.books.all().order_by("language__name")
        # Add chapter masters
        context["chaptermasters"] = self.object.chaptermasters.all()
        return context


class BookMasterUpdateView(LoginRequiredMixin, UpdateView):
    model = BookMaster
    form_class = BookMasterForm
    template_name = "books/bookmaster/form.html"
    context_object_name = "bookmaster"

    def get_success_url(self):
        return reverse_lazy("books:bookmaster_detail", kwargs={"pk": self.object.pk})


class BookMasterDeleteView(LoginRequiredMixin, DeleteView):
    model = BookMaster
    template_name = "books/bookmaster/confirm_delete.html"
    context_object_name = "bookmaster"
    success_url = reverse_lazy("books:bookmaster_list")
