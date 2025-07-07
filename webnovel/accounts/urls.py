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
