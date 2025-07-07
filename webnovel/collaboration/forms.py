from django import forms
from django.contrib.auth import get_user_model
from .models import BookCollaborator, TranslationAssignment
from .permissions import get_available_roles_for_user, get_collaboration_roles_for_user

User = get_user_model()


class BookCollaboratorForm(forms.ModelForm):
    """Form for adding/editing book collaborators"""
    
    class Meta:
        model = BookCollaborator
        fields = ('user', 'role', 'permissions', 'notes')
        widgets = {
            'permissions': forms.CheckboxSelectMultiple(),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        book = kwargs.pop('book', None)
        super().__init__(*args, **kwargs)
        
        if current_user and book:
            # Limit role choices based on current user's permissions
            available_roles = get_collaboration_roles_for_user(current_user, book)
            self.fields['role'].choices = available_roles
            
            # Filter user choices to exclude existing collaborators
            existing_collaborators = book.collaborators.values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(
                id__in=existing_collaborators
            ).exclude(id=book.owner.id)
        
        # Customize permissions field
        permission_choices = [
            ('can_read', 'Can Read'),
            ('can_write', 'Can Write'),
            ('can_translate', 'Can Translate'),
            ('can_edit', 'Can Edit'),
            ('can_approve', 'Can Approve'),
        ]
        self.fields['permissions'] = forms.MultipleChoiceField(
            choices=permission_choices,
            required=False,
            widget=forms.CheckboxSelectMultiple(),
            help_text="Select specific permissions for this collaborator"
        )


class TranslationAssignmentForm(forms.ModelForm):
    """Form for creating translation assignments"""
    
    class Meta:
        model = TranslationAssignment
        fields = ('translator', 'target_language', 'due_date', 'notes')
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        chapter = kwargs.pop('chapter', None)
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        if chapter:
            # Filter translators to only those who can translate
            from .permissions import check_permission
            translators = User.objects.filter(role__in=['translator', 'editor', 'admin'])
            
            # Filter out translators who already have assignments for this chapter
            existing_assignments = chapter.translation_assignments.values_list('translator_id', flat=True)
            translators = translators.exclude(id__in=existing_assignments)
            
            self.fields['translator'].queryset = translators
            
            # Filter target languages to exclude existing translations
            existing_languages = chapter.translations.values_list('language_id', flat=True)
            from books.models import Language
            available_languages = Language.objects.exclude(id__in=existing_languages)
            self.fields['target_language'].queryset = available_languages


class TranslationAssignmentFilterForm(forms.Form):
    """Form for filtering translation assignments"""
    
    STATUS_CHOICES = [('', 'All Statuses')] + TranslationAssignment.STATUS_CHOICES
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        help_text="Filter by assignment status"
    )
    
    target_language = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        help_text="Filter by target language"
    )
    
    is_overdue = forms.BooleanField(
        required=False,
        help_text="Show only overdue assignments"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            from books.models import Language
            # Get languages from user's assignments
            user_languages = Language.objects.filter(
                translationassignment__translator=user
            ).distinct()
            self.fields['target_language'].queryset = user_languages 