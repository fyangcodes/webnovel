from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill, Thumbnail


class User(AbstractUser):
    ROLE_CHOICES = [
        ("reader", "Reader"),
        ("writer", "Writer"),
        ("translator", "Translator"),
        ("editor", "Editor"),
        ("admin", "Administrator"),
    ]

    # Basic profile fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="reader")
    pen_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

    # Author-specific fields
    is_author = models.BooleanField(default=False)
    author_bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)

    def user_avatar_path(instance, filename):
        """Generate user-specific avatar upload path"""
        # Get file extension
        ext = filename.split(".")[-1]
        # Create path: users/{user_id}/avatar/avatar.{ext}
        return f"users/{instance.id}/avatar/avatar.{ext}"

    def user_avatar_thumbnail_path(instance, filename):
        """Generate user-specific avatar thumbnail upload path"""
        # Get file extension
        ext = filename.split(".")[-1]
        # Create path: users/{user_id}/avatar/thumbnail.{ext}
        return f"users/{instance.id}/avatar/thumbnail.{ext}"

    # Avatar with automatic resizing
    avatar = ProcessedImageField(
        upload_to=user_avatar_path,
        processors=[ResizeToFill(300, 300)],
        format="JPEG",
        options={"quality": 85},
        blank=True,
        null=True,
    )

    # Thumbnail for smaller displays
    avatar_thumbnail = ProcessedImageField(
        upload_to=user_avatar_thumbnail_path,
        processors=[Thumbnail(50, 50)],
        format="JPEG",
        options={"quality": 80},
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "auth_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def save(self, *args, **kwargs):
        # Generate thumbnail when avatar is saved
        # if self.avatar and not self.avatar_thumbnail:
        #     self.avatar_thumbnail = self.avatar
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    @property
    def display_name(self):
        """Return pen_name if available, otherwise username"""
        return self.pen_name or self.username

    @property
    def is_writer(self):
        return self.role in ["writer", "editor", "admin"]

    @property
    def is_translator(self):
        return self.role in ["translator", "editor", "admin"]

    @property
    def is_editor(self):
        return self.role in ["editor", "admin"]

    @property
    def is_administrator(self):
        return self.role == "admin"

    def get_role_display_name(self):
        """Get a more user-friendly role name"""
        role_names = {
            "reader": "Reader",
            "writer": "Writer",
            "translator": "Translator",
            "editor": "Editor",
            "admin": "Administrator",
        }
        return role_names.get(self.role, self.role.title())


class BookCollaborator(models.Model):
    """Model for managing book collaborations and permissions"""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("co_author", "Co-Author"),
        ("translator", "Translator"),
        ("reviewer", "Reviewer"),
        ("editor", "Editor"),
    ]

    book = models.ForeignKey(
        "books.Book", on_delete=models.CASCADE, related_name="collaborators"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_collaborations",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    permissions = models.JSONField(
        default=dict, help_text="Granular permissions for this collaboration"
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["book", "user"]
        verbose_name = "Book Collaborator"
        verbose_name_plural = "Book Collaborators"

    def __str__(self):
        return f"{self.user.display_name} - {self.role} on {self.book.title}"

    def get_permissions(self):
        """Get effective permissions for this collaboration"""
        base_permissions = {
            "can_read": True,
            "can_write": False,
            "can_edit": False,
            "can_delete": False,
            "can_translate": False,
            "can_approve": False,
        }

        role_permissions = {
            "owner": {
                "can_write": True,
                "can_edit": True,
                "can_delete": True,
            },
            "co_author": {
                "can_write": True,
                "can_edit": True,
                "can_delete": True,
            },
            "translator": {
                "can_translate": True,
            },
            "reviewer": {
                "can_approve": True,
            },
            "editor": {
                "can_write": True,
                "can_edit": True,
                "can_delete": True,
                "can_translate": True,
                "can_approve": True,
            },
        }

        # Merge base permissions with role permissions
        permissions = base_permissions.copy()
        if self.role in role_permissions:
            permissions.update(role_permissions[self.role])

        # Override with custom permissions if set
        permissions.update(self.permissions)

        return permissions


class TranslationAssignment(models.Model):
    """Model for managing translation assignments and workflow"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    chapter = models.ForeignKey(
        "books.Chapter",
        on_delete=models.CASCADE,
        related_name="translation_assignments",
    )
    translator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="translation_assignments",
    )
    target_language = models.ForeignKey("books.Language", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_translations",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    reviewer_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["chapter", "translator", "target_language"]
        verbose_name = "Translation Assignment"
        verbose_name_plural = "Translation Assignments"

    def __str__(self):
        return f"Translation of {self.chapter.title} to {self.target_language.name} by {self.translator.display_name}"

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ["approved", "rejected"]:
            from django.utils import timezone

            return timezone.now() > self.due_date
        return False

    @property
    def days_remaining(self):
        if self.due_date and self.status not in ["approved", "rejected"]:
            from django.utils import timezone
            from datetime import timedelta

            remaining = self.due_date - timezone.now()
            return remaining.days
        return None
