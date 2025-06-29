# LLM Integration Quality Control System

This module provides comprehensive tracking and quality control for LLM (Large Language Model) service usage in the webnovel application.

## Features

### 1. **LLM Service Call Tracking**
- Tracks every LLM API call with detailed metadata
- Records provider, model, operation type, and performance metrics
- Monitors response times, token usage, and error rates
- Links calls to specific books, chapters, and users

### 2. **Provider Management**
- Centralized configuration for multiple LLM providers
- Cost tracking per provider and model
- API key status monitoring
- Provider performance comparison

### 3. **Quality Metrics Aggregation**
- Automatic aggregation of performance metrics
- Success rate tracking by provider and operation
- Cost analysis and optimization insights
- Historical performance trends

### 4. **Quality Control Dashboard**
- Real-time monitoring of LLM service health
- Provider performance comparison
- Error tracking and alerting
- Cost analysis and optimization recommendations

## Models

### LLMProvider
Stores configuration for each LLM provider:
- Provider name and display name
- Available models and default model
- Cost per 1K tokens
- API key configuration status

### LLMServiceCall
Tracks individual API calls:
- Provider and model used
- Operation type (translation, abstract generation, etc.)
- Request parameters (temperature, max tokens)
- Response metrics (time, tokens, status)
- Error information and user context

### LLMQualityMetrics
Aggregated performance metrics:
- Success rates by provider/operation
- Average response times
- Total costs and token usage
- Time-period based aggregation

## Usage

### Setting Up Providers
```bash
python manage.py setup_llm_providers
```

### Generating Quality Reports
```bash
# Generate report for last 7 days
python manage.py generate_quality_report

# Generate report for last 30 days
python manage.py generate_quality_report --days 30

# Output as JSON
python manage.py generate_quality_report --format json
```

### Accessing the Dashboard
- Navigate to `/llm/dashboard/` for the quality control dashboard
- Access `/llm/service-calls/` to browse individual service calls
- Use `/llm/metrics/api/` for programmatic access to metrics

### Integration with LLM Service
The tracking is automatically integrated into the `LLMTranslationService`:

```python
from llm_integration.services import LLMTranslationService

# Service automatically tracks calls
service = LLMTranslationService()
result = service.translate_text(
    "Hello world", 
    "es",
    user=request.user  # Optional: for user tracking
)
```

## Benefits

### 1. **Quality Assurance**
- Monitor translation quality across providers
- Identify performance degradation early
- Track success rates and error patterns

### 2. **Cost Optimization**
- Track costs per provider and operation
- Identify most cost-effective providers
- Monitor token usage patterns

### 3. **Reliability Management**
- Automatic error tracking and categorization
- Provider fallback recommendations
- Performance trend analysis

### 4. **Business Intelligence**
- Usage pattern analysis
- Provider performance comparison
- Cost forecasting and budgeting

## Configuration

### Environment Variables
Set these environment variables for provider configuration:
```bash
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
COHERE_API_KEY=your_cohere_key
MISTRAL_API_KEY=your_mistral_key
```

### Settings
Configure in `settings.py`:
```python
# Default LLM provider
LLM_PROVIDER = "openai"
LLM_MODEL_NAME = "gpt-3.5-turbo"

# Provider-specific configurations
LLM_PROVIDERS = {
    "openai": {
        "api_key": OPENAI_API_KEY,
        "default_model": "gpt-3.5-turbo",
        "cost_per_1k_tokens": 0.002,
    },
    # ... other providers
}
```

## Admin Interface

Access the admin interface at `/admin/` to:
- View and manage LLM providers
- Browse service call history
- Monitor quality metrics
- Configure provider settings

## API Endpoints

### Quality Metrics API
`GET /llm/metrics/api/?days=7`
Returns JSON with provider performance data and recent errors.

### Dashboard
`GET /llm/dashboard/?days=7`
Web interface for quality control monitoring.

### Service Calls
`GET /llm/service-calls/?provider=1&operation=translation&status=success`
Browse and filter service call history.

## Best Practices

1. **Regular Monitoring**: Check the dashboard regularly for performance issues
2. **Cost Tracking**: Monitor costs and optimize provider usage
3. **Error Analysis**: Review error patterns and implement fallbacks
4. **Provider Diversity**: Use multiple providers for redundancy
5. **Performance Optimization**: Use the best provider for each operation type

## Troubleshooting

### Common Issues

1. **Migration Errors**: If tables already exist, use `--fake` flag:
   ```bash
   python manage.py migrate llm_integration --fake
   ```

2. **No Data**: Ensure LLM service calls are being made with tracking enabled

3. **Provider Configuration**: Run `setup_llm_providers` to configure default providers

### Debugging

- Check admin interface for detailed service call logs
- Use the quality report command for comprehensive analysis
- Monitor error patterns in the dashboard

## Future Enhancements

- Real-time alerting for performance issues
- Advanced cost optimization algorithms
- Quality scoring based on user feedback
- Automated provider selection based on performance
- Integration with external monitoring tools 