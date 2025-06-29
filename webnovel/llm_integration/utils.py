from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import LLMServiceCall, LLMQualityMetrics, LLMProvider
import logging

logger = logging.getLogger(__name__)


def aggregate_quality_metrics(period_days=7, force_recalculate=False):
    """
    Aggregate quality metrics for LLM service calls over a specified period
    
    Args:
        period_days: Number of days to aggregate (default: 7)
        force_recalculate: Whether to recalculate existing metrics
    
    Returns:
        List of created/updated LLMQualityMetrics objects
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Get all service calls in the period
    service_calls = LLMServiceCall.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    if not service_calls.exists():
        logger.info(f"No service calls found for period {start_date} to {end_date}")
        return []
    
    # Group by provider, model, operation, and language combination
    aggregated_metrics = []
    
    # Get unique combinations
    combinations = service_calls.values(
        'provider', 'model_name', 'operation', 'source_language', 'target_language'
    ).distinct()
    
    for combo in combinations:
        # Filter calls for this combination
        calls = service_calls.filter(
            provider=combo['provider'],
            model_name=combo['model_name'],
            operation=combo['operation'],
            source_language=combo['source_language'],
            target_language=combo['target_language']
        )
        
        # Calculate metrics
        total_calls = calls.count()
        success_calls = calls.filter(status='success').count()
        success_rate = success_calls / total_calls if total_calls > 0 else 0.0
        
        avg_response_time = calls.filter(
            response_time_ms__isnull=False
        ).aggregate(Avg('response_time_ms'))['response_time_ms__avg'] or 0.0
        
        avg_quality_score = calls.filter(
            quality_score__isnull=False
        ).aggregate(Avg('quality_score'))['quality_score__avg'] or 0.0
        
        total_tokens = calls.aggregate(
            total=Sum('input_tokens') + Sum('output_tokens')
        )['total'] or 0
        
        # Calculate total cost
        provider = LLMProvider.objects.get(id=combo['provider'])
        total_cost = 0.0
        if provider.cost_per_1k_tokens and total_tokens > 0:
            total_cost = (total_tokens / 1000) * provider.cost_per_1k_tokens
        
        # Create or update metrics
        metrics, created = LLMQualityMetrics.objects.get_or_create(
            provider=provider,
            model_name=combo['model_name'],
            operation=combo['operation'],
            period_start=start_date,
            period_end=end_date,
            source_language=combo['source_language'] or '',
            target_language=combo['target_language'] or '',
            defaults={
                'total_calls': total_calls,
                'success_rate': success_rate,
                'avg_response_time_ms': avg_response_time,
                'avg_quality_score': avg_quality_score,
                'total_tokens_used': total_tokens,
                'total_cost': total_cost,
            }
        )
        
        if not created and force_recalculate:
            # Update existing metrics
            metrics.total_calls = total_calls
            metrics.success_rate = success_rate
            metrics.avg_response_time_ms = avg_response_time
            metrics.avg_quality_score = avg_quality_score
            metrics.total_tokens_used = total_tokens
            metrics.total_cost = total_cost
            metrics.save()
        
        aggregated_metrics.append(metrics)
        
        if created:
            logger.info(f"Created metrics for {provider.name}/{combo['model_name']} - {combo['operation']}")
        elif force_recalculate:
            logger.info(f"Updated metrics for {provider.name}/{combo['model_name']} - {combo['operation']}")
    
    return aggregated_metrics


def get_provider_performance_summary(period_days=7):
    """
    Get a summary of provider performance for the specified period
    
    Args:
        period_days: Number of days to analyze (default: 7)
    
    Returns:
        Dictionary with provider performance data
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Get aggregated metrics for the period
    metrics = LLMQualityMetrics.objects.filter(
        period_start=start_date,
        period_end=end_date
    )
    
    if not metrics.exists():
        # Try to aggregate if no metrics exist
        aggregate_quality_metrics(period_days)
        metrics = LLMQualityMetrics.objects.filter(
            period_start=start_date,
            period_end=end_date
        )
    
    summary = {}
    
    for provider in LLMProvider.objects.filter(is_active=True):
        provider_metrics = metrics.filter(provider=provider)
        
        if not provider_metrics.exists():
            continue
        
        # Aggregate across all operations for this provider
        total_calls = provider_metrics.aggregate(Sum('total_calls'))['total_calls__sum'] or 0
        weighted_success_rate = sum(
            m.success_rate * m.total_calls for m in provider_metrics
        ) / total_calls if total_calls > 0 else 0.0
        
        weighted_response_time = sum(
            m.avg_response_time_ms * m.total_calls for m in provider_metrics
        ) / total_calls if total_calls > 0 else 0.0
        
        total_cost = provider_metrics.aggregate(Sum('total_cost'))['total_cost__sum'] or 0.0
        total_tokens = provider_metrics.aggregate(Sum('total_tokens_used'))['total_tokens_used__sum'] or 0
        
        summary[provider.name] = {
            'display_name': provider.display_name,
            'total_calls': total_calls,
            'success_rate': weighted_success_rate,
            'avg_response_time_ms': weighted_response_time,
            'total_cost': total_cost,
            'total_tokens': total_tokens,
            'cost_per_1k_tokens': provider.cost_per_1k_tokens,
            'api_key_configured': provider.api_key_configured,
        }
    
    return summary


