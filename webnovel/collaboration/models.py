from django.db import models
from django.conf import settings


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
