from django.db import models
from django.contrib.auth.models import User
from books.models import Book, Chapter
import json


class LLMProvider(models.Model):
    """LLM Provider configuration"""
    name = models.CharField(max_length=50, unique=True)  # openai, anthropic, etc.
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    api_key_configured = models.BooleanField(default=False)
    default_model = models.CharField(max_length=100)
    available_models = models.JSONField(default=list)
    cost_per_1k_tokens = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.display_name


class LLMServiceCall(models.Model):
    """Track individual LLM API calls for quality control"""
    
    OPERATION_CHOICES = [
        ('translation', 'Translation'),
        ('abstract_generation', 'Abstract Generation'),
        ('key_terms_extraction', 'Key Terms Extraction'),
        ('chapter_division', 'Chapter Division'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('rate_limited', 'Rate Limited'),
    ]
    
    # Service identification
    provider = models.ForeignKey(LLMProvider, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=100)
    operation = models.CharField(max_length=50, choices=OPERATION_CHOICES)
    
    # Request details
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    temperature = models.FloatField(default=0.3)
    max_tokens = models.IntegerField(default=2000)
    
    # Response details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    response_time_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Source content context (what we're translating FROM)
    source_book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=True, related_name='llm_calls_as_source')
    source_chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, null=True, blank=True, related_name='llm_calls_as_source')
    source_language = models.CharField(max_length=10, blank=True)
    
    # Target content context (what we're translating TO)
    target_book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=True, related_name='llm_calls_as_target')
    target_chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, null=True, blank=True, related_name='llm_calls_as_target')
    target_language = models.CharField(max_length=10, blank=True)
    
    # Quality metrics (optional)
    quality_score = models.FloatField(null=True, blank=True)  # 0-1 scale
    user_feedback = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'operation', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['source_book', 'source_chapter']),
            models.Index(fields=['target_book', 'target_chapter']),
        ]
    
    def __str__(self):
        return f"{self.provider.name}/{self.model_name} - {self.operation} ({self.status})"
    
    @property
    def total_tokens(self):
        return (self.input_tokens or 0) + (self.output_tokens or 0)
    
    @property
    def estimated_cost(self):
        if self.provider.cost_per_1k_tokens and self.total_tokens:
            return (self.total_tokens / 1000) * self.provider.cost_per_1k_tokens
        return None


class LLMQualityMetrics(models.Model):
    """Aggregated quality metrics for providers/models"""
    
    provider = models.ForeignKey(LLMProvider, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=100)
    operation = models.CharField(max_length=50, choices=LLMServiceCall.OPERATION_CHOICES)
    
    # Aggregated metrics
    total_calls = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)  # 0-1
    avg_response_time_ms = models.FloatField(default=0.0)
    avg_quality_score = models.FloatField(default=0.0)
    total_tokens_used = models.BigIntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Time period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Language-specific metrics
    source_language = models.CharField(max_length=10, blank=True)
    target_language = models.CharField(max_length=10, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['provider', 'model_name', 'operation', 'period_start', 'source_language', 'target_language']
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.provider.name}/{self.model_name} - {self.operation} ({self.success_rate:.2%})"
