from django.contrib import admin
from django.utils.html import format_html
from .models import BookCollaborator, TranslationAssignment


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
