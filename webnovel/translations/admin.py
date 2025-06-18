from django.contrib import admin
from .models import Translation, EditHistory

@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ['chapter', 'target_language', 'version', 'is_ai_generated', 'created_at', 'created_by']
    list_filter = ['target_language', 'is_ai_generated', 'created_at']
    search_fields = ['chapter__book__title', 'chapter__title', 'translated_text']
    raw_id_fields = ['chapter', 'created_by']
    readonly_fields = ['version']

@admin.register(EditHistory)
class EditHistoryAdmin(admin.ModelAdmin):
    list_display = ['translation', 'edited_by', 'edited_at']
    list_filter = ['edited_at', 'edited_by']
    search_fields = ['translation__chapter__book__title', 'comment']
    raw_id_fields = ['translation', 'edited_by']
    readonly_fields = ['diff_html']
