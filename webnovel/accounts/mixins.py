from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from .permissions import check_permission, get_user_permissions


class BookPermissionMixin(UserPassesTestMixin):
    """
    Mixin to check book-specific permissions
    """

    required_permission = "can_read"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Get the book object
        book = self.get_book_object()
        if not book:
            return False

        return check_permission(user, self.required_permission, book)

    def get_book_object(self):
        """
        Get the book object for permission checking.
        Override this method if the book is not directly accessible.
        """
        if hasattr(self, "get_object"):
            obj = self.get_object()
            if hasattr(obj, "book"):
                return obj.book
            elif hasattr(obj, "__class__") and obj.__class__.__name__ == "Book":
                return obj
        return None

    def handle_no_permission(self):
        messages.error(
            self.request, "You don't have permission to access this resource."
        )
        return redirect("books:book_list")


class TranslationPermissionMixin(UserPassesTestMixin):
    """
    Mixin to check translation permissions
    """

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        return user.role in ["translator", "editor", "admin"]

    def handle_no_permission(self):
        messages.error(
            self.request, "You don't have permission to perform translation tasks."
        )
        return redirect("books:book_list")


class EditorPermissionMixin(UserPassesTestMixin):
    """
    Mixin to check editor permissions
    """

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        return user.role in ["editor", "admin"]

    def handle_no_permission(self):
        messages.error(
            self.request, "You need editor permissions to perform this action."
        )
        return redirect("books:book_list")


class AdminPermissionMixin(UserPassesTestMixin):
    """
    Mixin to check admin permissions
    """

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        return user.role == "admin"

    def handle_no_permission(self):
        messages.error(
            self.request, "You need administrator permissions to perform this action."
        )
        return redirect("books:book_list")


class WriterPermissionMixin(UserPassesTestMixin):
    """
    Mixin to check writer permissions
    """

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        return user.role in ["writer", "editor", "admin"]

    def handle_no_permission(self):
        messages.error(
            self.request, "You need writer permissions to perform this action."
        )
        return redirect("books:book_list")


class BookOwnerMixin(UserPassesTestMixin):
    """
    Mixin to check if user is the owner of a book
    """

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers can access all books
        if user.is_superuser:
            return True

        book = self.get_book_object()
        if not book:
            return False

        return book.owner == user

    def get_book_object(self):
        """
        Get the book object for permission checking.
        Override this method if the book is not directly accessible.
        """
        if hasattr(self, "get_object"):
            obj = self.get_object()
            if hasattr(obj, "book"):
                return obj.book
            elif hasattr(obj, "__class__") and obj.__class__.__name__ == "Book":
                return obj
        return None

    def handle_no_permission(self):
        messages.error(self.request, "You can only modify your own books.")
        return redirect("books:book_list")


class BookCollaboratorMixin(UserPassesTestMixin):
    """
    Mixin to check if user is a collaborator on a book
    """

    required_collaboration_permission = "can_read"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers can access all books
        if user.is_superuser:
            return True

        book = self.get_book_object()
        if not book:
            return False

        # Check if user is owner
        if book.owner == user:
            return True

        # Check if user is a collaborator with required permissions
        collaboration = book.collaborators.filter(user=user, is_active=True).first()
        if collaboration:
            permissions = collaboration.get_permissions()
            return permissions.get(self.required_collaboration_permission, False)

        return False

    def get_book_object(self):
        """
        Get the book object for permission checking.
        Override this method if the book is not directly accessible.
        """
        if hasattr(self, "get_object"):
            obj = self.get_object()
            if hasattr(obj, "book"):
                return obj.book
            elif hasattr(obj, "__class__") and obj.__class__.__name__ == "Book":
                return obj
        return None

    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access this book.")
        return redirect("books:book_list")


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Mixin to check if user has a specific role
    """

    required_roles = []

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False

        # Superusers have all permissions
        if user.is_superuser:
            return True

        return user.role in self.required_roles

    def handle_no_permission(self):
        role_names = [
            dict(User.ROLE_CHOICES).get(role, role) for role in self.required_roles
        ]
        messages.error(
            self.request, f"You need one of these roles: {', '.join(role_names)}"
        )
        return redirect("books:book_list")
