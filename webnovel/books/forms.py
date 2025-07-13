from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import BookFile, Chapter, Book


class BookFileForm(forms.ModelForm):
    class Meta:
        model = BookFile
        fields = ["file", "description"]


class ChapterForm(forms.ModelForm):
    # Custom field for content that works with the new content system
    content = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 20, "cols": 80}),
        required=False,
        help_text="Chapter content"
    )
    
    class Meta:
        model = Chapter
        fields = ["title", "status", "active_at"]
        widgets = {
            "active_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for auto-generated fields
        if not self.instance.pk:  # Only for new instances
            self.instance.key_terms = []
            self.instance.chapter_number = None
        
        # Load raw content from S3 if available
        if self.instance.pk and hasattr(self.instance, 'get_raw_content'):
            raw_content = self.instance.get_raw_content()
            if raw_content:
                self.fields['content'].initial = raw_content

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
            # Save the instance first to get an ID
            instance.save()
            
            # Save raw content to S3
            content_text = self.cleaned_data.get('content', '')
            if content_text:
                try:
                    instance.save_raw_content(
                        content_text, 
                        user=getattr(self, 'user', None),
                        summary="Content updated via form"
                    )
                except Exception as e:
                    # Log error but don't fail the form save
                    print(f"Error saving raw content to S3: {e}")
        
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
