from django.conf import settings
from django.db import models
# from django.contrib.postgres.fields import JSONField

from books.models import Chapter
from languages.models import Language


class Translation(models.Model):
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="translations"
    )
    target_language = models.ForeignKey(
        Language, on_delete=models.CASCADE, related_name="translations"
    )
    title = models.CharField(max_length=255, default="")
    translated_text = models.TextField()
    key_terms = models.JSONField(default=dict, blank=True)
    is_ai_generated = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["chapter", "target_language", "version"]


class EditHistory(models.Model):
    translation = models.ForeignKey(
        Translation, on_delete=models.CASCADE, related_name="edit_history"
    )
    old_text = models.TextField()
    new_text = models.TextField()
    diff_html = models.TextField()  # Store HTML diff for display
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    edited_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)