def get_best_provider_for_operation(operation, target_language=None, source_language=None, period_days=7):
    """
    Get the best performing provider for a specific operation and language combination
    
    Args:
        operation: The operation type (translation, abstract_generation, etc.)
        target_language: Target language code
        source_language: Source language code
        period_days: Number of days to analyze
    
    Returns:
        LLMProvider object or None
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Get metrics for the specific operation and language combination
    metrics = LLMQualityMetrics.objects.filter(
        operation=operation,
        period_start=start_date,
        period_end=end_date,
        total_calls__gte=5  # Minimum calls for reliable metrics
    )
    
    if target_language:
        metrics = metrics.filter(target_language=target_language)
    if source_language:
        metrics = metrics.filter(source_language=source_language)
    
    if not metrics.exists():
        # Fallback to general operation metrics
        metrics = LLMQualityMetrics.objects.filter(
            operation=operation,
            period_start=start_date,
            period_end=end_date,
            total_calls__gte=5
        )
    
    if not metrics.exists():
        return None
    
    # Score providers based on success rate, response time, and cost
    best_provider = None
    best_score = -1
    
    for metric in metrics:
        # Calculate composite score (higher is better)
        # Weight: 60% success rate, 30% response time (inverse), 10% cost (inverse)
        success_score = metric.success_rate * 0.6
        
        # Response time score (faster is better, max 10 seconds = 10000ms)
        response_score = max(0, (10000 - metric.avg_response_time_ms) / 10000) * 0.3
        
        # Cost score (cheaper is better, normalize to 0-1)
        cost_score = 0.1  # Default score
        if metric.total_cost > 0 and metric.total_tokens_used > 0:
            cost_per_token = metric.total_cost / metric.total_tokens_used
            # Normalize cost (assume $0.01 per token is the worst case)
            cost_score = max(0, (0.01 - cost_per_token) / 0.01) * 0.1
        
        composite_score = success_score + response_score + cost_score
        
        if composite_score > best_score:
            best_score = composite_score
            best_provider = metric.provider
    
    return best_provider


def generate_quality_report(period_days=7):
    """
    Generate a comprehensive quality report for LLM services
    
    Args:
        period_days: Number of days to analyze
    
    Returns:
        Dictionary with report data
    """
    # Aggregate metrics first
    aggregate_quality_metrics(period_days)
    
    # Get provider summary
    provider_summary = get_provider_performance_summary(period_days)
    
    # Get operation-specific metrics
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    operation_metrics = LLMQualityMetrics.objects.filter(
        period_start=start_date,
        period_end=end_date
    ).values('operation').annotate(
        total_calls=Sum('total_calls'),
        avg_success_rate=Avg('success_rate'),
        avg_response_time=Avg('avg_response_time_ms'),
        total_cost=Sum('total_cost')
    )
    
    # Get recent errors
    recent_errors = LLMServiceCall.objects.filter(
        status__in=['error', 'timeout', 'rate_limited'],
        created_at__gte=start_date
    ).select_related('provider').order_by('-created_at')[:10]
    
    report = {
        'period': {
            'start': start_date,
            'end': end_date,
            'days': period_days
        },
        'provider_summary': provider_summary,
        'operation_metrics': list(operation_metrics),
        'recent_errors': [
            {
                'provider': error.provider.display_name,
                'model': error.model_name,
                'operation': error.operation,
                'status': error.status,
                'error_message': error.error_message[:100] + '...' if len(error.error_message) > 100 else error.error_message,
                'created_at': error.created_at
            }
            for error in recent_errors
        ],
        'total_calls': sum(p['total_calls'] for p in provider_summary.values()),
        'total_cost': sum(p['total_cost'] for p in provider_summary.values()),
    }
    
    return report 