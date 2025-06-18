from django import forms
from .models import Translation, EditHistory


class TranslationForm(forms.ModelForm):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Add a comment about your changes (optional)",
            }
        ),
    )

    class Meta:
        model = Translation
        fields = ["translated_text"]
        widgets = {
            "translated_text": forms.Textarea(
                attrs={
                    "rows": 10,
                    "class": "translation-editor",
                    "data-language": "{{ language }}",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["translated_text"].widget.attrs.update(
            {
                "class": "form-control translation-editor",
                "style": "font-family: monospace;",
            }
        )
