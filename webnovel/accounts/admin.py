from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, BookCollaborator, TranslationAssignment
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
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                obj.avatar.url
            )
        return "No avatar"
    avatar_preview.short_description = 'Avatar'


@admin.register(BookCollaborator)
class BookCollaboratorAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'book', 'role', 'is_active', 'joined_at'
    ]
    list_filter = [
        'role', 'is_active', 'joined_at'
    ]
    search_fields = [
        'user__username', 'user__pen_name', 'book__title'
    ]
    ordering = ['-joined_at']
    
    fieldsets = (
        ('Collaboration Info', {
            'fields': ('user', 'book', 'role', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'Custom permissions for this collaboration'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('joined_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['joined_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book')


@admin.register(TranslationAssignment)
class TranslationAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'chapter', 'translator', 'target_language', 'status', 
        'assigned_at', 'due_date', 'is_overdue_display'
    ]
    list_filter = [
        'status', 'target_language', 'assigned_at', 'due_date'
    ]
    search_fields = [
        'chapter__title', 'translator__username', 'translator__pen_name'
    ]
    ordering = ['-assigned_at']
    
    fieldsets = (
        ('Assignment Info', {
            'fields': ('chapter', 'translator', 'target_language', 'status')
        }),
        ('Timing', {
            'fields': ('assigned_at', 'due_date', 'started_at', 'completed_at')
        }),
        ('Notes', {
            'fields': ('notes', 'reviewer_notes'),
            'classes': ('collapse',)
        }),
        ('Assignment Details', {
            'fields': ('assigned_by',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'assigned_at', 'started_at', 'completed_at', 'is_overdue_display'
    ]
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">OVERDUE</span>'
            )
        elif obj.days_remaining is not None:
            if obj.days_remaining <= 3:
                color = 'orange'
            else:
                color = 'green'
            return format_html(
                '<span style="color: {};">{} days</span>',
                color, obj.days_remaining
            )
        return "No due date"
    is_overdue_display.short_description = 'Due Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'chapter', 'translator', 'target_language', 'assigned_by'
        )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new assignment
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
