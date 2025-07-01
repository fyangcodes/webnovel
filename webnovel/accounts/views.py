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

from .models import User, BookCollaborator, TranslationAssignment
from .forms import (
    UserProfileForm,
    BookCollaboratorForm,
    TranslationAssignmentForm,
    RoleAssignmentForm,
    UserSearchForm,
    TranslationAssignmentFilterForm,
)
from .mixins import (
    BookPermissionMixin,
    TranslationPermissionMixin,
    EditorPermissionMixin,
    AdminPermissionMixin,
    WriterPermissionMixin,
)
from .permissions import (
    get_user_permissions,
    get_books_user_can_access,
    get_translation_assignments_for_user,
    assign_translation_task,
)


@login_required
def profile_view(request):
    """User profile view"""
    user = request.user

    # Get user's books
    books = get_books_user_can_access(user)

    # Get translation assignments
    translation_assignments = get_translation_assignments_for_user(user)

    # Get collaborations
    collaborations = user.book_collaborations.filter(is_active=True)

    context = {
        "user": user,
        "books": books,
        "translation_assignments": translation_assignments,
        "collaborations": collaborations,
        "permissions": get_user_permissions(user),
    }

    return render(request, "accounts/profile.html", context)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """View for users to update their own profile"""

    model = User
    form_class = UserProfileForm
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)


class UserListView(AdminPermissionMixin, ListView):
    """View for listing users (admin only)"""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.all()

        # Apply search filter
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(pen_name__icontains=search)
            )

        # Apply role filter
        role = self.request.GET.get("role")
        if role:
            queryset = queryset.filter(role=role)

        # Apply verification filter
        is_verified = self.request.GET.get("is_verified")
        if is_verified == "on":
            queryset = queryset.filter(is_verified=True)

        return queryset.order_by("-date_joined")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = UserSearchForm(self.request.GET)
        return context


class UserDetailView(AdminPermissionMixin, DetailView):
    """View for viewing user details (admin only)"""

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "target_user"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()

        context.update(
            {
                "books": get_books_user_can_access(user),
                "translation_assignments": get_translation_assignments_for_user(user),
                "collaborations": user.book_collaborations.filter(is_active=True),
                "permissions": get_user_permissions(user),
            }
        )

        return context


class TranslationAssignmentListView(TranslationPermissionMixin, ListView):
    """View for listing translation assignments"""

    model = TranslationAssignment
    template_name = "accounts/translation_assignments.html"
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


class TranslationAssignmentDetailView(TranslationPermissionMixin, DetailView):
    """View for viewing translation assignment details"""

    model = TranslationAssignment
    template_name = "accounts/translation_assignment_detail.html"
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

    return redirect("accounts:translation_assignment_detail", pk=pk)


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

    return redirect("accounts:translation_assignment_detail", pk=pk)


@login_required
def approve_translation_assignment(request, pk):
    """Approve a translation assignment (editors only)"""
    assignment = get_object_or_404(TranslationAssignment, pk=pk)

    if not request.user.role in ["editor", "admin"]:
        messages.error(request, "You need editor permissions to approve translations.")
        return redirect("accounts:translation_assignment_detail", pk=pk)

    if assignment.status == "review":
        assignment.status = "approved"
        assignment.save()
        messages.success(request, "Translation approved!")
    else:
        messages.warning(request, "This assignment cannot be approved.")

    return redirect("accounts:translation_assignment_detail", pk=pk)


@login_required
def reject_translation_assignment(request, pk):
    """Reject a translation assignment (editors only)"""
    assignment = get_object_or_404(TranslationAssignment, pk=pk)

    if not request.user.role in ["editor", "admin"]:
        messages.error(request, "You need editor permissions to reject translations.")
        return redirect("accounts:translation_assignment_detail", pk=pk)

    if assignment.status == "review":
        assignment.status = "rejected"
        assignment.reviewer_notes = request.POST.get("reviewer_notes", "")
        assignment.save()
        messages.success(request, "Translation rejected.")
    else:
        messages.warning(request, "This assignment cannot be rejected.")

    return redirect("accounts:translation_assignment_detail", pk=pk)


@login_required
def assign_role_ajax(request, user_id):
    """AJAX view for assigning roles to users (admin/editor only)"""
    if not request.user.role in ["admin", "editor"]:
        return JsonResponse({"success": False, "error": "Permission denied"})

    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        form = RoleAssignmentForm(request.POST, current_user=request.user)

        if form.is_valid():
            new_role = form.cleaned_data["role"]
            target_user.role = new_role
            target_user.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Role updated to {target_user.get_role_display_name()}",
                    "new_role": new_role,
                    "new_role_display": target_user.get_role_display_name(),
                }
            )
        else:
            return JsonResponse({"success": False, "error": "Invalid form data"})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def get_user_permissions_ajax(request):
    """AJAX view to get user permissions for a book"""
    book_id = request.GET.get("book_id")
    if not book_id:
        return JsonResponse({"success": False, "error": "Book ID required"})

    from books.models import Book

    book = get_object_or_404(Book, id=book_id)
    permissions = get_user_permissions(request.user, book)

    return JsonResponse({"success": True, "permissions": permissions})


@login_required
def custom_logout(request):
    """Custom logout view that handles both GET and POST requests"""
    from django.contrib.auth import logout
    from django.shortcuts import redirect

    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("accounts:login")
