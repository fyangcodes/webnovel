from django import forms
from .models import BookFile, Chapter

class BookFileForm(forms.ModelForm):
    class Meta:
        model = BookFile
        fields = ["file", "description"]

class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ["title", "content", "chapter_number", "abstract", "key_terms"] 