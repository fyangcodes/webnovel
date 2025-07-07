from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import BookCollaborator, TranslationAssignment
from .forms import (
    BookCollaboratorForm,
    TranslationAssignmentForm,
    TranslationAssignmentFilterForm,
)
from .permissions import (
    get_user_permissions,
    get_books_user_can_access,
    get_translation_assignments_for_user,
    assign_translation_task,
)


class TranslationAssignmentListView(LoginRequiredMixin, ListView):
    """View for listing translation assignments"""

    model = TranslationAssignment
    template_name = "collaboration/translation_assignments.html"
    context_object_name = "assignments"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = get_translation_assignments_for_user(user)

        # Apply filters
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        target_language = self.request.GET.get("target_language")
        if target_language:
            queryset = queryset.filter(target_language_id=target_language)

        is_overdue = self.request.GET.get("is_overdue")
        if is_overdue == "on":
            queryset = queryset.filter(due_date__lt=timezone.now())

        return queryset.order_by("-assigned_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        all_assignments = get_translation_assignments_for_user(user)

        # Calculate statistics
        context.update(
            {
                "filter_form": TranslationAssignmentFilterForm(
                    self.request.GET, user=self.request.user
                ),
                "total_assignments": all_assignments.count(),
                "in_progress_count": all_assignments.filter(
                    status="in_progress"
                ).count(),
                "review_count": all_assignments.filter(status="review").count(),
                "completed_count": all_assignments.filter(
                    status__in=["approved", "rejected"]
                ).count(),
            }
        )
        return context


class TranslationAssignmentDetailView(LoginRequiredMixin, DetailView):
    """View for viewing translation assignment details"""

    model = TranslationAssignment
    template_name = "collaboration/translation_assignment_detail.html"
    context_object_name = "assignment"

    def get_queryset(self):
        user = self.request.user
        return get_translation_assignments_for_user(user)


@login_required
def start_translation_assignment(request, pk):
    """Start working on a translation assignment"""
    assignment = get_object_or_404(
        TranslationAssignment, pk=pk, translator=request.user
    )

    if assignment.status == "assigned":
        assignment.status = "in_progress"
        assignment.started_at = timezone.now()
        assignment.save()
        messages.success(request, "Translation work started!")
    else:
        messages.warning(request, "This assignment cannot be started.")

    return redirect("collaboration:translation_assignment_detail", pk=pk)


@login_required
def submit_translation_assignment(request, pk):
    """Submit a translation assignment for review"""
    assignment = get_object_or_404(
        TranslationAssignment, pk=pk, translator=request.user
    )

    if assignment.status == "in_progress":
        assignment.status = "review"
        assignment.completed_at = timezone.now()
        assignment.save()
        messages.success(request, "Translation submitted for review!")
    else:
        messages.warning(request, "This assignment cannot be submitted.")

    return redirect("collaboration:translation_assignment_detail", pk=pk)


@login_required
def approve_translation_assignment(request, pk):
    """Approve a translation assignment (editors only)"""
    assignment = get_object_or_404(TranslationAssignment, pk=pk)

    if not request.user.role in ["editor", "admin"]:
        messages.error(request, "You need editor permissions to approve translations.")
        return redirect("collaboration:translation_assignment_detail", pk=pk)

    if assignment.status == "review":
        assignment.status = "approved"
        assignment.save()
        messages.success(request, "Translation approved!")
    else:
        messages.warning(request, "This assignment cannot be approved.")

    return redirect("collaboration:translation_assignment_detail", pk=pk)


@login_required
def reject_translation_assignment(request, pk):
    """Reject a translation assignment (editors only)"""
    assignment = get_object_or_404(TranslationAssignment, pk=pk)

    if not request.user.role in ["editor", "admin"]:
        messages.error(request, "You need editor permissions to reject translations.")
        return redirect("collaboration:translation_assignment_detail", pk=pk)

    if assignment.status == "review":
        assignment.status = "rejected"
        assignment.save()
        messages.success(request, "Translation rejected.")
    else:
        messages.warning(request, "This assignment cannot be rejected.")

    return redirect("collaboration:translation_assignment_detail", pk=pk)
