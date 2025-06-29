from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .utils import generate_quality_report, get_provider_performance_summary
from .models import LLMServiceCall, LLMProvider, LLMQualityMetrics
from django.db import models


@staff_member_required
def llm_dashboard(request):
    """Dashboard for LLM quality control and monitoring"""
    # Get period from request
    days = int(request.GET.get('days', 7))
    
    # Generate report
    report = generate_quality_report(days)
    
    # Get recent service calls
    recent_calls = LLMServiceCall.objects.select_related('provider', 'book', 'chapter').order_by('-created_at')[:20]
    
    # Get provider statistics
    providers = LLMProvider.objects.filter(is_active=True)
    
    context = {
        'report': report,
        'recent_calls': recent_calls,
        'providers': providers,
        'selected_days': days,
        'period_options': [1, 7, 30, 90],
    }
    
    return render(request, 'llm_integration/dashboard.html', context)


@staff_member_required
def llm_metrics_api(request):
    """API endpoint for LLM metrics data"""
    days = int(request.GET.get('days', 7))
    
    # Get provider performance summary
    provider_summary = get_provider_performance_summary(days)
    
    # Get recent errors
    recent_errors = LLMServiceCall.objects.filter(
        status__in=['error', 'timeout', 'rate_limited']
    ).select_related('provider').order_by('-created_at')[:10]
    
    # Get operation metrics
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    operation_metrics = LLMQualityMetrics.objects.filter(
        period_start=start_date,
        period_end=end_date
    ).values('operation').annotate(
        total_calls=models.Sum('total_calls'),
        avg_success_rate=models.Avg('success_rate'),
        avg_response_time=models.Avg('avg_response_time_ms'),
        total_cost=models.Sum('total_cost')
    )
    
    return JsonResponse({
        'provider_summary': provider_summary,
        'recent_errors': [
            {
                'provider': error.provider.display_name,
                'model': error.model_name,
                'operation': error.operation,
                'status': error.status,
                'error_message': error.error_message[:100] + '...' if len(error.error_message) > 100 else error.error_message,
                'created_at': error.created_at.isoformat()
            }
            for error in recent_errors
        ],
        'operation_metrics': list(operation_metrics),
        'period': {
            'days': days,
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    })


@staff_member_required
def llm_service_calls(request):
    """View for browsing LLM service calls"""
    # Get filters from request
    provider_id = request.GET.get('provider')
    operation = request.GET.get('operation')
    status = request.GET.get('status')
    days = int(request.GET.get('days', 7))
    
    # Build queryset
    calls = LLMServiceCall.objects.select_related('provider', 'book', 'chapter', 'created_by')
    
    if provider_id:
        calls = calls.filter(provider_id=provider_id)
    if operation:
        calls = calls.filter(operation=operation)
    if status:
        calls = calls.filter(status=status)
    
    # Filter by date
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    calls = calls.filter(created_at__gte=start_date)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(calls, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    providers = LLMProvider.objects.filter(is_active=True)
    operations = LLMServiceCall.OPERATION_CHOICES
    statuses = LLMServiceCall.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'providers': providers,
        'operations': operations,
        'statuses': statuses,
        'filters': {
            'provider_id': provider_id,
            'operation': operation,
            'status': status,
            'days': days,
        }
    }
    
    return render(request, 'llm_integration/service_calls.html', context)
