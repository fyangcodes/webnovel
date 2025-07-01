from django.contrib import admin
from .models import LLMProvider, LLMServiceCall, LLMQualityMetrics


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "display_name",
        "is_active",
        "api_key_configured",
        "default_model",
        "cost_per_1k_tokens",
    ]
    list_filter = ["is_active", "api_key_configured"]
    search_fields = ["name", "display_name"]
    readonly_fields = ["available_models"]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return list(self.readonly_fields) + ["name"]
        return self.readonly_fields


@admin.register(LLMServiceCall)
class LLMServiceCallAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "model_name",
        "operation",
        "status",
        "response_time_ms",
        "total_tokens",
        "created_at",
    ]
    list_filter = ["provider", "operation", "status", "created_at"]
    search_fields = ["provider__name", "model_name", "operation", "error_message"]
    readonly_fields = ["created_at", "total_tokens", "estimated_cost"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Service Information",
            {"fields": ("provider", "model_name", "operation", "status")},
        ),
        (
            "Request Details",
            {"fields": ("input_tokens", "output_tokens", "temperature", "max_tokens")},
        ),
        ("Response Details", {"fields": ("response_time_ms", "error_message")}),
        (
            "Content Context",
            {"fields": ("book", "chapter", "source_language", "target_language")},
        ),
        ("Quality Metrics", {"fields": ("quality_score", "user_feedback")}),
        (
            "Metadata",
            {"fields": ("created_at", "created_by", "total_tokens", "estimated_cost")},
        ),
    )


@admin.register(LLMQualityMetrics)
class LLMQualityMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "provider",
        "model_name",
        "operation",
        "total_calls",
        "success_rate",
        "avg_response_time_ms",
        "period_start",
    ]
    list_filter = ["provider", "operation", "period_start"]
    search_fields = ["provider__name", "model_name", "operation"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "period_start"

    fieldsets = (
        ("Provider Information", {"fields": ("provider", "model_name", "operation")}),
        (
            "Metrics",
            {
                "fields": (
                    "total_calls",
                    "success_rate",
                    "avg_response_time_ms",
                    "avg_quality_score",
                )
            },
        ),
        ("Usage & Cost", {"fields": ("total_tokens_used", "total_cost")}),
        ("Time Period", {"fields": ("period_start", "period_end")}),
        ("Language Context", {"fields": ("source_language", "target_language")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )
