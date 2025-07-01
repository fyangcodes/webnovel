from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    LoginView,
    PasswordChangeView,
    PasswordChangeDoneView,
)
from . import views

app_name = "accounts"

urlpatterns = [
    # Profile management
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    # User management (admin only)
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path(
        "users/<int:user_id>/assign-role/",
        views.assign_role_ajax,
        name="assign_role_ajax",
    ),
    # Translation assignments
    path(
        "translations/",
        views.TranslationAssignmentListView.as_view(),
        name="translation_assignments",
    ),
    path(
        "translations/<int:pk>/",
        views.TranslationAssignmentDetailView.as_view(),
        name="translation_assignment_detail",
    ),
    path(
        "translations/<int:pk>/start/",
        views.start_translation_assignment,
        name="start_translation_assignment",
    ),
    path(
        "translations/<int:pk>/submit/",
        views.submit_translation_assignment,
        name="submit_translation_assignment",
    ),
    path(
        "translations/<int:pk>/approve/",
        views.approve_translation_assignment,
        name="approve_translation_assignment",
    ),
    path(
        "translations/<int:pk>/reject/",
        views.reject_translation_assignment,
        name="reject_translation_assignment",
    ),
    # Authentication
    path(
        "login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        views.custom_logout,
        name="logout",
    ),
    path(
        "password_change/",
        PasswordChangeView.as_view(
            template_name="registration/password_change_form.html"
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
    # AJAX endpoints
    path("permissions/", views.get_user_permissions_ajax, name="get_permissions_ajax"),
]
