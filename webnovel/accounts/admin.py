from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    
    list_display = [
        'username', 'email', 'display_name', 'role', 'is_verified', 
        'is_active', 'date_joined', 'avatar_preview'
    ]
    list_filter = [
        'role', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 
        'date_joined', 'is_author'
    ]
    search_fields = ['username', 'email', 'pen_name', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'email', 'pen_name', 'bio', 
                'birth_date', 'location', 'website'
            )
        }),
        ('Role & Permissions', {
            'fields': (
                'role', 'is_verified', 'is_author', 'author_bio',
                'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
            )
        }),
        ('Avatar', {
            'fields': ('avatar', 'avatar_thumbnail'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2', 'role', 
                'pen_name', 'is_active'
            ),
        }),
    )
    
    readonly_fields = ['avatar_thumbnail', 'date_joined', 'last_login']
    
    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = 'Display Name'
    
    def avatar_preview(self, obj):
        return format_html(
            '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
            obj.get_avatar_url()
        )
    avatar_preview.short_description = 'Avatar'



