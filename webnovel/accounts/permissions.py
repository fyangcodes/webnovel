from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from .models import TranslationAssignment, User, BookCollaborator


def get_user_permissions(user, book=None):
    """
    Get user permissions for a specific book or globally

    Args:
        user: User instance
        book: Book instance (optional)

    Returns:
        dict: Dictionary of permissions
    """
    permissions = {
        "can_read": True,  # Everyone can read
        "can_write": user.role in ["writer", "editor", "admin"],
        "can_translate": user.role in ["translator", "editor", "admin"],
        "can_edit": user.role in ["editor", "admin"],
        "can_approve": user.role in ["editor", "admin"],
        "can_delete": user.role == "admin",
        "can_assign_translations": user.role in ["editor", "admin"],
        "can_manage_users": user.role == "admin",
    }

    if book:
        # Check book-specific permissions
        collaboration = book.collaborators.filter(user=user, is_active=True).first()
        if collaboration:
            collaboration_permissions = collaboration.get_permissions()
            # Merge global permissions with book-specific permissions
            for key, value in collaboration_permissions.items():
                if value:  # Only override if permission is granted
                    permissions[key] = value

    return permissions


def check_permission(user, permission, book=None):
    """
    Check if user has a specific permission

    Args:
        user: User instance
        permission: Permission string (e.g., 'can_write', 'can_translate')
        book: Book instance (optional)

    Returns:
        bool: True if user has permission, False otherwise
    """
    permissions = get_user_permissions(user, book)
    return permissions.get(permission, False)


def get_books_user_can_access(user):
    """
    Get queryset of books user can access based on their role and collaborations

    Args:
        user: User instance

    Returns:
        QuerySet: Books the user can access
    """
    from books.models import Book

    if user.role == "admin":
        return Book.objects.all()
    elif user.role in ["editor", "writer"]:
        return Book.objects.filter(
            models.Q(owner=user)
            | models.Q(collaborators__user=user, collaborators__is_active=True)
        ).distinct()
    elif user.role == "translator":
        # Translators can see books they have translation assignments for
        return Book.objects.filter(
            models.Q(collaborators__user=user, collaborators__is_active=True)
            | models.Q(chapters__translation_assignments__translator=user)
        ).distinct()
    else:
        # Readers can only see published books
        return Book.objects.filter(status="published")


def get_translation_assignments_for_user(user):
    """
    Get translation assignments for a user

    Args:
        user: User instance

    Returns:
        QuerySet: Translation assignments for the user
    """
    if user.role in ["translator", "editor", "admin"]:
        return user.translation_assignments.all()
    return TranslationAssignment.objects.none()


def can_user_translate_chapter(user, chapter, target_language):
    """
    Check if user can translate a specific chapter to a target language

    Args:
        user: User instance
        chapter: Chapter instance
        target_language: Language instance

    Returns:
        bool: True if user can translate, False otherwise
    """
    # Check if user has translation permissions
    if not check_permission(user, "can_translate", chapter.book):
        return False

    # Check if translation already exists
    existing_translation = chapter.translations.filter(
        language=target_language
    ).exists()
    if existing_translation:
        return False

    # Check if user already has an assignment for this translation
    existing_assignment = chapter.translation_assignments.filter(
        translator=user, target_language=target_language
    ).exists()

    return not existing_assignment


def assign_translation_task(
    user, chapter, target_language, assigned_by=None, due_date=None
):
    """
    Assign a translation task to a user

    Args:
        user: User to assign the task to
        chapter: Chapter to translate
        target_language: Target language
        assigned_by: User who is making the assignment
        due_date: Due date for the translation

    Returns:
        TranslationAssignment: Created assignment instance
    """
    if not can_user_translate_chapter(user, chapter, target_language):
        raise ValueError("User cannot be assigned this translation task")

    assignment = TranslationAssignment.objects.create(
        chapter=chapter,
        translator=user,
        target_language=target_language,
        assigned_by=assigned_by,
        due_date=due_date,
        status="assigned",
    )

    return assignment


def get_user_role_display(user):
    """
    Get a user-friendly display name for the user's role

    Args:
        user: User instance

    Returns:
        str: Display name for the role
    """
    return user.get_role_display_name()


def get_available_roles_for_user(current_user, target_user=None):
    """
    Get available roles that the current user can assign

    Args:
        current_user: User making the role assignment
        target_user: User being assigned a role (optional)

    Returns:
        list: Available role choices
    """
    if current_user.role == "admin":
        return User.ROLE_CHOICES
    elif current_user.role == "editor":
        # Editors can assign reader, writer, and translator roles
        return [
            ("reader", "Reader"),
            ("writer", "Writer"),
            ("translator", "Translator"),
        ]
    else:
        # Other roles cannot assign roles
        return []


def get_collaboration_roles_for_user(current_user, book):
    """
    Get available collaboration roles that the current user can assign for a book

    Args:
        current_user: User making the collaboration assignment
        book: Book instance

    Returns:
        list: Available collaboration role choices
    """
    if current_user.role == "admin":
        return BookCollaborator.ROLE_CHOICES
    elif current_user.role == "editor" or book.owner == current_user:
        # Editors and book owners can assign collaboration roles
        return [
            ("co_author", "Co-Author"),
            ("translator", "Translator"),
            ("editor", "Editor"),
            ("reviewer", "Reviewer"),
        ]
    else:
        return []
