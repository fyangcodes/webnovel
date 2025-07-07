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



