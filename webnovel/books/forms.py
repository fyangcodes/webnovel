from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import BookFile, Chapter, Book


class BookFileForm(forms.ModelForm):
    class Meta:
        model = BookFile
        fields = ["file", "description"]


class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ["title", "content", "status", "active_at"]
        widgets = {
            "active_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "content": forms.Textarea(attrs={"rows": 20, "cols": 80}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for auto-generated fields
        if not self.instance.pk:  # Only for new instances
            self.instance.key_terms = []
            # Ensure chapter_number is None for new instances so AutoIncrementingPositiveIntegerField can handle it
            self.instance.chapter_number = None

    def clean_active_at(self):
        active_at = self.cleaned_data.get("active_at")
        status = self.cleaned_data.get("status")

        if status == "scheduled" and not active_at:
            raise forms.ValidationError(
                "Scheduled chapters must have a publish date/time"
            )

        if active_at and active_at <= timezone.now():
            raise forms.ValidationError("Publish date/time must be in the future")

        return active_at

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure key_terms is set to empty list if not provided
        if not hasattr(instance, 'key_terms') or instance.key_terms is None:
            instance.key_terms = []
        # Ensure chapter_number is None for new instances
        if not instance.pk and (not hasattr(instance, 'chapter_number') or instance.chapter_number is None):
            instance.chapter_number = None
        if commit:
            instance.save()
        return instance


class ChapterScheduleForm(forms.Form):
    """Form for scheduling chapter publication"""

    publish_datetime = forms.DateTimeField(
        label="Publish Date & Time",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
        help_text="When should this chapter be published?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default to tomorrow at 9 AM
        tomorrow = timezone.now() + timedelta(days=1)
        default_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        self.fields["publish_datetime"].initial = default_time

    def clean_publish_datetime(self):
        publish_datetime = self.cleaned_data.get("publish_datetime")

        if publish_datetime and publish_datetime <= timezone.now():
            raise forms.ValidationError("Publish date/time must be in the future")

        return publish_datetime


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "language",
            "isbn",
            "description",
            "cover_image",
            "status",
        ]
