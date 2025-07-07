from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import User
from collaboration.permissions import get_available_roles_for_user, get_collaboration_roles_for_user

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users with role selection"""
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'pen_name', 'bio', 'avatar')
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Limit role choices based on current user's permissions
        if current_user:
            available_roles = get_available_roles_for_user(current_user)
            self.fields['role'].choices = available_roles
        else:
            # Default to reader role for self-registration
            self.fields['role'].choices = [('reader', 'Reader')]
            self.fields['role'].initial = 'reader'
        
        # Make role field required for admins/editors
        if current_user and current_user.role in ['admin', 'editor']:
            self.fields['role'].required = True
        else:
            self.fields['role'].required = False


class CustomUserChangeForm(UserChangeForm):
    """Form for editing user profiles"""
    
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'pen_name', 'bio', 'birth_date', 
                 'location', 'website', 'is_author', 'author_bio', 'avatar')
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        target_user = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        
        # Limit role choices based on current user's permissions
        if current_user:
            available_roles = get_available_roles_for_user(current_user, target_user)
            self.fields['role'].choices = available_roles
        else:
            # If no current user (e.g., admin interface), show all roles
            pass


class UserProfileForm(forms.ModelForm):
    """Form for users to edit their own profile"""
    
    class Meta:
        model = User
        fields = ('pen_name', 'bio', 'birth_date', 'location', 'website', 
                 'is_author', 'author_bio', 'avatar')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make avatar optional
        self.fields['avatar'].required = False


class RoleAssignmentForm(forms.Form):
    """Form for assigning roles to users"""
    
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        help_text="Select the role to assign to this user"
    )
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        if current_user:
            available_roles = get_available_roles_for_user(current_user)
            self.fields['role'].choices = available_roles


class UserSearchForm(forms.Form):
    """Form for searching users"""
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search by username, email, or pen name'})
    )
    
    role = forms.ChoiceField(
        choices=[('', 'All Roles')] + User.ROLE_CHOICES,
        required=False,
        help_text="Filter by user role"
    )
    
    is_verified = forms.BooleanField(
        required=False,
        help_text="Show only verified users"
    ) 